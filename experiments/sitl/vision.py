"""
Synthetic-Vision Simulation with In-the-Loop ArUco Marker Detection (Step 3.12 & 3.13).
Pipeline:
Simulated Robot Ground Truth -> Rendered Camera Frame -> Simulated Lens Noise/Occlusion
-> OpenCV ArUco Detection -> Detected Pose -> Processing Latency -> Allocator Input

DISCLAIMER: This experiment is a SYNTHETIC-VISION SIMULATION.
No physical cameras, lenses, or robots were used.
All images and detections are synthesized in simulation.
"""

import os
import sys
import math
import json
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import networkx as nx
import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from experiments.plot_style import get_git_commit

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VISION_OUT_DIR = os.path.join(REPO_ROOT, "results", "sitl", "vision")
os.makedirs(VISION_OUT_DIR, exist_ok=True)


class SyntheticVisionSystem:
    """Overhead synthetic camera with ArUco marker tracking, noise, and latency."""

    def __init__(
        self,
        img_width: int = 640,
        img_height: int = 640,
        world_size: float = 100.0,
        pixel_noise_sigma: float = 2.0,
        occlusion_prob: float = 0.05,
        detection_drop_prob: float = 0.03,
        latency_ticks: int = 1,
        seed: Optional[int] = 42,
    ):
        self.w = img_width
        self.h = img_height
        self.world_size = world_size
        self.pixel_noise_sigma = pixel_noise_sigma
        self.occlusion_prob = occlusion_prob
        self.drop_prob = detection_drop_prob
        self.latency_ticks = latency_ticks
        self.rng = np.random.default_rng(seed)

        # ArUco dictionary (4x4, 50 markers)
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.detector_params = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.detector_params)

        # Pre-generate marker templates (IDs 0..7)
        self.marker_templates: Dict[int, np.ndarray] = {}
        for mid in range(8):
            raw_m = cv2.aruco.generateImageMarker(self.aruco_dict, mid, 36)
            # Add white border padding so detector recognizes border
            padded = np.ones((52, 52), dtype=np.uint8) * 255
            padded[8:44, 8:44] = raw_m
            self.marker_templates[mid] = padded

        # Latency buffer: queue of (ready_step, detected_poses)
        self.latency_queue: List[Tuple[int, Dict[int, Tuple[float, float, float]]]] = []

        # Metric logs
        self.total_frames: int = 0
        self.marker_opportunities: int = 0
        self.successful_detections: int = 0
        self.missed_detections: int = 0
        self.occlusion_events: int = 0
        self.position_errors: List[float] = []
        self.orientation_errors: List[float] = []

    def world_to_pixel(self, x: float, y: float) -> Tuple[int, int]:
        """Convert continuous 2D world coordinate [0, world_size] to image pixel (u, v)."""
        u = int(np.clip((x / self.world_size) * (self.w - 1), 0, self.w - 1))
        # Y inverted for image coordinates
        v = int(np.clip(((self.world_size - y) / self.world_size) * (self.h - 1), 0, self.h - 1))
        return u, v

    def pixel_to_world(self, u: float, v: float) -> Tuple[float, float]:
        """Convert image pixel coordinate (u, v) back to continuous world coordinate."""
        x = (u / (self.w - 1)) * self.world_size
        y = ((self.h - 1 - v) / (self.h - 1)) * self.world_size
        return float(x), float(y)

    def render_overhead_frame(
        self,
        robot_poses: Dict[int, Tuple[float, float, float]],
        map_background: Optional[np.ndarray] = None,
    ) -> Tuple[np.ndarray, Dict[int, bool]]:
        """
        Synthesize top-down camera view with ArUco markers on robot chassis.
        Returns (rendered_image, is_occluded_flags).
        """
        if map_background is not None:
            canvas = map_background.copy()
            if canvas.shape[:2] != (self.h, self.w):
                canvas = cv2.resize(canvas, (self.w, self.h))
        else:
            canvas = np.ones((self.h, self.w, 3), dtype=np.uint8) * 230

        is_occluded = {}

        for rid, (rx, ry, ryaw) in robot_poses.items():
            self.marker_opportunities += 1
            cu, cv_px = self.world_to_pixel(rx, ry)

            # Check simulated occlusion
            if float(self.rng.uniform()) < self.occlusion_prob:
                is_occluded[rid] = True
                self.occlusion_events += 1
                # Draw occlusion shadow
                cv2.circle(canvas, (cu, cv_px), 25, (80, 80, 80), -1)
                continue

            is_occluded[rid] = False

            # Draw robot circular base
            cv2.circle(canvas, (cu, cv_px), 24, (200, 120, 50), -1)
            cv2.circle(canvas, (cu, cv_px), 24, (20, 20, 20), 2)

            # Overlay ArUco marker template rotated by ryaw
            marker_img = self.marker_templates.get(rid, self.marker_templates[0])
            mw, mh = marker_img.shape[1], marker_img.shape[0]

            # Rotation matrix for marker
            # In image space, turning CCW from +u toward -v corresponds to turning CCW
            # in world space (from +X toward +Y). OpenCV getRotationMatrix2D rotates CCW
            # for positive angle values, so angle_deg = +math.degrees(ryaw).
            angle_deg = float(math.degrees(ryaw))
            rot_mat = cv2.getRotationMatrix2D((mw / 2.0, mh / 2.0), angle_deg, 1.0)
            rotated_marker = cv2.warpAffine(
                marker_img, rot_mat, (mw, mh), borderMode=cv2.BORDER_CONSTANT, borderValue=255
            )

            # Paste into canvas
            x1 = max(0, cu - mw // 2)
            y1 = max(0, cv_px - mh // 2)
            x2 = min(self.w, x1 + mw)
            y2 = min(self.h, y1 + mh)

            src_x2 = x2 - x1
            src_y2 = y2 - y1

            if src_x2 > 0 and src_y2 > 0:
                marker_bgr = cv2.cvtColor(rotated_marker[:src_y2, :src_x2], cv2.COLOR_GRAY2BGR)
                canvas[y1:y2, x1:x2] = marker_bgr

        # Add camera sensor noise (Gaussian pixel noise)
        noise = self.rng.normal(0, self.pixel_noise_sigma, canvas.shape).astype(np.float32)
        noisy_canvas = np.clip(canvas.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        self.total_frames += 1
        return noisy_canvas, is_occluded

    def detect_and_estimate_poses(
        self,
        frame: np.ndarray,
        ground_truth_poses: Dict[int, Tuple[float, float, float]],
        current_step: int,
    ) -> Tuple[Dict[int, Tuple[float, float, float]], np.ndarray]:
        """
        Run cv2.aruco marker detection on frame and calculate estimated continuous poses.
        Returns (detected_poses, annotated_visualization_frame).
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, rejected = self.detector.detectMarkers(gray)

        detected_poses = {}
        annotated_frame = frame.copy()

        if ids is not None and len(ids) > 0:
            cv2.aruco.drawDetectedMarkers(annotated_frame, corners, ids)
            for idx, mid in enumerate(ids.flatten()):
                # Check simulated detector dropout
                if float(self.rng.uniform()) < self.drop_prob:
                    self.missed_detections += 1
                    continue

                pts = corners[idx][0]  # (4, 2) corners in order: top-left, top-right, bottom-right, bottom-left
                center_u = float(np.mean(pts[:, 0]))
                center_v = float(np.mean(pts[:, 1]))

                est_x, est_y = self.pixel_to_world(center_u, center_v)

                # -------------------------------------------------------------
                # Mathematical Orientation Convention & Flip Ambiguity Resolution:
                # 1. Marker Canonical Frame:
                #    OpenCV ArUco detector orders corners clockwise:
                #      pts[0]: Top-Left,     pts[1]: Top-Right,
                #      pts[2]: Bottom-Right, pts[3]: Bottom-Left.
                #    The internal 4x4 binary payload (DICT_4X4_50) is asymmetric
                #    and rotationally distinct across all four 90-degree rotations.
                #    This eliminates the 180-degree flip ambiguity inherent in
                #    unmarked planar squares.
                # 2. Camera Frame vs World Frame:
                #    Overhead camera frame: +X_cam points right (+u), +Y_cam points down (+v),
                #    with optical axis +Z_cam directed normal to the ground plane.
                #    World frame: +X_world points right, +Y_world points up (+y).
                # 3. Heading (Yaw) Calculation:
                #    Forward orientation vector is defined by the top edge:
                #      v_img = pts[1] - pts[0] = (u_1 - u_0, v_1 - v_0).
                #    Inverting image Y to map to world coordinates:
                #      edge_dx = u_1 - u_0
                #      edge_dy = -(v_1 - v_0)
                #      est_yaw = atan2(edge_dy, edge_dx) in [-pi, pi].
                # -------------------------------------------------------------
                edge_vector_img = pts[1] - pts[0]
                edge_dx = float(edge_vector_img[0])
                edge_dy = -float(edge_vector_img[1])
                est_yaw = float(math.atan2(edge_dy, edge_dx))

                detected_poses[int(mid)] = (est_x, est_y, est_yaw)
                self.successful_detections += 1

                # Calculate error vs ground truth
                if mid in ground_truth_poses:
                    gt_x, gt_y, gt_yaw = ground_truth_poses[mid]
                    pos_err = float(math.hypot(est_x - gt_x, est_y - gt_y))
                    yaw_err = abs((est_yaw - gt_yaw + math.pi) % (2.0 * math.pi) - math.pi)
                    self.position_errors.append(pos_err)
                    self.orientation_errors.append(yaw_err)

                    # Overlay error text
                    cv2.putText(
                        annotated_frame,
                        f"R{mid}: err={pos_err:.2f}m",
                        (int(center_u) + 10, int(center_v) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.42,
                        (0, 0, 255),
                        1,
                    )

        # Buffer into latency queue
        delivery_tick = current_step + self.latency_ticks
        self.latency_queue.append((delivery_tick, detected_poses))

        # Retrieve poses ready after latency delay
        ready_poses = {}
        remaining = []
        for d_tick, poses in self.latency_queue:
            if current_step >= d_tick:
                ready_poses.update(poses)
            else:
                remaining.append((d_tick, poses))
        self.latency_queue = remaining

        # Visual notice banner
        cv2.putText(
            annotated_frame,
            "SYNTHETIC-VISION SIMULATION -- No Physical Camera/Robot",
            (25, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (0, 0, 200),
            2,
        )

        return ready_poses, annotated_frame

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Compute final synthetic vision localization error telemetry."""
        pos_errs = np.array(self.position_errors) if self.position_errors else np.array([0.0])
        yaw_errs = np.array(self.orientation_errors) if self.orientation_errors else np.array([0.0])

        det_rate = (
            float(self.successful_detections / self.marker_opportunities)
            if self.marker_opportunities > 0
            else 0.0
        )
        miss_rate = 1.0 - det_rate

        return {
            "disclaimer": "SYNTHETIC-VISION SIMULATION ONLY -- No physical cameras or robots used.",
            "git_commit": get_git_commit(),
            "total_frames_analyzed": self.total_frames,
            "total_marker_opportunities": self.marker_opportunities,
            "successful_detections": self.successful_detections,
            "detection_rate_pct": float(det_rate * 100.0),
            "missed_marker_rate_pct": float(miss_rate * 100.0),
            "occlusion_events": self.occlusion_events,
            "latency_ticks": self.latency_ticks,
            "position_error_mean_meters": float(np.mean(pos_errs)),
            "position_error_rmse_meters": float(np.sqrt(np.mean(pos_errs**2))),
            "position_error_max_meters": float(np.max(pos_errs)),
            "orientation_error_mean_rad": float(np.mean(yaw_errs)),
            "orientation_error_mean_deg": float(math.degrees(np.mean(yaw_errs))),
            "orientation_error_rmse_rad": float(np.sqrt(np.mean(yaw_errs**2))),
        }


def run_synthetic_vision_experiment(
    graph: nx.Graph,
    n_frames: int = 30,
    seed: int = 42,
    output_video_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute synthetic-vision experiment, recording video and metrics."""
    if output_video_path is None:
        output_video_path = os.path.join(VISION_OUT_DIR, "vision_sim.mp4")

    vision_sys = SyntheticVisionSystem(
        img_width=640,
        img_height=640,
        world_size=100.0,
        pixel_noise_sigma=2.0,
        occlusion_prob=0.05,
        detection_drop_prob=0.03,
        latency_ticks=1,
        seed=seed,
    )

    # Initialize 4 robot trajectories from graph nodes
    rng = np.random.default_rng(seed)
    nodes = list(graph.nodes())
    pos_dict = nx.get_node_attributes(graph, "pos")
    starts = rng.choice(nodes, size=4, replace=False)
    targets = rng.choice([n for n in nodes if n not in starts], size=4, replace=False)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(output_video_path, fourcc, 5.0, (640, 640))

    # Pre-render background map
    bg = np.ones((640, 640, 3), dtype=np.uint8) * 240
    for u, v in graph.edges():
        pu = vision_sys.world_to_pixel(*pos_dict[u])
        pv = vision_sys.world_to_pixel(*pos_dict[v])
        cv2.line(bg, pu, pv, (180, 180, 180), 1)

    curr_poses = {
        i: (float(pos_dict[starts[i]][0]), float(pos_dict[starts[i]][1]), 0.0)
        for i in range(4)
    }

    raw_frame_sample = None
    annotated_sample = None

    for tick in range(n_frames):
        # Move robots slightly toward target
        for i in range(4):
            tgt_pos = pos_dict[targets[i]]
            cx, cy, cyaw = curr_poses[i]
            dx = tgt_pos[0] - cx
            dy = tgt_pos[1] - cy
            dist = math.hypot(dx, dy)
            if dist > 0.5:
                heading = math.atan2(dy, dx)
                step_size = min(1.2, dist)
                nx_pt = cx + step_size * math.cos(heading)
                ny_pt = cy + step_size * math.sin(heading)
                curr_poses[i] = (nx_pt, ny_pt, heading)

        # 1. Synthesize camera frame
        raw_frame, is_occ = vision_sys.render_overhead_frame(curr_poses, map_background=bg)
        if tick == 0:
            raw_frame_sample = raw_frame.copy()

        # 2. Detect markers & estimate poses
        est_poses, annot_frame = vision_sys.detect_and_estimate_poses(raw_frame, curr_poses, tick)
        if tick == 0:
            annotated_sample = annot_frame.copy()

        vw.write(annot_frame)

    vw.release()

    metrics = vision_sys.get_metrics_summary()

    # Save metrics JSON
    json_path = os.path.join(VISION_OUT_DIR, "vision_metrics.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    # Save sample frames
    if raw_frame_sample is not None:
        cv2.imwrite(os.path.join(VISION_OUT_DIR, "sample_raw_frame.png"), raw_frame_sample)
    if annotated_sample is not None:
        cv2.imwrite(os.path.join(VISION_OUT_DIR, "sample_annotated_frame.png"), annotated_sample)

    print(f"Synthetic-vision simulation complete. Video saved to {output_video_path}.")
    print(f"Vision metrics: Detection Rate = {metrics['detection_rate_pct']:.1f}%, Pos RMSE = {metrics['position_error_rmse_meters']:.3f}m")
    return metrics


if __name__ == "__main__":
    from acalib.env.real_maps import generate_real_road_network
    g = generate_real_road_network()
    run_synthetic_vision_experiment(g)
