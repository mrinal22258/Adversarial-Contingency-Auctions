"""Environment module for Adversarial Contingency Auctions framework.

Contains:
- GraphWorld: Represents the true world state and mutations.
- Adversary: Represents the strategic path blocker.
"""

from .graph_world import GraphWorld, Adversary

__all__ = ["GraphWorld", "Adversary"]
