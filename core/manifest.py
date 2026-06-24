from pydantic import BaseModel


class FileMapping(BaseModel):
    src: str   # relative to methodologies/<id>/
    dest: str  # relative to worktree root


class Source(BaseModel):
    repo: str
    commit: str


class Manifest(BaseModel):
    id: str
    description: str
    source: Source | None = None
    noop: bool = False
    harnesses: dict[str, list[FileMapping]] = {}
    # Repo-contexts only: empty = applies to all tasks; non-empty = only those task ids.
    # Ignored for methodologies.
    task_affinity: list[str] = []
