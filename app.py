"""
Adversarial Contingency Auctions (ACA) — Mission Control Explorer.

Provides:
1. Interactive Gradio Mission Control dashboard mounted at `/`
2. Live simulation and paired comparison API endpoints at `/api/...`
3. Structured JSON/CSV exports from live simulation telemetry
"""
# ruff: noqa: E402

import os
import sys
import json
import time
import asyncio
import logging
import collections
import threading
import uuid
from typing import Dict, Any, List, Literal, Optional

# Ensure repository root is in sys.path
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import networkx as nx
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator
import uvicorn
import gradio as gr

from acalib import __version__, PROTOCOL_FULL_NAME, PROTOCOL_LABEL, PROTOCOL_VERSION
from acalib.demo.ui.styles import MISSION_CONTROL_CSS
from acalib.demo.ui.layout import build_app
from acalib.demo.ui.callbacks import (
    run_simulation_wrapper,
    plot_simulation_state,
    get_metrics_table,
)
from acalib.demo.runner import (
    run_single_simulation,
    run_paired_comparison,
    run_20_seeds_paired,
)
from acalib.demo.narrate import generate_event_log

__all__ = [
    "app",
    "run_simulation_wrapper",
    "plot_simulation_state",
    "get_metrics_table",
]

logger = logging.getLogger("aca.api")

# Canonical Gradio Blocks instance
demo = build_app()
demo.queue(default_concurrency_limit=10)

app = FastAPI(
    title="Adversarial Contingency Auctions (ACA) — Mission Control",
    description="Strategic Multi-Robot Task Allocation under Inconsistent Beliefs and Adversarial Path Blockages",
    version=__version__,
)

# CORS configuration (P1)
allowed_origins_env = os.environ.get("ACA_CORS_ORIGINS", "")
if allowed_origins_env:
    allowed_origins = [orig.strip() for orig in allowed_origins_env.split(",") if orig.strip()]
else:
    allowed_origins = [
        "http://localhost:7860",
        "http://127.0.0.1:7860",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


MAX_BODY_SIZE = 1_048_576  # 1 MiB


class SecurityAndSizeMiddleware:
    """Enforce body payload size cap and standard security headers (P4, F-25)."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        cl_raw = headers.get(b"content-length")
        security_headers = [
            (b"x-content-type-options", b"nosniff"),
            (b"x-frame-options", b"DENY"),
        ]

        async def send_error_response(status_code: int, detail: str):
            body = json.dumps({"detail": detail}).encode("utf-8")
            resp_headers = list(security_headers) + [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ]
            await send({
                "type": "http.response.start",
                "status": status_code,
                "headers": resp_headers,
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })

        if cl_raw is not None:
            try:
                cl = int(cl_raw.decode("latin1"))
                if cl < 0:
                    await send_error_response(400, "Invalid Content-Length header.")
                    return
                if cl > MAX_BODY_SIZE:
                    await send_error_response(413, "Request payload exceeds 1MB limit.")
                    return
            except ValueError:
                await send_error_response(400, "Malformed Content-Length header.")
                return

        # Read and buffer request body chunks up to MAX_BODY_SIZE + 1
        body_chunks = []
        total_bytes = 0
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                total_bytes += len(chunk)
                if total_bytes > MAX_BODY_SIZE:
                    await send_error_response(413, "Request payload exceeds 1MB limit.")
                    return
                body_chunks.append(message)
                more_body = message.get("more_body", False)
            elif message["type"] == "http.disconnect":
                return
            else:
                body_chunks.append(message)
                break

        # Replay buffered messages to downstream handlers
        idx = 0
        async def replay_receive():
            nonlocal idx
            if idx < len(body_chunks):
                msg = body_chunks[idx]
                idx += 1
                return msg
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                resp_headers = list(message.get("headers", []))
                existing = {h[0].lower() for h in resp_headers}
                if b"x-content-type-options" not in existing:
                    resp_headers.append((b"x-content-type-options", b"nosniff"))
                if b"x-frame-options" not in existing:
                    resp_headers.append((b"x-frame-options", b"DENY"))
                message = dict(message)
                message["headers"] = resp_headers
            await send(message)

        await self.app(scope, replay_receive, send_wrapper)


app.add_middleware(SecurityAndSizeMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler preventing stack traces in HTTP responses (P4)."""
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )
    logger.error("Unhandled exception processing %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Consult system logs for details."},
    )


class IPRateLimiter:
    """Sliding-window per-IP rate limiter (F-25)."""

    def __init__(self, default_limit: int = 60):
        self._lock = threading.Lock()
        self._records: Dict[str, List[float]] = collections.defaultdict(list)
        self.default_limit = default_limit

    def get_limit(self) -> int:
        val = os.environ.get("ACA_RATE_LIMIT_PER_MIN")
        if val is not None:
            try:
                return int(val)
            except ValueError:
                pass
        return self.default_limit

    def check_rate_limit(self, client_ip: str) -> None:
        limit = self.get_limit()
        if limit <= 0:
            return

        now = time.time()
        cutoff = now - 60.0

        with self._lock:
            timestamps = self._records[client_ip]
            valid = [t for t in timestamps if t > cutoff]
            if len(valid) >= limit:
                retry_after = int(max(1, 60.0 - (now - valid[0])))
                self._records[client_ip] = valid
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit of {limit} requests per minute exceeded.",
                    headers={"Retry-After": str(retry_after)},
                )
            valid.append(now)
            self._records[client_ip] = valid

    def reset(self):
        with self._lock:
            self._records.clear()


class ConcurrencyLimiter:
    """Bounded concurrency semaphore for heavy simulation endpoints (F-25)."""

    def __init__(self):
        self._sem: Optional[asyncio.Semaphore] = None
        self._max: Optional[int] = None

    def get_semaphore(self) -> asyncio.Semaphore:
        max_sims = int(os.environ.get("ACA_MAX_CONCURRENT_SIMS", "4"))
        if self._sem is None or self._max != max_sims:
            self._max = max_sims
            self._sem = asyncio.Semaphore(max_sims)
        return self._sem

    async def acquire_slot(self) -> asyncio.Semaphore:
        sem = self.get_semaphore()
        if sem._value <= 0:
            raise HTTPException(
                status_code=429,
                detail="Maximum concurrent simulations reached; please retry shortly.",
                headers={"Retry-After": "2"},
            )
        await sem.acquire()
        return sem


_RATE_LIMITER = IPRateLimiter()
_CONCURRENCY_LIMITER = ConcurrencyLimiter()


@app.get("/api/health")
async def api_health():
    """Healthcheck endpoint for orchestrators and container probes (P3)."""
    return {"status": "healthy", "service": "aca-mission-control"}


@app.get("/api/version")
async def api_version():
    """Version and provenance inspection endpoint (P3)."""
    git_info = None
    try:
        from acalib.utils.gitinfo import get_git_info
        info = get_git_info(REPO_ROOT)
        git_info = {
            "commit": info.commit,
            "is_dirty": info.is_dirty,
            "source": info.source,
        }
    except Exception:
        pass
    return {
        "version": __version__,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_label": PROTOCOL_LABEL,
        "protocol_full_name": PROTOCOL_FULL_NAME,
        "git": git_info,
    }


# Mount static directory for repository images, diagrams, and assets
static_dir = os.path.join(REPO_ROOT, "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Thread-safe in-memory storage for real simulation runs (F-04)
class RunStore:
    """Thread-safe in-memory store for simulation telemetry runs."""

    def __init__(self, maxsize: int = 32):
        self._lock = threading.Lock()
        self._runs: Dict[str, Dict[str, Any]] = {}
        self._latest_id: Optional[str] = None
        self._maxsize = maxsize

    def set_run(self, run_data: Dict[str, Any]) -> str:
        run_id = str(uuid.uuid4())
        if "metadata" in run_data and isinstance(run_data["metadata"], dict):
            run_data["metadata"]["run_id"] = run_id
        with self._lock:
            self._runs[run_id] = run_data
            self._latest_id = run_id
            if len(self._runs) > self._maxsize:
                oldest_id = next(iter(self._runs))
                del self._runs[oldest_id]
        return run_id

    def get_run(self, run_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._lock:
            target_id = run_id if run_id is not None else self._latest_id
            if target_id is None or target_id not in self._runs:
                return None
            return self._runs[target_id]

    def has_runs(self) -> bool:
        with self._lock:
            return self._latest_id is not None

    def clear(self):
        with self._lock:
            self._runs.clear()
            self._latest_id = None


_RUN_STORE = RunStore()
_LAST_RUN: Dict[str, Any] = {}


class SimulateRequest(BaseModel):
    topology: Literal["boston", "warehouse_small", "warehouse_large"] = "boston"
    allocator: str = Field(default="ACA (Ours)", max_length=100)
    adversary: str = Field(default="Reactive (Corridor Interdiction)", max_length=100)
    numRobots: int = Field(default=4, ge=1, le=20)
    numTasks: int = Field(default=15, ge=1, le=100)
    seed: int = Field(default=10001, ge=0)
    maxSteps: int = Field(default=80, ge=10, le=500)
    depth: int = Field(default=1, ge=0, le=3)
    commRange: float = Field(default=50.0, ge=0.0, le=500.0)
    pDrop: float = Field(default=0.02, ge=0.0, le=1.0)
    blockedEdges: Optional[List[Any]] = None

    @field_validator("blockedEdges")
    @classmethod
    def validate_blocked_edges(cls, v):
        if v is None:
            return v
        if not isinstance(v, list):
            raise ValueError("blockedEdges must be a list of edges")
        cleaned = []
        for item in v:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise ValueError(f"Each blocked edge must be a list or tuple of length 2, got {item}")
            u, w = item
            if type(u) is not int or type(w) is not int:
                raise ValueError(f"Edge nodes must be strict integers, got {item}")
            cleaned.append([u, w])
        return cleaned


class CompareRequest(BaseModel):
    topology: Literal["boston", "warehouse_small", "warehouse_large"] = "boston"
    allocator: str = Field(default="ACA (Ours)", max_length=100)
    adversary: str = Field(default="Reactive (Corridor Interdiction)", max_length=100)
    numRobots: int = Field(default=4, ge=1, le=20)
    numTasks: int = Field(default=15, ge=1, le=100)
    seed: int = Field(default=10001, ge=0)
    maxSteps: int = Field(default=80, ge=10, le=500)
    depth: int = Field(default=1, ge=0, le=3)
    commRange: float = Field(default=50.0, ge=0.0, le=500.0)
    pDrop: float = Field(default=0.02, ge=0.0, le=1.0)


class MonteCarloRequest(BaseModel):
    topology: Literal["boston", "warehouse_small", "warehouse_large"] = "boston"
    allocator: str = Field(default="ACA (Ours)", max_length=100)
    adversary: str = Field(default="Reactive (Corridor Interdiction)", max_length=100)
    numRobots: int = Field(default=4, ge=1, le=20)
    numTasks: int = Field(default=15, ge=1, le=100)
    numTrials: int = Field(default=20, ge=1, le=50)
    seedBase: int = Field(default=10001, ge=0)
    maxSteps: int = Field(default=80, ge=10, le=500)
    commRange: float = Field(default=50.0, ge=0.0, le=500.0)
    pDrop: float = Field(default=0.02, ge=0.0, le=1.0)


@app.get("/hud", include_in_schema=False)
async def redirect_hud():
    """Redirect legacy /hud route to main simulator interface."""
    return RedirectResponse(url="/", status_code=307)


def _execute_simulation(req: SimulateRequest) -> Dict[str, Any]:
    global _LAST_RUN

    if req.topology == "boston":
        fam, nodes, variant = "road_osmnx", 216, "none"
    elif req.topology == "warehouse_small":
        fam, nodes, variant = "warehouse_movingai", 38, "10-20-10-2-1"
    else:
        fam, nodes, variant = "warehouse_movingai", 125, "20-40-10-2-1"

    custom_blocked = [tuple(e) for e in req.blockedEdges] if req.blockedEdges else None
    prebuilt_env = None
    if custom_blocked:
        from experiments.run_sweep import build_crn_environment
        prebuilt_env = build_crn_environment(
            graph_family=fam,
            n_nodes=nodes,
            seed=req.seed,
            n_robots=req.numRobots,
            n_tasks=req.numTasks,
            max_steps=req.maxSteps,
            variant=variant,
        )
        topo_graph = prebuilt_env["graph"]
        for u, v in custom_blocked:
            if u not in topo_graph or v not in topo_graph or not topo_graph.has_edge(u, v):
                raise HTTPException(
                    status_code=422,
                    detail=f"Blocked edge ({u}, {v}) does not exist in topology '{req.topology}'."
                )

    res = run_single_simulation(
        graph_family=fam,
        n_nodes=nodes,
        adversary_str=req.adversary,
        allocator_str=req.allocator,
        n_robots=req.numRobots,
        n_tasks=req.numTasks,
        seed=req.seed,
        max_steps=req.maxSteps,
        contingency_depth=req.depth,
        comm_range=req.commRange,
        p_drop=req.pDrop,
        variant=variant,
        prebuilt_env=prebuilt_env,
        custom_blocked_edges=custom_blocked,
        record_history=True,
    )

    summary = res["summary"]
    history = res["history"]
    graph = res["graph"]

    raw_pos = nx.get_node_attributes(graph, "pos")
    nodes_list = []
    if raw_pos:
        xs = [p[0] for p in raw_pos.values()]
        ys = [p[1] for p in raw_pos.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(1e-5, max_x - min_x)
        span_y = max(1e-5, max_y - min_y)

        for nid in graph.nodes():
            p = raw_pos.get(nid, (0, 0))
            nx_norm = (p[0] - min_x) / span_x - 0.5
            ny_norm = (p[1] - min_y) / span_y - 0.5
            nodes_list.append({
                "id": nid,
                "x": nx_norm * 920,
                "y": ny_norm * 560,
            })

    edges_list = [[u, v] for u, v in graph.edges()]
    final_frame = history[-1] if history else {}
    blocked_edges = final_frame.get("blocked_edges", [])
    active_detour_edges = final_frame.get("active_detours", [])
    narrative_events = generate_event_log(history)

    result_data = {
        "status": "ok",
        "summary": summary,
        "nodes": nodes_list,
        "edges": edges_list,
        "blocked_edges": blocked_edges,
        "detour_edges": active_detour_edges,
        "events": narrative_events,
        "max_ticks": len(history),
    }

    run_snapshot = {
        "metadata": {
            "application": "ACA Mission Control",
            "protocol": PROTOCOL_FULL_NAME,
            "topology": req.topology,
            "allocator": req.allocator,
            "adversary": req.adversary,
            "numRobots": req.numRobots,
            "numTasks": req.numTasks,
            "seed": req.seed,
            "maxSteps": req.maxSteps,
        },
        "summary": summary,
        "history": history,
    }
    run_id = _RUN_STORE.set_run(run_snapshot)
    _LAST_RUN = run_snapshot
    result_data["run_id"] = run_id

    return result_data


@app.post("/api/simulate")
async def api_simulate(req: SimulateRequest, request: Request):
    """Execute high-fidelity simulation engine and return structured JSON."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    _RATE_LIMITER.check_rate_limit(client_ip)
    sem = await _CONCURRENCY_LIMITER.acquire_slot()
    try:
        return await run_in_threadpool(_execute_simulation, req)
    finally:
        sem.release()


def _execute_compare(req: CompareRequest) -> Dict[str, Any]:
    if req.topology == "boston":
        fam, nodes, variant = "road_osmnx", 216, "none"
    elif req.topology == "warehouse_small":
        fam, nodes, variant = "warehouse_movingai", 38, "10-20-10-2-1"
    else:
        fam, nodes, variant = "warehouse_movingai", 125, "20-40-10-2-1"

    comp_res = run_paired_comparison(
        graph_family=fam,
        n_nodes=nodes,
        adversary_str=req.adversary,
        selected_allocator_str=req.allocator,
        comm_range=req.commRange,
        p_drop=req.pDrop,
        n_robots=req.numRobots,
        n_tasks=req.numTasks,
        seed=req.seed,
        max_steps=req.maxSteps,
        contingency_depth=req.depth,
        variant=variant,
    )

    s_sel = comp_res["selected"]["summary"]
    s_lr = comp_res["cbba_partial_lr"]["summary"]
    s_cbba = comp_res["cbba"]["summary"]
    s_ctp = comp_res["ctp_replan"]["summary"]

    table = [
        {"metric": "Completion Rate (%)", "selected": f"{s_sel.get('completion_rate_pct', 0.0):.1f}%", "cbba_lr": f"{s_lr.get('completion_rate_pct', 0.0):.1f}%", "cbba": f"{s_cbba.get('completion_rate_pct', 0.0):.1f}%", "ctp": f"{s_ctp.get('completion_rate_pct', 0.0):.1f}%"},
        {"metric": "Completed Tasks", "selected": f"{s_sel.get('completed_tasks', 0)}/{req.numTasks}", "cbba_lr": f"{s_lr.get('completed_tasks', 0)}/{req.numTasks}", "cbba": f"{s_cbba.get('completed_tasks', 0)}/{req.numTasks}", "ctp": f"{s_ctp.get('completed_tasks', 0)}/{req.numTasks}"},
        {"metric": "Cumulative Conflicts", "selected": str(s_sel.get('total_conflicts', 0)), "cbba_lr": str(s_lr.get('total_conflicts', 0)), "cbba": str(s_cbba.get('total_conflicts', 0)), "ctp": str(s_ctp.get('total_conflicts', 0))},
        {"metric": "Total Messages", "selected": str(s_sel.get('total_messages', 0)), "cbba_lr": str(s_lr.get('total_messages', 0)), "cbba": str(s_cbba.get('total_messages', 0)), "ctp": str(s_ctp.get('total_messages', 0))},
        {"metric": "Total Travel Distance", "selected": f"{s_sel.get('total_travel_distance', 0.0):.1f}", "cbba_lr": f"{s_lr.get('total_travel_distance', 0.0):.1f}", "cbba": f"{s_cbba.get('total_travel_distance', 0.0):.1f}", "ctp": f"{s_ctp.get('total_travel_distance', 0.0):.1f}"},
        {"metric": "Net Welfare", "selected": f"{s_sel.get('net_welfare', 0.0):.1f}", "cbba_lr": f"{s_lr.get('net_welfare', 0.0):.1f}", "cbba": f"{s_cbba.get('net_welfare', 0.0):.1f}", "ctp": f"{s_ctp.get('net_welfare', 0.0):.1f}"},
    ]

    return {"status": "ok", "table": table}


@app.post("/api/compare")
async def api_compare(req: CompareRequest, request: Request):
    """Run paired comparison across ACA and baselines under identical CRN environment."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    _RATE_LIMITER.check_rate_limit(client_ip)
    sem = await _CONCURRENCY_LIMITER.acquire_slot()
    try:
        return await run_in_threadpool(_execute_compare, req)
    finally:
        sem.release()


def _execute_monte_carlo(req: MonteCarloRequest) -> Dict[str, Any]:
    fam = "road_osmnx" if req.topology == "boston" else "warehouse_movingai"
    nodes = 216 if req.topology == "boston" else (38 if req.topology == "warehouse_small" else 125)
    variant = "none" if req.topology == "boston" else ("10-20-10-2-1" if req.topology == "warehouse_small" else "20-40-10-2-1")

    mc_res = run_20_seeds_paired(
        graph_family=fam,
        n_nodes=nodes,
        adversary_str=req.adversary,
        allocator_str=req.allocator,
        comm_range=req.commRange,
        p_drop=req.pDrop,
        n_robots=req.numRobots,
        n_tasks=req.numTasks,
        max_steps=req.maxSteps,
        variant=variant,
        seed_start=req.seedBase,
        num_seeds=req.numTrials,
    )

    comparisons_table = mc_res.get("comparisons_table")
    table_records = []
    if isinstance(comparisons_table, pd.DataFrame):
        table_records = comparisons_table.to_dict(orient="records")
    elif isinstance(comparisons_table, list):
        table_records = comparisons_table

    summary = {
        "n_seeds": mc_res.get("n_seeds", req.numTrials),
        "main_method": mc_res.get("main_method", req.allocator),
        "main_completion": mc_res.get("main_completion", "0.0%"),
        "verdict": mc_res.get("verdict", ""),
        "comparisons": table_records,
    }

    return {"status": "ok", "summary": summary}


@app.post("/api/monte_carlo")
async def api_monte_carlo(req: MonteCarloRequest, request: Request):
    """Run 20-seed Monte Carlo sweep under Common Random Numbers."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    _RATE_LIMITER.check_rate_limit(client_ip)
    sem = await _CONCURRENCY_LIMITER.acquire_slot()
    try:
        return await run_in_threadpool(_execute_monte_carlo, req)
    finally:
        sem.release()


@app.get("/api/export_json")
async def api_export_json(run_id: Optional[str] = None):
    """Download full simulation telemetry run as JSON from the latest or specified run_id."""
    run = _RUN_STORE.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail="No simulation has been run; POST /api/simulate first",
        )

    payload = {
        "metadata": run.get("metadata", {}),
        "summary": run.get("summary", {}),
        "history": run.get("history", []),
    }
    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=aca_telemetry_run.json"},
    )


@app.get("/api/export_csv")
async def api_export_csv(run_id: Optional[str] = None):
    """Download tick-level simulation metrics log as CSV from the latest or specified run_id."""
    run = _RUN_STORE.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail="No simulation has been run; POST /api/simulate first",
        )

    history = run.get("history", [])
    csv_rows = ["tick,completed_tasks,conflicts,messages,travel,welfare,safe_claims,deferred_claims,reauction_events"]
    for step in history:
        csv_rows.append(
            f"{step.get('tick', 0)},"
            f"{step.get('completed_tasks', 0)},"
            f"{step.get('conflicts', 0)},"
            f"{step.get('messages', 0)},"
            f"{step.get('travel', 0.0):.2f},"
            f"{step.get('welfare', 0.0):.2f},"
            f"{step.get('safe_claims', 0)},"
            f"{step.get('deferred_claims', 0)},"
            f"{step.get('reauction_events', 0)}"
        )
    csv_text = "\n".join(csv_rows) + "\n"
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=aca_telemetry_ticks.csv"},
    )


# Mount Gradio Blocks interface at / with full Clash HUD theme and CSS
app = gr.mount_gradio_app(
    app,
    demo,
    path="/",
    theme=getattr(demo, "theme", None),
    head=f"""
    <link href="https://fonts.googleapis.com/css?family=Google+Sans|Noto+Sans|Castoro" rel="stylesheet">
    <style id="clash-hud-theme">
    {MISSION_CONTROL_CSS}
    </style>
    """,
)

if __name__ == "__main__":
    server_port = int(os.environ.get("PORT", 7860))
    server_name = os.environ.get("HOST", os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1"))
    print(f"[*] Starting ACA Mission Control on {server_name}:{server_port}...")
    print(f"[*] Dashboard Viewport: http://{server_name}:{server_port}/")
    uvicorn.run(app, host=server_name, port=server_port, log_level="info")
