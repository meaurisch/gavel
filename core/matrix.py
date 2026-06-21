"""Trial matrix builder — Cartesian product of tasks x setups x models x reps."""

import logging

from core.models import Trial
from core.setup_loader import load_setup

logger = logging.getLogger(__name__)

HARNESS_MAP: dict[str, str] = {
    "claude-code": "claude-code",
    "copilot-cli": "copilot",
    "oracle": "claude-code",
    "nop": "claude-code",
    "manual": "claude-code",
}


def expand(
    tasks: list[str],
    setups: list[str],
    models: list[str],
    runner: str,
    reps: int,
) -> list[Trial]:
    harness = HARNESS_MAP.get(runner, "claude-code")

    valid_setups: list[str] = []
    for setup_id in setups:
        try:
            load_setup(setup_id, harness)
            valid_setups.append(setup_id)
        except (ValueError, FileNotFoundError) as exc:
            logger.warning(
                "Setup '%s' unusable for harness '%s' — skipping for runner '%s': %s",
                setup_id, harness, runner, exc,
            )

    trials: list[Trial] = []
    for task_id in tasks:
        for setup_id in valid_setups:
            for model in models:
                for rep in range(reps):
                    trial_id = f"{task_id}_{setup_id}_{model}_{runner}_{rep}"
                    trials.append(Trial(
                        id=trial_id,
                        task_id=task_id,
                        setup_id=setup_id,
                        model=model,
                        runner=runner,
                        rep=rep,
                    ))
    return trials
