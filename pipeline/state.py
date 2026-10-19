import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["pending", "awaiting_approval", "approved", "failed"]
STAGES = ["brief", "prd", "build", "review"]


class RunState(BaseModel):
    run_id: str
    idea: str
    stages: dict[str, Status] = Field(
        default_factory=lambda: {s: "pending" for s in STAGES}
    )


def run_dir(run_id: str, runs_dir: Path = Path("runs")) -> Path:
    return runs_dir / run_id


def save(state: RunState, runs_dir: Path = Path("runs")) -> None:
    d = run_dir(state.run_id, runs_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / "state.json").write_text(state.model_dump_json(indent=2))


def load(run_id: str, runs_dir: Path = Path("runs")) -> RunState:
    text = (run_dir(run_id, runs_dir) / "state.json").read_text()
    return RunState.model_validate_json(text)


def new_run(idea: str, runs_dir: Path = Path("runs")) -> RunState:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    state = RunState(run_id=f"{stamp}-{uuid.uuid4().hex[:4]}", idea=idea)
    save(state, runs_dir)
    return state


def approve(run_id: str, stage: str, runs_dir: Path = Path("runs")) -> RunState:
    state = load(run_id, runs_dir)
    current = state.stages.get(stage)
    if current != "awaiting_approval":
        raise ValueError(f"Stage '{stage}' is '{current}', not awaiting approval")
    state.stages[stage] = "approved"
    save(state, runs_dir)
    return state
