"""장비 전환 스케줄링 도메인 모델 + 1시간 step 시뮬레이터.

gym/sb3/DB에 의존하지 않는 순수 코어.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Task:
    plan_prod_key: str
    oper_id: str
    oper_seq: int
    batch_id: str
    plan_qty: int
    init_wip: int


@dataclass
class ProblemInstance:
    rule_timekey: str
    horizon_hours: int
    switch_time_hours: int
    tasks: list[Task]
    _uph: dict[tuple[str, int], float]          # (model, task_index) -> uph
    eqp_qty: dict[str, int]                      # model -> total units
    init_assign: dict[tuple[str, int], int]      # (model, task_index) -> count
    tool_qty: dict[tuple[str, str], int]         # (batch_id, model) -> tools
    conv_groups: dict[str, list[str]]            # group_id -> [batch_id, ...]
    ground_truth: dict = field(default_factory=dict)

    def uph_of(self, model: str, task_index: int) -> float | None:
        return self._uph.get((model, task_index))

    def batch_of(self, task_index: int) -> str:
        return self.tasks[task_index].batch_id

    def conv_group_of(self, batch_id: str) -> str | None:
        for gid, batches in self.conv_groups.items():
            if batch_id in batches:
                return gid
        return None

    def can_convert(self, from_batch: str, to_batch: str) -> bool:
        """conversion 그룹이 같아야 batch 전환 가능."""
        g = self.conv_group_of(from_batch)
        return g is not None and g == self.conv_group_of(to_batch)

    def next_task_index(self, task_index: int) -> int | None:
        """같은 plan_prod_key의 oper_seq+1 태스크 인덱스(없으면 None)."""
        t = self.tasks[task_index]
        for i, o in enumerate(self.tasks):
            if o.plan_prod_key == t.plan_prod_key and o.oper_seq == t.oper_seq + 1:
                return i
        return None

    def models(self) -> list[str]:
        return sorted(self.eqp_qty)


def load_problem(path: str | Path) -> ProblemInstance:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tasks = [
        Task(t["plan_prod_key"], t["oper_id"], int(t["oper_seq"]),
             t["batch_id"], int(t["plan_qty"]), int(t.get("init_wip", 0)))
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
    return ProblemInstance(
        rule_timekey=data["rule_timekey"],
        horizon_hours=int(data["horizon_hours"]),
        switch_time_hours=int(data.get("switch_time_hours", 1)),
        tasks=tasks,
        _uph=uph,
        eqp_qty={k: int(v) for k, v in data["eqp_qty"].items()},
        init_assign=init_assign,
        tool_qty=tool_qty,
        conv_groups={k: list(v) for k, v in data["conv_groups"].items()},
        ground_truth=data.get("ground_truth", {}),
    )
