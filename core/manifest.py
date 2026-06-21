from pydantic import BaseModel


class FileMapping(BaseModel):
    src: str   # relative to setups/<id>/
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
