"""순수 도메인 모델 — 외부 프레임워크 의존 없음."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple


class Move(NamedTuple):
    model: str
    from_index: int
    to_index: int


@dataclass(frozen=True)
class Equipment:
    """실제 장비 호기 1대 — 모델/호기ID/현재 BATCH_ID/PLAN_PROD_KEY(/OPER_ID)."""
    eqp_id: str
    eqp_model: str
    batch_id: str = ""
    plan_prod_key: str = ""
    oper_id: str = ""


def largest_remainder(fracs: list[float], total: int) -> list[int]:
    """비례 실수 배분 → 정수. 합계 = total (최대잉여법)."""
    floors = [int(f) for f in fracs]
    remainders = [(fracs[i] - floors[i], i) for i in range(len(fracs))]
    deficit = total - sum(floors)
    remainders.sort(reverse=True)
    for k in range(max(0, deficit)):
        floors[remainders[k][1]] += 1
    return floors


@dataclass(frozen=True)
class Task:
    plan_prod_key: str
    oper_id: str
    oper_seq: int
    batch_id: str
    plan_qty: int
    init_wip: int
    equip_batch_id: str = ""

    @property
    def wip_qty(self) -> int:
        return self.init_wip

    def allocation_batch_id(self) -> str:
        """RTS_EQPALLOCATION 등 장비(UPH) 기준 BATCH_ID."""
        return self.equip_batch_id or self.batch_id


@dataclass
class ProblemInstance:
    rule_timekey: str
    horizon_hours: int
    switch_time_hours: int
    tasks: list[Task]
    _uph: dict[tuple[str, int], float]
    eqp_qty: dict[str, int]
    init_assign: dict[tuple[str, int], int]
    tool_qty: dict[tuple[str, str], int]
    conv_groups: dict[str, list[str]]
    facid: str | None = None
    equipments: list[Equipment] = field(default_factory=list)
    ground_truth: dict = field(default_factory=dict)

    def uph_of(self, model: str, task_index: int) -> float | None:
        return self._uph.get((model, task_index))

    def batch_of(self, task_index: int) -> str:
        return self.tasks[task_index].batch_id

    def lot_cd_of(self, batch_id: str) -> str:
        from src.db.eqpconvplan import split_batch_lot_temper
        lot, _ = split_batch_lot_temper(batch_id)
        return lot

    def tool_cap(self, batch_id: str, model: str) -> int:
        return self.tool_qty.get((self.lot_cd_of(batch_id), model), 0)

    def conv_group_of(self, batch_id: str) -> str | None:
        for gid, batches in self.conv_groups.items():
            if batch_id in batches:
                return gid
        return None

    def can_convert(self, from_batch: str, to_batch: str) -> bool:
        g = self.conv_group_of(from_batch)
        return g is not None and g == self.conv_group_of(to_batch)

    def next_task_index(self, task_index: int) -> int | None:
        t = self.tasks[task_index]
        for i, o in enumerate(self.tasks):
            if o.plan_prod_key == t.plan_prod_key and o.oper_seq == t.oper_seq + 1:
                return i
        return None

    def prev_task_index(self, task_index: int) -> int | None:
        t = self.tasks[task_index]
        for i, o in enumerate(self.tasks):
            if o.plan_prod_key == t.plan_prod_key and o.oper_seq == t.oper_seq - 1:
                return i
        return None

    def complete_guide_allocation(
        self, guide: dict[tuple[str, int], float | int],
    ) -> dict[tuple[str, int], int]:
        result: dict[tuple[str, int], int] = {}
        for model in self.models():
            for ti in range(len(self.tasks)):
                if self.uph_of(model, ti) is not None:
                    result[(model, ti)] = int(guide.get((model, ti), 0))
        return result

    def plan_target_allocation(self) -> dict[tuple[str, int], float]:
        result: dict[tuple[str, int], float] = {}
        for model in self.models():
            weights = {
                ti: t.plan_qty / uph
                for ti, t in enumerate(self.tasks)
                if (uph := self.uph_of(model, ti)) and uph > 0
            }
            total_w = sum(weights.values())
            if total_w <= 0:
                continue
            eqp = float(self.eqp_qty[model])
            for ti, w in weights.items():
                result[(model, ti)] = w / total_w * eqp
        return result

    def plan_target_allocation_int(self) -> dict[tuple[str, int], int]:
        raw = self.plan_target_allocation()
        result: dict[tuple[str, int], int] = {}
        for model in self.models():
            tasks = [ti for ti in range(len(self.tasks)) if self.uph_of(model, ti) is not None]
            if not tasks:
                continue
            fracs = [raw.get((model, ti), 0.0) for ti in tasks]
            counts = largest_remainder(fracs, self.eqp_qty[model])
            for ti, cnt in zip(tasks, counts):
                result[(model, ti)] = cnt
        return result

    def models(self) -> list[str]:
        return sorted(self.eqp_qty)
