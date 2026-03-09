RVT-Swarm v4 changes
- Stronger recovery-mode topology dynamics and expert recovery action.
- Recoverability scoring now weights formation-tube recovery more heavily.
- Selector now prefers recover when bottleneck clears and penalizes lingering split/switching.
- Environment reward/metrics emphasize formation recovery, penalize oscillation and stale split states.
- Config retuned for stronger recover/aux supervision.
