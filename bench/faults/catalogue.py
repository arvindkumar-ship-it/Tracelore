from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict


class Fault(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    category: str
    injection: dict[str, Any]
    ground_truth_node: str
    signature: dict[str, Any]
    real_fix: dict[str, Any] | None = None
    rag_split: Literal["index", "eval", "control"]


def load_catalogue() -> list[Fault]:
    source = Path(__file__).with_name("catalogue.yaml")
    values = yaml.safe_load(source.read_text())
    faults = [Fault.model_validate(value) for value in values]
    identifiers = [fault.id for fault in faults]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("fault ids must be unique")
    if sum(fault.rag_split != "control" for fault in faults) != 40:
        raise ValueError("the catalogue must contain exactly 40 faults")
    return faults
