"""JSON 스냅샷 → ProblemInstance."""
from __future__ import annotations

import json
from pathlib import Path

import config
from src.simulation.domain.problem import Equipment, ProblemInstance, Task


def _task_wip_qty(task_data: dict) -> int:
    if "wip_qty" in task_data:
        return int(task_data["wip_qty"])
    return int(task_data.get("init_wip", 0))


def load_problem(path: str | Path) -> ProblemInstance:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tasks = [
        Task(t["plan_prod_key"], t["oper_id"], int(t["oper_seq"]),
             t["batch_id"], int(t["plan_qty"]), _task_wip_qty(t))
        for t in data["tasks"]
    ]

    def task_index(ppk: str, oper: str) -> int:
        for i, t in enumerate(tasks):
            if t.plan_prod_key == ppk and t.oper_id == oper:
                return i
        raise KeyError(f"task not found: {ppk}/{oper}")

    uph = {
        (u["eqp_model"], task_index(u["plan_prod_key"], u["oper_id"])): float(u["uph"])
        for u in data["uph"] if float(u["uph"]) > 0
    }
    init_assign = {
        (a["eqp_model"], task_index(a["plan_prod_key"], a["oper_id"])): int(a["count"])
        for a in data["init_assign"]
    }
    tool_qty = {(t["batch_id"], t["eqp_model"]): int(t["tool_qty"]) for t in data["tool_qty"]}
    equipments = [
        Equipment(
            eqp_id=str(e["eqp_id"]),
            eqp_model=str(e["eqp_model"]),
            batch_id=str(e.get("batch_id", "")),
            plan_prod_key=str(e.get("plan_prod_key", "")),
            oper_id=str(e.get("oper_id", "")),
        )
        for e in data.get("equipments", [])
    ]
    return ProblemInstance(
        rule_timekey=data["rule_timekey"],
        horizon_hours=int(data["horizon_hours"]),
        switch_time_hours=int(data.get("switch_time_hours", 1)),
        tasks=tasks,
        _uph=uph,
        eqp_qty={k: int(v) for k, v in data["eqp_qty"].items()},
        init_assign=init_assign,
        tool_qty=tool_qty,
        conv_groups=config.load_conv_groups(),
        facid=data.get("facid") or data.get("fac_id"),
        equipments=equipments,
        ground_truth=data.get("ground_truth", {}),
    )


def problem_to_dict(problem: ProblemInstance, include_ground_truth: bool = True) -> dict:
    tasks = [
        {
            "plan_prod_key": t.plan_prod_key,
            "oper_id": t.oper_id,
            "oper_seq": t.oper_seq,
            "batch_id": t.batch_id,
            "plan_qty": t.plan_qty,
            "wip_qty": t.wip_qty,
            "init_wip": t.init_wip,
        }
        for t in problem.tasks
    ]
    uph = []
    for (model, ti), val in sorted(problem._uph.items()):
        t = problem.tasks[ti]
        uph.append({
            "plan_prod_key": t.plan_prod_key,
            "oper_id": t.oper_id,
            "eqp_model": model,
            "uph": val,
        })
    init_assign = []
    for (model, ti), cnt in sorted(problem.init_assign.items()):
        t = problem.tasks[ti]
        init_assign.append({
            "eqp_model": model,
            "plan_prod_key": t.plan_prod_key,
            "oper_id": t.oper_id,
            "count": cnt,
        })
    tool_qty = [
        {"batch_id": b, "eqp_model": m, "tool_qty": q}
        for (b, m), q in sorted(problem.tool_qty.items())
    ]
    data = {
        "rule_timekey": problem.rule_timekey,
        "horizon_hours": problem.horizon_hours,
        "switch_time_hours": problem.switch_time_hours,
        "tasks": tasks,
        "uph": uph,
        "eqp_qty": dict(problem.eqp_qty),
        "init_assign": init_assign,
        "tool_qty": tool_qty,
    }
    if problem.facid:
        data["facid"] = problem.facid
    if problem.equipments:
        data["equipments"] = [
            {
                "eqp_id": e.eqp_id,
                "eqp_model": e.eqp_model,
                "batch_id": e.batch_id,
                "plan_prod_key": e.plan_prod_key,
                "oper_id": e.oper_id,
            }
            for e in problem.equipments
        ]
    if include_ground_truth and problem.ground_truth:
        data["ground_truth"] = problem.ground_truth
    return data


def save_problem(problem: ProblemInstance, path: str | Path,
                 include_ground_truth: bool = True) -> Path:
    path = config.replace_file(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(problem_to_dict(problem, include_ground_truth), indent=2, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")
    return path
