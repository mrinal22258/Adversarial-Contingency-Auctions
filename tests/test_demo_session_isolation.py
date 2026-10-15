"""Regression test (AUD-01): graph/layout state must be per-session, not module-global."""
# ruff: noqa: E402

import json
from unittest.mock import MagicMock

import pytest

pytest.importorskip("gradio")
pytestmark = [pytest.mark.ui]

from acalib.demo.ui import callbacks as cb


def _run(map_choice, coarsen):
    return cb.run_sim_action(
        map_choice, coarsen, True, 4, 8,
        cb.ADVERSARY_OPTIONS[0], cb.ALLOCATOR_OPTIONS[0],
        12, "benign (50m, 2% loss)", 50.0, 0.02, 2, 10001,
        progress=MagicMock(),
    )


def test_sessions_do_not_share_graph_state():
    assert not hasattr(cb, "CURRENT_MISSION_GRAPH")
    maps = list(cb.MAP_OPTIONS)
    a = _run(maps[1], "38")
    b = _run(maps[2], "125")  # second "user" runs a different map afterwards
    hist_a, ev_a, env_a = a[0], a[1], a[2]
    assert len(env_a["_graph"]) != len(b[2]["_graph"])

    # User A scrubs after user B ran: must render from A's own graph.
    assert cb.scrub_action(3, hist_a, ev_a, "All", env_a, True)[0] is not None
    assert cb.replay_from_start(hist_a, env_a, True)[1] is not None
    # A session with no stored graph degrades gracefully instead of raising.
    assert cb.scrub_action(3, hist_a, ev_a, "All", {}, True)[0] is None


def test_json_export_excludes_private_graph_state(tmp_path):
    a = _run(list(cb.MAP_OPTIONS)[1], "38")
    path = cb.export_json_action(a[0], a[3], a[2])
    meta = json.load(open(path, encoding="utf-8"))["metadata"]
    assert "_graph" not in meta and "_pos" not in meta
