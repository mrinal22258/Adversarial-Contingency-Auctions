import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from experiments.sitl.world import PhysicsWorld
from experiments.sitl.robot import DiffDriveRobotSITL

t0 = time.perf_counter()
w = PhysicsWorld("warehouse_movingai")
print(f"World loaded in: {time.perf_counter() - t0:.4f} s", flush=True)

t1 = time.perf_counter()
r = DiffDriveRobotSITL(0, w.client_id, (10.0, 10.0))
print(f"Robot created in: {time.perf_counter() - t1:.4f} s", flush=True)

t2 = time.perf_counter()
for _ in range(50):
    r.update_controller(0.05)
    w.step_simulation(1)
print(f"50 steps physics in: {time.perf_counter() - t2:.4f} s", flush=True)

w.close()
print("Clean exit.", flush=True)
