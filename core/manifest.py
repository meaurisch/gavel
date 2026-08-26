from pydantic import BaseModel


class FileMapping(BaseModel):
    src: str   # relative to methodologies/<id>/
    dest: str  # relative to worktree root


class Source(BaseModel):
    repo: str
    commit: str


class Build(BaseModel):
    """Declares how to regenerate a derived payload (e.g. exported/synthesized
    from another repo) instead of it being authored by hand in place.

    `command` runs from the manifest's own directory (so relative paths like
    `content/.memory` resolve against it); `source_ref` is provenance only —
    a human-readable pointer to what was exported (repo@ref, branch, PR) —
    the command itself is responsible for fetching whatever it needs.
    See scripts/build_repo_context.py.
    """
    command: str
    source_ref: str


class Manifest(BaseModel):
    id: str
    description: str
    source: Source | None = None
    build: Build | None = None
    noop: bool = False
    harnesses: dict[str, list[FileMapping]] = {}
    # Repo-contexts only: empty = applies to all tasks; non-empty = only those task ids.
    # Ignored for methodologies.
    task_affinity: list[str] = []
