"""간트 projection 테스트."""
from __future__ import annotations

from dataclasses import replace

from src.utils.json_io import load_problem
from src.utils.rows import build_assign_rows
from src.views.gantt import gantt_rows, gantt_wip_summary
from agents.runner import run_policy
from agents.registry import get_dispatch
from src.simulation.kernel.simulator import Simulator


def test_gantt_wip_summary():
    p = load_problem("data/raw/test/benchmark_01.json")
    rows = gantt_wip_summary(p)
    assert len(rows) == 1
    assert rows[0]["init_wip"] == 1000
    assert rows[0]["plan_qty"] == 300


def test_gantt_idle_segments_when_wip_zero():
    p = load_problem("data/raw/test/benchmark_01.json")
    p.tasks[0] = replace(p.tasks[0], init_wip=0)
    sim = Simulator(p)
    run = run_policy(sim, get_dispatch("heuristic"))
    assign_rows = build_assign_rows(p, run.legacy_hourly_stats, trace=run.legacy_trace)
    segments = gantt_rows(p, assign_rows, run.legacy_trace, run.legacy_hourly_stats)
    idle = [s for s in segments if s["kind"] == "IDLE"]
    assert idle, "WIP=0이면 IDLE 구간이 생성되어야 함"
    assert all(s["idle_reason"] == "WIP_ZERO" for s in idle)


def test_hourly_view_includes_plan():
    from src.views.viewmodel import _hourly_view

    p = load_problem("data/raw/test/benchmark_01.json")
    sim = Simulator(p)
    run = run_policy(sim, get_dispatch("heuristic"))
    hourly = _hourly_view(p, run.legacy_hourly_stats)
    assert len(hourly) == 3
    assert hourly[0]["plan_hourly"] == 100  # 300 / 3h
    assert hourly[-1]["plan_cumulative"] == 300
