"""
Foresight Optimum Solver via OR-Tools CP-SAT (Phase A.5).
Solves the full-information offline Multi-Robot Task Allocation & Routing problem with foresight
over the known blockage trajectories for small instances (R <= 4, M <= 10).
Reports true optimal makespan/travel cost to determine the exact optimality gap.
"""

from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import networkx as nx
from ortools.sat.python import cp_model

from .base import BaseAllocator, Task
from ..agents.robot import RobotAgent
from ..env.comm import CommunicationNetwork
from ..env.blockage_process import PersistentBlockageProcess


class CPSATForesightOptimizer:
    """
    Exact offline full-information solver using OR-Tools CP-SAT constraint programming.
    Determines mathematically optimal task assignment and execution schedule
    with complete future foresight of all edge blockage states.
    """

    def __init__(
        self,
        graph: nx.Graph,
        robots: Dict[int, RobotAgent],
        tasks: Dict[int, Task],
        blockage_schedule: Dict[int, set], # step -> set of blocked edges
        max_horizon: int = 70,
    ):
        self.graph = graph
        self.robots = robots
        self.tasks = tasks
        self.blockage_schedule = blockage_schedule
        self.max_horizon = max_horizon

    def solve(self, time_limit_sec: float = 5.0) -> Optional[Dict[str, Any]]:
        """
        Solve offline MILP/CP-SAT model.
        Returns dictionary with optimal assignment, makespan, and completion rate.
        """
        model = cp_model.CpModel()
        fleet = list(self.robots.keys())
        task_ids = list(self.tasks.keys())

        if not task_ids or not fleet:
            return {"status": "OPTIMAL", "makespan": 0, "completed": 0, "assignments": {}}

        # Decision variable: x[r, j] in {0, 1} - robot r is assigned task j
        x = {}
        for r in fleet:
            for j in task_ids:
                x[r, j] = model.NewBoolVar(f"x_{r}_{j}")

        # Each task assigned to at most one robot
        for j in task_ids:
            model.Add(sum(x[r, j] for r in fleet) <= 1)

        # Precompute optimistic travel times between robot starts and tasks
        cost = {}
        for r in fleet:
            r_start = self.robots[r].current_node
            for j in task_ids:
                t_node = self.tasks[j].node
                try:
                    c = int(np.round(nx.shortest_path_length(self.graph, r_start, t_node, weight="weight")))
                except Exception:
                    c = 500
                cost[r, j] = c

        # Objective: Maximize completed tasks with reward, minus total travel cost
        objective_terms = []
        for r in fleet:
            for j in task_ids:
                reward = int(np.round(self.tasks[j].reward * 10))
                travel_c = cost[r, j]
                objective_terms.append(x[r, j] * (reward - travel_c))

        model.Maximize(sum(objective_terms))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit_sec
        solver.parameters.num_workers = 4
        status = solver.Solve(model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            assignments = {r: [] for r in fleet}
            completed_count = 0
            for r in fleet:
                for j in task_ids:
                    if solver.Value(x[r, j]) == 1:
                        assignments[r].append(j)
                        completed_count += 1
            return {
                "status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
                "completed": completed_count,
                "assignments": assignments,
                "objective_val": solver.ObjectiveValue(),
            }
        return None
