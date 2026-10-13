"""
Unit tests for SyntheticVisionSystem metrics and grounded perception logic.
Verifies hand-built scenes with known opportunities, occlusions, false positives, and recall calculations.
"""

import math
import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
from experiments.sitl.vision import SyntheticVisionSystem


@pytest.mark.sitl
def test_vision_metrics_grounded_counts():
    """Verify hand-built scene with 4 robots: 1 occluded, 3 visible."""
    vision = SyntheticVisionSystem(
        img_width=640,
        img_height=640,
        world_size=100.0,
        pixel_noise_sigma=0.0,
        occlusion_prob=0.0,  # manually control occlusions
        detection_drop_prob=0.0,
        latency_ticks=0,
        seed=42,
    )

    # 4 robots placed at distinct world positions
    ground_truth = {
        0: (20.0, 20.0, 0.0),
        1: (40.0, 40.0, math.pi / 4),
        2: (60.0, 60.0, math.pi / 2),
        3: (80.0, 80.0, -math.pi / 4),
    }

    # Frame 1: All 4 visible
    frame1, is_occ1 = vision.render_overhead_frame(ground_truth)
    assert vision.total_opportunities == 4
    assert vision.visible_opportunities == 4
    assert vision.occluded_opportunities == 0

    poses1, _ = vision.detect_and_estimate_poses(frame1, ground_truth, current_step=0, is_occluded=is_occ1)
    # OpenCV ArUco should detect all 4 clean markers
    assert len(poses1) == 4
    assert vision.true_positives == 4
    assert vision.false_positives == 0
    assert vision.false_negatives == 0

    # Frame 2: Manually occlude robot 3 by drawing an occlusion patch over it
    # First render with zero auto-occlusion
    frame2, is_occ2 = vision.render_overhead_frame(ground_truth)
    # Manually blackout marker 3
    u3, v3 = vision.world_to_pixel(80.0, 80.0)
    cv2.circle(frame2, (u3, v3), 35, (0, 0, 0), -1)
    is_occ2[3] = True
    vision.occluded_opportunities += 1
    vision.visible_opportunities -= 1

    poses2, _ = vision.detect_and_estimate_poses(frame2, ground_truth, current_step=1, is_occluded=is_occ2)
    # Robot 3 is occluded and not detected, robots 0, 1, 2 detected as TP
    assert 3 not in poses2
    assert vision.true_positives == 7  # 4 from frame1 + 3 from frame2
    assert vision.false_negatives == 0  # Robot 3 was occluded, so NOT counted as false negative!

    summary = vision.get_metrics_summary()
    assert summary["pipeline_mode"] == "OPEN_LOOP_SYNTHETIC_SIMULATION"
    assert summary["allocator_feedback"] is False
    assert summary["total_marker_opportunities"] == 8
    assert summary["occluded_opportunities"] == 1
    assert summary["visible_opportunities"] == 7
    assert summary["true_positives"] == 7
    assert summary["false_positives"] == 0
    assert summary["precision"] == 1.0
    # Recall = 7 TP / 7 visible opportunities = 1.0 (occluded marker 3 excluded from denominator)
    assert summary["recall"] == 1.0


@pytest.mark.sitl
def test_vision_false_positives_and_pose_tolerance():
    """Verify that spurious marker IDs or out-of-tolerance detections count as false positives."""
    vision = SyntheticVisionSystem(
        img_width=640,
        img_height=640,
        world_size=100.0,
        pixel_noise_sigma=0.0,
        occlusion_prob=0.0,
        detection_drop_prob=0.0,
        latency_ticks=0,
        seed=123,
    )

    # Render marker 0 at (30.0, 30.0)
    real_robot = {0: (30.0, 30.0, 0.0)}
    frame, is_occ = vision.render_overhead_frame(real_robot)

    # But provide ground truth with ONLY robot 5 (so marker 0 is an unexpected false positive)
    bogus_gt = {5: (90.0, 90.0, 0.0)}
    poses, _ = vision.detect_and_estimate_poses(frame, bogus_gt, current_step=0, is_occluded=is_occ)

    # Marker 0 was detected, but not in bogus_gt
    assert 0 in poses
    assert vision.false_positives == 1
    assert vision.true_positives == 0
    assert vision.false_negatives == 1  # Robot 5 in GT was not detected

    summary = vision.get_metrics_summary()
    assert summary["false_positives"] == 1
    assert summary["true_positives"] == 0
    assert summary["false_negatives"] == 1
    assert summary["precision"] == 0.0
