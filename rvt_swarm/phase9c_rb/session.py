"""Publication scientific executor (RB-3), locality boundary (RB-4),
Phase 6 adapter (RB-5) and snapshot/restore (RB-7).

One authoritative session. It *composes* frozen modules and duplicates none:

* Phase 6 base action and safety projection come from
  `ForcedTopologyRuntimeAdapter` -> `RobotLocalController` ->
  `RobotLocalSafetyProjection`. No controller equation and no gain is restated
  here.
* Phase 7 lifecycle comes from `TransitionProtocolNode`, one instance per
  robot. This module never computes a team-wide readiness or a central
  candidate decision.
* Metric V3 comes from `formation_metric_v3`.
* Integration reproduces the frozen environment step exactly:
  `soft_clip(a, a_max)`, `v += a*dt`, radial speed clip, `p += v*dt`.

The locality boundary is `_build_robot_view`. It is the only function that
reads global state on a robot's behalf, and everything it returns is
ego-relative and range-gated. Nothing downstream of it receives the session.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from ..decentralized.ego_graph_v2 import (
    RobotLocalTopologyMetadata, prepare_robot_local_topology_metadata,
)
from ..decentralized.forced_topology_runtime import ForcedTopologyRuntimeAdapter
from ..decentralized.local_control_types import LocalObstacleControlState
from ..decentralized.system_model import NeighbourRecord, RobotView
from ..decentralized.transition_protocol import (
    TransitionProtocolNode, TransitionProtocolRuntimeOptions,
)
from ..runtime_configuration import (
    DEFAULT_RUNTIME_CONFIG, RuntimeConfig, canonical_runtime_hash,
)
from ..topology_registry import COMPACT, LINE, generate_persistent_roles
from ..utils import soft_clip
from .binding import ScenarioRuntimeBinding
from .channel import build_channel, CommunicationChannel
from .dynamics import build_dynamic_world, DynamicWorld
from .streams import (
    STREAM_INITIAL_POSITION, STREAM_INITIAL_VELOCITY, STREAM_ROBOT_ACCELERATION,
    STREAM_S5_ACCELERATION, CounterStream,
)
from .world import build_static_world, StaticWorld

Vec2 = Tuple[float, float]

STATE_BROADCAST = "state_broadcast"


@dataclass
class RobotRuntimeState:
    """Per-robot mutable state. Simulator scope; robots never read each other's."""

    robot_id: int
    role_id: str
    position: Vec2
    velocity: Vec2
    acceleration: Vec2
    committed_topology: int
    compact_offset: Vec2
    line_offset: Vec2
    protocol_node: TransitionProtocolNode
    adapter_by_topology: Mapping[int, ForcedTopologyRuntimeAdapter]
    local_topology_metadata: object = None
    # Defect 9: after commit the robot follows the FROZEN role-space profile,
    # not an immediate target swap. `transition_executor` holds the frozen
    # RobotLocalTransitionExecutor while the profile is running; it is cleared
    # on completion, after which normal topology hold resumes.
    transition_executor: object = None
    transition_source_topology: Optional[int] = None
    transition_commit_seconds: Optional[float] = None
    neighbour_table: Dict[int, Dict[str, object]] = field(default_factory=dict)
    safety_unresolved: bool = False
    safety_infeasible_seen: bool = False
    safety_solver_failure_seen: bool = False
    projection_intervened_count: int = 0
    steps_since_decision: int = 0
    local_progress: float = 0.0
    transition_progress: float = 0.0
    policy_state: Dict[str, object] = field(default_factory=dict)

    def role_offset(self, topology_id: int) -> Vec2:
        return self.compact_offset if topology_id == COMPACT else self.line_offset


@dataclass
class EpisodeTermination:
    cause: str
    control_step: int
    time_seconds: float
    detail: str = ""


class SimulatorEpisodeSession:
    """Complete executable episode: binding -> world -> robots -> evaluator inputs."""

    def __init__(self, binding: ScenarioRuntimeBinding, *, protocol: Mapping[str, object],
                 target_contract: Mapping[str, object], seeds: Mapping[str, int],
                 source_policy: object,
                 runtime_config: RuntimeConfig = DEFAULT_RUNTIME_CONFIG,
                 episode_id: str = "episode") -> None:
        self.binding = binding
        self.protocol = protocol
        self.target_contract = target_contract
        # The runtime config is team-size specific: the frozen protocol node
        # requires `mission.team_size == len(member_ids)`, and the derived
        # diameter and round counts follow team size. `RuntimeConfig.for_team_size`
        # is the same approved constructor the Phase 8E compiler used, so the
        # canonical hash must reproduce the compiled expectation exactly.
        if int(runtime_config.mission.team_size) != int(binding.team_size):
            runtime_config = RuntimeConfig.for_team_size(int(binding.team_size))
        expected_config_hash = str(binding.config_hashes["runtime_configuration_sha256"])
        actual_config_hash = canonical_runtime_hash(runtime_config)
        if actual_config_hash != expected_config_hash:
            raise ValueError(
                "runtime configuration does not match the compiled specification: "
                f"expected {expected_config_hash}, derived {actual_config_hash}")
        self.runtime_config = runtime_config
        self.episode_id = episode_id
        self.seeds = {str(k): int(v) for k, v in seeds.items()}
        self.source_policy = source_policy

        self.control_period = float(runtime_config.physical.control_period_seconds)
        self.horizon_seconds = binding.horizon_seconds
        self.team_size = int(binding.team_size)

        specification = _specification_from_binding(binding)
        self.static_world: StaticWorld = build_static_world(
            specification, runtime_config, protocol, target_contract)
        self.dynamic_world: DynamicWorld = build_dynamic_world(
            specification, runtime_config, target_contract,
            self.seeds.get("dynamic_obstacle", 0))
        self.channel: CommunicationChannel = build_channel(
            specification, self.team_size, runtime_config,
            self.seeds.get("communication", 0))

        self.mission_direction: Vec2 = (
            float(binding.mission_frame["longitudinal_axis"][0]),      # type: ignore[index]
            float(binding.mission_frame["longitudinal_axis"][1]))      # type: ignore[index]
        self.mission_origin: Vec2 = (
            float(binding.mission_frame["initial_topology_origin_meters"][0]),   # type: ignore[index]
            float(binding.mission_frame["initial_topology_origin_meters"][1]))   # type: ignore[index]
        self.goal_center: Vec2 = (
            float(binding.goal_contract["center_meters"][0]),          # type: ignore[index]
            float(binding.goal_contract["center_meters"][1]))          # type: ignore[index]

        # Counter-keyed streams. Seed identity only -- no mutable RNG object.
        self.position_stream = CounterStream(
            self.seeds.get("initial_condition", 0), STREAM_INITIAL_POSITION)
        self.velocity_stream = CounterStream(
            self.seeds.get("initial_condition", 0), STREAM_INITIAL_VELOCITY)
        self.s5_stream = CounterStream(
            self.seeds.get("initial_condition", 0), STREAM_S5_ACCELERATION)
        self.disturbance_stream: Optional[CounterStream] = None
        self.disturbance_max_magnitude = 0.0

        self.control_step = 0
        self.time_seconds = 0.0
        self.termination: Optional[EpisodeTermination] = None
        self.robots: List[RobotRuntimeState] = []
        self.max_longitudinal_progress = 0.0
        self.irreversible_loss_open = False
        self.collision_detected = False
        self.deadlock_detected = False
        self.deadlock_window_start_progress = 0.0
        self.deadlock_window_elapsed = 0.0
        self.numerically_valid = True
        self.initialization_valid = True
        self.lifecycle_counter = 0
        self.role_set = None
        self.event_log: List[Dict[str, object]] = []
        # Metric V3 dwell clocks, one per admitted candidate topology. Physical
        # time, reset to zero on any exit from the tube, exactly as the frozen
        # condition specifies.
        self.metric_v3_dwell: Dict[int, float] = {COMPACT: 0.0, LINE: 0.0}

        self._initialize_robots()

    # ------------------------------------------------------------------
    # Initialization (RB-2 / initialization contract)
    # ------------------------------------------------------------------
    def _initialize_robots(self) -> None:
        n = self.team_size
        role_set = generate_persistent_roles(n)
        self.role_set = role_set
        nominal = self.binding.nominal_positions
        role_ids = self.binding.role_ids
        bound_position = float(self.binding.initialization["position_perturbation_bound_meters"])   # type: ignore[index]
        bound_velocity = float(
            self.binding.initialization["velocity_component_bound_meters_per_second"])             # type: ignore[index]
        max_speed = float(self.runtime_config.physical.maximum_speed_meters_per_second)

        longitudinal = self.mission_direction
        lateral = (-longitudinal[1], longitudinal[0])

        options = TransitionProtocolRuntimeOptions(transition_protocol_v1_enabled=True)
        member_ids = tuple(range(n))

        # Publication initialization is COMPACT. The only admitted override is
        # S2's offline forced-topology interface; KEEP is never reachable here
        # because `initial_topology_override` may only return LINE.
        initial_topology = COMPACT
        override = getattr(self.source_policy, "initial_topology_override", None)
        if callable(override):
            requested = override()
            if requested is not None:
                if requested != LINE:
                    raise ValueError(
                        f"only LINE may override publication initialization, got {requested}")
                initial_topology = LINE
        self.initial_topology = initial_topology

        for robot_id in range(n):
            metadata = prepare_robot_local_topology_metadata(
                role_set, robot_id, self.runtime_config.formation)
            adapters = {
                topology: ForcedTopologyRuntimeAdapter(self.runtime_config, metadata, topology)
                for topology in (COMPACT, LINE)
            }
            # Mission-frame perturbations, then mapped into world axes.
            dx = self.position_stream.symmetric(bound_position, robot_id, "longitudinal")
            dy = self.position_stream.symmetric(bound_position, robot_id, "lateral")
            vx = self.velocity_stream.symmetric(bound_velocity, robot_id, "longitudinal")
            vy = self.velocity_stream.symmetric(bound_velocity, robot_id, "lateral")

            base = nominal[robot_id]
            position = (base[0] + dx * longitudinal[0] + dy * lateral[0],
                        base[1] + dx * longitudinal[1] + dy * lateral[1])
            velocity = (vx * longitudinal[0] + vy * lateral[0],
                        vx * longitudinal[1] + vy * lateral[1])
            if math.hypot(*velocity) > max_speed:
                # Contract: reject, do not rescale and do not redraw.
                self.initialization_valid = False
                self.termination = EpisodeTermination(
                    "INITIALIZATION_INVALID", 0, 0.0, f"robot {robot_id} initial speed")

            compact_offset = metadata.candidate(COMPACT).own_role_offset_meters
            line_offset = metadata.candidate(LINE).own_role_offset_meters

            # S2 is the sole initialization specialisation the frozen contract
            # allows: "the offline forced topology interface initializes LINE
            # role targets at time zero without creating a source-equals-target
            # epoch". The compiled `nominal_positions_meters` are COMPACT poses,
            # so the LINE poses are rebuilt from the same frozen formula
            # `p_i = origin + R(heading) * role_offset_i` used by the compiler.
            if initial_topology == LINE:
                offset = line_offset
                position = (
                    self.mission_origin[0] + longitudinal[0] * float(offset[0])
                    + lateral[0] * float(offset[1]) + dx * longitudinal[0] + dy * lateral[0],
                    self.mission_origin[1] + longitudinal[1] * float(offset[0])
                    + lateral[1] * float(offset[1]) + dx * longitudinal[1] + dy * lateral[1])
            self.robots.append(RobotRuntimeState(
                robot_id=robot_id,
                role_id=role_ids[robot_id] if robot_id < len(role_ids) else metadata.observer_role_id,
                position=position, velocity=velocity, acceleration=(0.0, 0.0),
                committed_topology=initial_topology,
                compact_offset=(float(compact_offset[0]), float(compact_offset[1])),
                line_offset=(float(line_offset[0]), float(line_offset[1])),
                protocol_node=TransitionProtocolNode(
                    robot_id=robot_id, member_ids=member_ids,
                    runtime_config=self.runtime_config, committed_topology=initial_topology,
                    options=options),
                adapter_by_topology=adapters,
                local_topology_metadata=metadata,
            ))

        if not bool(self.binding.initialization["nominal_validity"]["valid"]):   # type: ignore[index]
            self.initialization_valid = False
            self.termination = self.termination or EpisodeTermination(
                "INITIALIZATION_INVALID", 0, 0.0, "nominal initial state invalid for this N")
        if self.termination is None and self._static_collision_at_start():
            self.initialization_valid = False
            self.termination = EpisodeTermination(
                "INITIALIZATION_INVALID", 0, 0.0, "initial collision")
        self.max_longitudinal_progress = self._longitudinal_progress()
        self.deadlock_window_start_progress = self.max_longitudinal_progress

    def _static_collision_at_start(self) -> bool:
        for robot in self.robots:
            if self.static_world.static_collision(robot.position) is not None:
                return True
            if self.static_world.boundary_exit(robot.position):
                return True
        clearance = float(self.runtime_config.derived.robot_robot_required_clearance_meters)
        for i in range(len(self.robots)):
            for j in range(i + 1, len(self.robots)):
                if math.dist(self.robots[i].position, self.robots[j].position) <= clearance:
                    return True
        return False

    # ------------------------------------------------------------------
    # Locality boundary (RB-4) -- the ONLY global read on a robot's behalf
    # ------------------------------------------------------------------
    def _build_robot_view(self, robot: RobotRuntimeState) -> RobotView:
        """Approved robot-local input only.

        Peers come from the neighbour table, i.e. from *delivered* messages,
        never from the joint state array. Obstacles come from range-gated
        ego-relative sensor tokens. Nothing here exposes family id, headroom,
        the layout, world bounds, future obstacle motion, the future
        communication schedule, a global centroid or a candidate outcome.

        `RobotView.role_keep` / `role_line` are legacy field names. Publication
        execution is COMPACT/LINE, so the COMPACT offset occupies the first
        slot. The Phase 6 path does not read either field -- it reads the
        topology metadata slice -- so no KEEP geometry is introduced.
        """
        neighbours: List[NeighbourRecord] = []
        for peer_id, entry in sorted(robot.neighbour_table.items()):
            age = self.time_seconds - float(entry["timestamp"])
            if self.channel.is_stale(age):
                continue                      # stale never enters features or agreement
            position = entry["position"]
            velocity = entry["velocity"]
            neighbours.append(NeighbourRecord(
                robot_id=int(peer_id),
                rel_position=(float(position[0]) - robot.position[0],
                              float(position[1]) - robot.position[1]),
                rel_velocity=(float(velocity[0]) - robot.velocity[0],
                              float(velocity[1]) - robot.velocity[1]),
                role_keep=tuple(entry["compact_offset"]),      # type: ignore[arg-type]
                role_line=tuple(entry["line_offset"]),         # type: ignore[arg-type]
                committed_mode=int(entry["committed_topology"]),
                epoch_id=int(entry["epoch_id"]),
                message_age_steps=int(round(age / self.control_period)),
                degree=int(entry["degree"]),
                link_valid=True,
                packet_loss_estimate=0.0,
            ))

        # STATIC tokens only. Dynamic obstacles are deliberately excluded here
        # and supplied separately by `_dynamic_obstacle_relative_states`:
        # `RobotView.obstacles` carries no velocity, so the frozen adapter
        # assigns every entry the static relative velocity `-own_velocity`.
        # Including a dynamic obstacle here as well would enter it twice -- once
        # with a wrong (stationary) relative velocity and once with the right
        # one -- and the wrong copy would drive the time-to-collision term.
        obstacles = [(float(offset[0]), float(offset[1]), float(radius))
                     for offset, radius, _ in self.static_world.observable_tokens(
                         robot.position, float(self.runtime_config.sensing.obstacle_sensing_range_meters))]

        return RobotView(
            robot_id=robot.robot_id,
            position=robot.position,
            velocity=robot.velocity,
            role_keep=robot.compact_offset,
            role_line=robot.line_offset,
            committed_mode=robot.committed_topology,
            epoch_id=int(robot.protocol_node.mode_epoch_count),
            steps_since_decision=int(robot.steps_since_decision),
            local_progress=float(robot.local_progress),
            goal=self.goal_center,
            mission_dir=self.mission_direction,
            neighbours=tuple(neighbours),
            obstacles=tuple(obstacles),
        )

    def _dynamic_obstacle_relative_states(self, robot: RobotRuntimeState
                                          ) -> Tuple[LocalObstacleControlState, ...]:
        """Dynamic tokens with true relative velocity.

        `ForcedTopologyRuntimeAdapter.build_input` assigns every obstacle the
        static relative velocity `-own_velocity`, which is correct for walls and
        circles but would make an F9 obstacle look stationary to the
        time-to-collision term. The frozen adapter is not modified; its output
        is refined with `dataclasses.replace`, the same composition the frozen
        Phase 6 qualification fixtures use.
        """
        states: List[LocalObstacleControlState] = []
        for offset, velocity, radius, key in self.dynamic_world.observable_tokens(
                robot.position, self.time_seconds):
            states.append(LocalObstacleControlState(
                source_key=f"dynamic:{key}",
                relative_center_meters=(float(offset[0]), float(offset[1])),
                radius_meters=float(radius),
                relative_velocity_meters_per_second=(
                    float(velocity[0]) - robot.velocity[0],
                    float(velocity[1]) - robot.velocity[1]),
            ))
        return tuple(states)

    # ------------------------------------------------------------------
    # Communication
    # ------------------------------------------------------------------
    def _communicate(self) -> None:
        degree_by_robot: Dict[int, int] = {}
        for sender in self.robots:
            degree = sum(1 for other in self.robots
                         if other.robot_id != sender.robot_id
                         and self.channel.physical_edge(sender.position, other.position))
            degree_by_robot[sender.robot_id] = degree
        for sender in self.robots:
            payload = {
                "position": sender.position, "velocity": sender.velocity,
                "compact_offset": sender.compact_offset, "line_offset": sender.line_offset,
                "committed_topology": sender.committed_topology,
                "epoch_id": int(sender.protocol_node.mode_epoch_count),
                "degree": degree_by_robot[sender.robot_id],
                "timestamp": self.time_seconds,
                "protocol_state": sender.protocol_node.state,
                "active_intent": sender.protocol_node.active_intent,
            }
            for receiver in self.robots:
                if receiver.robot_id == sender.robot_id:
                    continue
                if not self.channel.physical_edge(sender.position, receiver.position):
                    continue
                self.channel.send(sender.robot_id, receiver.robot_id,
                                  STATE_BROADCAST, payload, self.time_seconds)

        for message in self.channel.deliver(self.channel.tick):
            receiver = self.robots[message.receiver_id]
            payload = dict(message.payload)             # type: ignore[arg-type]
            receiver.neighbour_table[message.sender_id] = payload

    # ------------------------------------------------------------------
    # One control step
    # ------------------------------------------------------------------
    def step(self) -> None:
        if self.termination is not None:
            return
        self._communicate()

        max_accel = float(self.runtime_config.physical.maximum_acceleration_meters_per_second_squared)
        max_speed = float(self.runtime_config.physical.maximum_speed_meters_per_second)
        dt = self.control_period

        previous_positions = [robot.position for robot in self.robots]
        actions: List[Vec2] = []

        for robot in self.robots:
            view = self._build_robot_view(robot)
            # While the frozen profile is running the robot's local target comes
            # from RobotLocalTransitionExecutor, whose build_input/evaluate
            # interface is identical to the forced-topology adapter. No
            # interpolation is recomputed here.
            adapter = (robot.transition_executor if robot.transition_executor is not None
                       else robot.adapter_by_topology[robot.committed_topology])
            controller_input = adapter.build_input(view, self.time_seconds)
            dynamic_states = self._dynamic_obstacle_relative_states(robot)
            if dynamic_states:
                controller_input = replace(
                    controller_input,
                    obstacle_states=controller_input.obstacle_states + dynamic_states)

            # Source policy acts on robot-local data only.
            self.source_policy.observe(self, robot, view, controller_input)

            controller = getattr(adapter, 'controller', None) or adapter.adapter.controller
            output = controller.evaluate(controller_input)
            action = (float(output.projected_action[0]), float(output.projected_action[1]))

            disturbance = self._disturbance_for(robot)
            if disturbance != (0.0, 0.0):
                # Additive command disturbance BEFORE the unchanged projection.
                projection = controller.safety_projection
                base = (float(output.base_action[0]) + disturbance[0],
                        float(output.base_action[1]) + disturbance[1])
                if projection is not None:
                    result = projection.project(base, controller_input)
                    action = (float(result.projected_action[0]), float(result.projected_action[1]))
                    output = replace(output, projection_infeasible=result.infeasible,
                                     projection_solver_failed=result.solver_failed)
                else:
                    action = base

            if output.projection_infeasible:
                robot.safety_infeasible_seen = True
                robot.safety_unresolved = True
            elif output.projection_solver_failed:
                robot.safety_solver_failure_seen = True
                robot.safety_unresolved = True
            elif robot.safety_unresolved:
                robot.safety_unresolved = False       # a later feasible projection clears it
            if output.projection_intervened:
                robot.projection_intervened_count += 1
            if not all(math.isfinite(value) for value in action):
                self.numerically_valid = False
                self.termination = EpisodeTermination(
                    "NUMERICAL_INVALID", self.control_step, self.time_seconds,
                    f"robot {robot.robot_id} nonfinite action")
                return
            actions.append(action)

        # Frozen semi-implicit integration, identical to the environment step.
        for robot, action in zip(self.robots, actions):
            clipped = soft_clip(np.asarray(action, dtype=np.float32), max_accel)
            velocity = (robot.velocity[0] + float(clipped[0]) * dt,
                        robot.velocity[1] + float(clipped[1]) * dt)
            speed = math.hypot(*velocity)
            if speed > max_speed:
                velocity = (velocity[0] / speed * max_speed, velocity[1] / speed * max_speed)
            robot.acceleration = (float(clipped[0]), float(clipped[1]))
            robot.velocity = velocity
            robot.position = (robot.position[0] + velocity[0] * dt,
                              robot.position[1] + velocity[1] * dt)
            robot.steps_since_decision += 1

        self.control_step += 1
        self.time_seconds = self.control_step * self.control_period
        self.channel.advance()

        self._check_collisions(previous_positions)
        self._update_progress()
        self._run_protocol_step()
        if self.termination is None and self.time_seconds >= self.horizon_seconds:
            self.termination = EpisodeTermination(
                "HORIZON_COMPLETE", self.control_step, self.time_seconds)

    def _disturbance_for(self, robot: RobotRuntimeState) -> Vec2:
        vector = (0.0, 0.0)
        if self.disturbance_stream is not None and self.disturbance_max_magnitude > 0.0:
            vector = self.disturbance_stream.uniform_disk(
                self.disturbance_max_magnitude, robot.robot_id, self.control_step)
        extra = self.source_policy.acceleration_disturbance(self, robot)
        return (vector[0] + extra[0], vector[1] + extra[1])

    def _check_collisions(self, previous_positions: Sequence[Vec2]) -> None:
        if self.termination is not None:
            return
        clearance = float(self.runtime_config.derived.robot_robot_required_clearance_meters)
        tolerance = self.static_world.collision_tolerance_meters
        from .world import _moving_point_min_distance
        time_a = (self.control_step - 1) * self.control_period
        time_b = self.time_seconds
        for index, robot in enumerate(self.robots):
            pa, pb = previous_positions[index], robot.position
            if self.static_world.swept_static_collision(pa, pb) is not None:
                self.collision_detected = True
                self.termination = EpisodeTermination(
                    "COLLISION", self.control_step, self.time_seconds,
                    f"robot {robot.robot_id} static")
                return
            if self.dynamic_world.swept_collision(pa, pb, time_a, time_b) is not None:
                self.collision_detected = True
                self.termination = EpisodeTermination(
                    "COLLISION", self.control_step, self.time_seconds,
                    f"robot {robot.robot_id} dynamic")
                return
            if self.static_world.boundary_exit(pb):
                self.termination = EpisodeTermination(
                    "WORLD_BOUNDARY_EXIT", self.control_step, self.time_seconds,
                    f"robot {robot.robot_id}")
                return
        for i in range(len(self.robots)):
            for j in range(i + 1, len(self.robots)):
                separation = _moving_point_min_distance(
                    previous_positions[i], self.robots[i].position,
                    previous_positions[j], self.robots[j].position)
                if separation <= clearance + tolerance:
                    self.collision_detected = True
                    self.termination = EpisodeTermination(
                        "COLLISION", self.control_step, self.time_seconds,
                        f"robots {i}-{j}")
                    return

    # ------------------------------------------------------------------
    # Progress, deadlock and goal (Target V4 inputs)
    # ------------------------------------------------------------------
    def fitted_topology_origin(self, topology_id: int) -> Vec2:
        """Least-squares topology origin: mean of (position - rotated role offset).

        The same estimator for COMPACT and LINE, which is what makes the goal
        and deadlock predicates topology-neutral.
        """
        ex, ey = self.mission_direction
        total_x = total_y = 0.0
        for robot in self.robots:
            offset = robot.role_offset(topology_id)
            rotated = (ex * offset[0] - ey * offset[1], ey * offset[0] + ex * offset[1])
            total_x += robot.position[0] - rotated[0]
            total_y += robot.position[1] - rotated[1]
        count = float(len(self.robots))
        return (total_x / count, total_y / count)

    def _longitudinal_progress(self) -> float:
        origin = self.fitted_topology_origin(self.robots[0].committed_topology
                                             if self.robots else COMPACT)
        delta = (origin[0] - self.mission_origin[0], origin[1] - self.mission_origin[1])
        return delta[0] * self.mission_direction[0] + delta[1] * self.mission_direction[1]

    def _any_protocol_paused(self) -> bool:
        paused = set(self.target_contract["conditions"]["no_persistent_deadlock"]   # type: ignore[index]
                     ["paused_states"])
        return any(robot.protocol_node.state in paused for robot in self.robots)

    def _update_progress(self) -> None:
        if self.termination is not None:
            return
        conditions = self.target_contract["conditions"]                       # type: ignore[index]
        progress = self._longitudinal_progress()
        for robot in self.robots:
            robot.local_progress = progress

        spacing = float(self.runtime_config.formation.nominal_spacing_meters)
        margin = float(self.runtime_config.formation.spacing_margin_meters)
        if progress > self.max_longitudinal_progress:
            self.max_longitudinal_progress = progress
            self.irreversible_loss_open = False
        elif self.max_longitudinal_progress - progress > spacing:
            self.irreversible_loss_open = True
        elif self.irreversible_loss_open and self.max_longitudinal_progress - progress <= margin:
            self.irreversible_loss_open = False

        deadlock = conditions["no_persistent_deadlock"]
        if self._any_protocol_paused():
            # Pause and DISCARD the partial window, per the frozen contract.
            self.deadlock_window_elapsed = 0.0
            self.deadlock_window_start_progress = progress
        else:
            self.deadlock_window_elapsed += self.control_period
            if self.deadlock_window_elapsed >= float(deadlock["window_seconds"]) - 1e-12:
                advanced = progress - self.deadlock_window_start_progress
                if advanced < float(deadlock["threshold_meters"]):
                    self.deadlock_detected = True
                    self.termination = EpisodeTermination(
                        "PERSISTENT_DEADLOCK", self.control_step, self.time_seconds)
                    return
                self.deadlock_window_elapsed = 0.0
                self.deadlock_window_start_progress = progress

        from .protocol_session import _inside_candidate_tube
        for topology in (COMPACT, LINE):
            if _inside_candidate_tube(self, topology):
                self.metric_v3_dwell[topology] += self.control_period
            else:
                self.metric_v3_dwell[topology] = 0.0

        goal = conditions["downstream_goal_complete"]
        origin = self.fitted_topology_origin(self.robots[0].committed_topology)
        if math.dist(origin, self.goal_center) <= float(goal["tolerance_meters"]):
            dwell = float(self.robots[0].policy_state.get("goal_dwell", 0.0)) + self.control_period
            for robot in self.robots:
                robot.policy_state["goal_dwell"] = dwell
            if dwell >= float(goal["required_dwell_seconds"]) - 1e-12:
                self.termination = EpisodeTermination(
                    "GOAL_COMPLETE", self.control_step, self.time_seconds)
        else:
            for robot in self.robots:
                robot.policy_state["goal_dwell"] = 0.0

    # ------------------------------------------------------------------
    # Phase 7 session adapter (RB-6)
    # ------------------------------------------------------------------
    def _run_protocol_step(self) -> None:
        """Drive each robot's own protocol node. No central decision is made here."""
        from .protocol_session import advance_transition_lifecycle
        advance_transition_lifecycle(self)

    def request_candidate(self, robot: RobotRuntimeState, candidate_topology: int,
                          event_type: str) -> bool:
        """Origination by one robot on its own evidence."""
        from .protocol_session import originate_candidate
        return originate_candidate(self, robot, candidate_topology, event_type)

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------
    def run_until(self, time_seconds: float) -> None:
        while self.termination is None and self.time_seconds < time_seconds - 1e-12:
            self.step()

    def run_episode(self) -> EpisodeTermination:
        self.run_until(self.horizon_seconds)
        if self.termination is None:
            self.termination = EpisodeTermination(
                "HORIZON_COMPLETE", self.control_step, self.time_seconds)
        return self.termination


def build_event_plan(binding: ScenarioRuntimeBinding, source_policy_contracts: Mapping[str, object],
                     runtime_config: RuntimeConfig = DEFAULT_RUNTIME_CONFIG):
    """ET-addendum landmark event plan for this binding.

    S0 reads it because it is explicitly an offline scripted collection policy.
    It contains landmark positions only -- never a time, a horizon fraction, a
    headroom category or an outcome.
    """
    from ..phase8e.event_timing import build_family_event_plan
    from ..phase8e.event_timing_artifacts import SUPPORT_DISC_RADIUS_METERS
    table = dict(source_policy_contracts["policies"]["S0_SCRIPTED_DIAGNOSTIC"]
                 ["machine_readable_script"])
    topologies = tuple(int(entry[1]) for entry in table.get(binding.family, ()))
    specification = _specification_from_binding(binding)
    specification["mission_frame"] = binding.mission_frame
    return build_family_event_plan(
        specification, binding.team_size, topologies,
        sensing_range_meters=float(runtime_config.sensing.obstacle_sensing_range_meters),
        nominal_spacing_meters=float(runtime_config.formation.nominal_spacing_meters),
        support_disc_radius_meters=SUPPORT_DISC_RADIUS_METERS,
        maximum_speed_meters_per_second=float(
            runtime_config.physical.maximum_speed_meters_per_second))


def _specification_from_binding(binding: ScenarioRuntimeBinding) -> Dict[str, object]:
    """Reassemble the compiled fields the world builders need from the binding.

    The binding is the single source; the executor never re-reads the layout
    file, so a binding and its session cannot drift apart.
    """
    static = dict(binding.static_world_contract)
    return {
        "static_obstacles": static["static_obstacles"],
        "passages": static["passages"],
        "world_bounds_meters": static["world_bounds_meters"],
        "dynamic_obstacles": dict(binding.dynamic_obstacle_contract)["dynamic_obstacles"],
        "communication": dict(binding.communication_contract),
    }
