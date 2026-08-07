"""Counter-keyed deterministic streams (RB-9).

The protocol freezes `sha256-canonical-counter-uint64/v1`:

    u = uint64_be(SHA256(canonical_json([prf_version, seed, process, *counter]))[0:8]) / 2**64

There is deliberately **no mutable RNG object**. A stream is a `(seed, process)`
pair plus an explicit counter tuple supplied at every draw, so:

* two candidate clones holding the same seed identity produce identical
  realizations without sharing state, and neither can advance the other's
  stream (the failure mode `PHASE8E_INITIALIZATION_AND_DISTURBANCE_CONTRACT.md`
  names when it says "candidate clones carry the seed identity and counter
  coordinates, not a shared mutable RNG object");
* snapshot/restore is trivially exact -- there is no RNG state to restore, only
  the counter coordinates, which are themselves derived from robot id, step and
  message identity;
* job execution order cannot change any drawn value.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

from ..phase8e.protocol import counter_uniform

PRF_VERSION = "sha256-canonical-counter-uint64/v1"

# Frozen stream names. `seed_binding.streams` in the executable protocol maps
# each to its source job field; nothing here invents a stream.
STREAM_INITIAL_POSITION = "initial_position"
STREAM_INITIAL_VELOCITY = "initial_velocity"
STREAM_ROBOT_ACCELERATION = "robot_acceleration"
STREAM_S5_ACCELERATION = "s5_acceleration"
STREAM_COMMUNICATION = "communication"

NAMED_STREAMS: Tuple[str, ...] = (
    STREAM_INITIAL_POSITION,
    STREAM_INITIAL_VELOCITY,
    STREAM_ROBOT_ACCELERATION,
    STREAM_S5_ACCELERATION,
    STREAM_COMMUNICATION,
)


@dataclass(frozen=True)
class CounterStream:
    """An immutable `(seed, process)` handle. Draws take explicit coordinates."""

    seed: int
    process: str

    def uniform(self, *counter: object) -> float:
        """u in [0,1) for these counter coordinates. Referentially transparent."""
        return counter_uniform(self.seed, self.process, *counter)

    def closed_interval(self, low: float, high: float, *counter: object) -> float:
        """`a + (b-a)*u` -- the frozen `closed_interval_mapping`.

        The upper endpoint is approached but not reached; that is stated in the
        contract, so it is not a defect to be "fixed" with a +1 ulp nudge.
        """
        return low + (high - low) * self.uniform(*counter)

    def symmetric(self, bound: float, *counter: object) -> float:
        return self.closed_interval(-bound, bound, *counter)

    def uniform_disk(self, max_radius: float, *counter: object) -> Tuple[float, float]:
        """`radius = max_radius*sqrt(u_radius)`, `angle = 2*pi*u_angle`.

        Two distinct counter coordinates, so the radius draw cannot correlate
        with the angle draw.
        """
        radius = max_radius * math.sqrt(self.uniform(*counter, "radius"))
        angle = 2.0 * math.pi * self.uniform(*counter, "angle")
        return (radius * math.cos(angle), radius * math.sin(angle))

    def bernoulli(self, probability: float, *counter: object) -> bool:
        if probability <= 0.0:
            return False
        return self.uniform(*counter) < probability

    def identity(self) -> Tuple[str, int, str]:
        """What a snapshot stores. There is no other state."""
        return (PRF_VERSION, int(self.seed), str(self.process))
