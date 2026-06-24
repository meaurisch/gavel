"""Trial matrix builder — Cartesian product of tasks x methodologies x models x reps."""

import logging

from core.models import Trial
from core.methodology_loader import load_methodology

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
    methodologies: list[str],
    models: list[str],
    runner: str,
    reps: int,
) -> list[Trial]:
    harness = HARNESS_MAP.get(runner, "claude-code")

    valid_methodologies: list[str] = []
    for methodology_id in methodologies:
        try:
            load_methodology(methodology_id, harness)
            valid_methodologies.append(methodology_id)
        except (ValueError, FileNotFoundError) as exc:
            logger.warning(
                "Methodology '%s' unusable for harness '%s' — skipping for runner '%s': %s",
                methodology_id, harness, runner, exc,
            )

    trials: list[Trial] = []
    for task_id in tasks:
        for methodology_id in valid_methodologies:
            for model in models:
                for rep in range(reps):
                    trial_id = f"{task_id}_{methodology_id}_{model}_{runner}_{rep}"
                    trials.append(Trial(
                        id=trial_id,
                        task_id=task_id,
                        methodology_id=methodology_id,
                        model=model,
                        runner=runner,
                        rep=rep,
                    ))
    return trials
