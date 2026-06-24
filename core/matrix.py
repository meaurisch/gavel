"""Trial matrix builder — Cartesian product of tasks x methodologies x repo-contexts x models x reps."""

import logging

from core.models import Trial
from core.methodology_loader import load_methodology
from core.repo_context_loader import get_task_affinity, load_repo_context

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
    repo_contexts: list[str],
    models: list[str],
    runner: str,
    reps: int,
    full_matrix: bool = False,
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

    valid_repo_contexts: list[str] = []
    for repo_context_id in repo_contexts:
        try:
            load_repo_context(repo_context_id, harness)
            valid_repo_contexts.append(repo_context_id)
        except (ValueError, FileNotFoundError) as exc:
            logger.warning(
                "Repo context '%s' unusable for harness '%s' — skipping for runner '%s': %s",
                repo_context_id, harness, runner, exc,
            )

    trials: list[Trial] = []
    for task_id in tasks:
        for methodology_id in valid_methodologies:
            for repo_context_id in valid_repo_contexts:
                if not full_matrix:
                    affinity = get_task_affinity(repo_context_id)
                    if affinity and task_id not in affinity:
                        continue
                for model in models:
                    for rep in range(reps):
                        trial_id = f"{task_id}_{methodology_id}_{repo_context_id}_{model}_{runner}_{rep}"
                        trials.append(Trial(
                            id=trial_id,
                            task_id=task_id,
                            methodology_id=methodology_id,
                            repo_context_id=repo_context_id,
                            model=model,
                            runner=runner,
                            rep=rep,
                        ))
    return trials
