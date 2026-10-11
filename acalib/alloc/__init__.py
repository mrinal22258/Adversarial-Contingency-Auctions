"""
Allocation mechanisms: ACA, CBBA, SSI, CBBA-Partial, CC-CBBA, Implicit, Pessimistic, Oracle.
"""

from .base import Task, BaseAllocator
from .cbba import CBBAAllocator
from .aca import ACAAllocator
from .ssi import SSIAllocator
from .cbba_partial import CBBAPartialReplanAllocator
from .cc_cbba import ChanceConstrainedCBBAAllocator
from .implicit import ImplicitCoordinationAllocator
from .pessimistic import PessimisticRobustAllocator, CentralizedOracleAllocator

def _create_allocator(alloc_type: str, **kwargs):
    if alloc_type in ("foresight_opt", "foresight_optimal"):
        from .foresight_opt import ForesightOptAllocator
        return ForesightOptAllocator(**kwargs)
    raise ValueError(f"Unknown allocator type: {alloc_type}")

def __getattr__(name: str):
    if name == "ForesightOptAllocator":
        from .foresight_opt import ForesightOptAllocator
        return ForesightOptAllocator
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "Task",
    "BaseAllocator",
    "CBBAAllocator",
    "ACAAllocator",
    "SSIAllocator",
    "CBBAPartialReplanAllocator",
    "ChanceConstrainedCBBAAllocator",
    "ImplicitCoordinationAllocator",
    "PessimisticRobustAllocator",
    "CentralizedOracleAllocator",
    "ForesightOptAllocator",
    "_create_allocator",
]
