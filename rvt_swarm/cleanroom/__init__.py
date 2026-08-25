"""Clean-room scientific engine for the final RVT-Swarm program.

Every rule the clean-room protocol freezes lives here exactly once. Orchestration
scripts consume the executable manifest and call into this package; they never
restate a scientific rule themselves. That separation is the structural fix for
the pilot programme's Stage-5D failure, where an orchestration script chose a
family statistic the frozen rule did not define.
"""
