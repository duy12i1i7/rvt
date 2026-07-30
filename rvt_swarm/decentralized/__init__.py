"""Fully decentralized keep/line formation-mode selection.

Runtime architecture, per robot, with no central entity anywhere in the loop:

    neighbour discovery -> ego-graph inference -> leaderless mode agreement
    -> robot-local mode-conditioned control

`system_model.py` holds the decentralization contract; every other module
imports its parameters from there.
"""
from .system_model import (  # noqa: F401
    KEEP, LINE, MODES, MODE_NAME, CommParams, ConsensusParams, K_SCORE_GRID,
    CentralizedAccessError, NeighbourRecord, RobotView, RuntimeFlags,
    describe_contract,
)
