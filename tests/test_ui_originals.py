"""Tests for ui.originals — pre-agent file reconstruction for the three-way view."""

import subprocess

import pytest

from core.models import TaskSpec
from ui import originals
from ui.originals import OriginalResolver, diff_file_entries


def test_diff_file_entries_modify_create_delete_rename():
    diff = (
        "diff --git a/src/mod.py b/src/mod.py\n"
        "--- a/src/mod.py\n"
        "+++ b/src/mod.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
        "diff --git a/created.py b/created.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/created.py\n"
        "@@ -0,0 +1 @@\n"
        "+hello\n"
        "diff --git a/gone.py b/gone.py\n"
        "deleted file mode 100644\n"
        "--- a/gone.py\n"
        "+++ /dev/null\n"
        "@@ -1 +0,0 @@\n"
        "-bye\n"
        "diff --git a/old_name.py b/new_name.py\n"
        "--- a/old_name.py\n"
        "+++ b/new_name.py\n"
        "@@ -1 +1 @@\n"
        "-a\n"
        "+b\n"
    )
    assert diff_file_entries(diff) == [
        ("src/mod.py", "src/mod.py"),
        (None, "created.py"),
        ("gone.py", None),
        ("old_name.py", "new_name.py"),
    ]


def test_diff_file_entries_skips_mode_only_changes():
    diff = (
        "diff --git a/script.sh b/script.sh\n"
        "old mode 100644\n"
        "new mode 100755\n"
    )
    assert diff_file_entries(diff) == []


@pytest.fixture()
def fake_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("print('base content')\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo),
                         capture_output=True, text=True, check=True).stdout.strip()
    return repo, sha


def _task(repo, sha, **overrides):
    fields = dict(
        id="faketask", repo_url="https://example.com/fake", base_commit=sha,
        instruction="do it", run_cmd="true", held_out_tests_path="x",
        reference_diff_path="y", repo="fake",
    )
    fields.update(overrides)
    return TaskSpec(**fields)


def test_resolver_reads_base_commit_content(fake_repo, monkeypatch):
    repo, sha = fake_repo
    task = _task(repo, sha)
    monkeypatch.setattr(originals, "load_task", lambda tid: task)
    monkeypatch.setattr(originals, "resolve_repo_path", lambda t: repo)

    r = OriginalResolver("faketask", "baseline", "none", "oracle")
    assert r.available
    assert r.content("src/app.py") == "print('base content')\n"
    assert r.content("does/not/exist.py") is None


def test_resolver_prefers_laid_down_files(fake_repo, monkeypatch):
    repo, sha = fake_repo
    task = _task(repo, sha)
    monkeypatch.setattr(originals, "load_task", lambda tid: task)
    monkeypatch.setattr(originals, "resolve_repo_path", lambda t: repo)

    class FakeSpec:
        files = {"src/app.py": ["laid down line"]}

    monkeypatch.setattr(originals, "load_methodology", lambda mid, h: FakeSpec())
    r = OriginalResolver("faketask", "whatever", "none", "oracle")
    assert r.content("src/app.py") == "laid down line\n"


def test_resolver_unavailable_without_local_task(monkeypatch):
    def boom(tid):
        raise FileNotFoundError("no task")
    monkeypatch.setattr(originals, "load_task", boom)
    r = OriginalResolver("demo-lru-cache", "demo-baseline", "none", "demo-runner")
    assert not r.available
    assert "no local task spec" in r.reason
    # user-facing message must not expose internal exception class names
    assert "Error" not in r.reason
    assert r.content("anything.py") is None


def test_resolver_unavailable_without_cloned_repo(fake_repo, monkeypatch, tmp_path):
    repo, sha = fake_repo
    task = _task(repo, sha)
    monkeypatch.setattr(originals, "load_task", lambda tid: task)
    monkeypatch.setattr(originals, "resolve_repo_path", lambda t: tmp_path / "not-cloned")
    r = OriginalResolver("faketask", "baseline", "none", "oracle")
    assert not r.available
    assert "not cloned" in r.reason
