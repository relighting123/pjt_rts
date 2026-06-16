"""출력 테이블 계약."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OutputTables:
    assign: list[dict] = field(default_factory=list)
    conv: list[dict] = field(default_factory=list)

    def as_dict(self, assign_key: str, conv_key: str) -> dict[str, list[dict]]:
        return {assign_key: list(self.assign), conv_key: list(self.conv)}
