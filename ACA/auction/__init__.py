"""Auction module for Adversarial Contingency Auctions framework.

Contains:
- Task: Target objectives requiring dynamic allocation.
- Bid: Bid offers proposed by agents.
- AuctionEngine: Orchestrates evaluation and winner determination.
"""

from .engine import Task, Bid, AuctionEngine

__all__ = ["Task", "Bid", "AuctionEngine"]
