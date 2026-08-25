"""Hidden FAIL_TO_PASS tests for studio-B: `studio conform` checks the GitHub
description against the README "What & why" opening sentence (naming.md rule 6).

Stubs the description source the same way tests/test_cli_conform.py does
(fake GitHub client + registry file + STUDIO_ROOT), and asserts only behaviour
the instruction states: missing description -> warning, exit 0 (unchanged);
disagreement -> a WARNING naming both sides; agreement modulo
case/whitespace/trailing-period -> no warning.
"""
import pytest
from click.testing import CliRunner

import studio_cli.cli as cli_mod
from studio_cli.cli import main
from studio_cli.github import GitHubError


class FakeGH:
    def __init__(self):
        self.repos = {}
        self.labels = {}
        self.patches = []

    def get(self, path, **kw):
        if path.endswith("/labels"):
            return self.labels.get(path, [])
        if path in self.repos:
            return self.repos[path]
        raise GitHubError(404, "Not Found")

    def post(self, path, json=None):
        return {}

    def patch(self, path, json=None):
        self.patches.append((path, json))
        return {}

    def put(self, path, json=None):
        return {}


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_gh(monkeypatch):
    fake = FakeGH()
    monkeypatch.setattr(cli_mod, "make_github", lambda: fake)
    return fake


@pytest.fixture
def project_dir(monkeypatch, tmp_path):
    """A registered project whose local path holds only a README (no .git, so
    conform's template-file block is skipped and no git state is touched)."""
    proj = tmp_path / "gavel"
    proj.mkdir()
    registry_path = tmp_path / "studio.yaml"
    registry_path.write_text(
        "projects:\n"
        "  gavel:\n"
        "    repo: meaurisch/gavel\n"
        "    tier: monthly\n"
        "    check: python3 tasks.py check\n"
        "    path: gavel\n"
    )
    monkeypatch.setattr(cli_mod, "REGISTRY_PATH", registry_path)
    monkeypatch.setattr(cli_mod, "STUDIO_ROOT", tmp_path)
    return proj


def _write_readme(proj, sentence):
    (proj / "README.md").write_text(
        f"# gavel\n\n## What & why\n{sentence} More detail\nfollows here.\n\n## Quickstart\nx\n",
        encoding="utf-8",
    )


def test_missing_description_still_warns_and_exits_zero(runner, fake_gh, project_dir):
    _write_readme(project_dir, "This repo benchmarks agentic coding setups blind.")
    fake_gh.repos["/repos/meaurisch/gavel"] = {"description": None}
    res = runner.invoke(main, ["conform", "gavel"])
    assert res.exit_code == 0, res.output
    assert "WARNING" in res.output


def test_disagreeing_description_warns_naming_both(runner, fake_gh, project_dir):
    _write_readme(project_dir, "This repo benchmarks agentic coding setups blind.")
    fake_gh.repos["/repos/meaurisch/gavel"] = {"description": "This repo grades cheese."}
    res = runner.invoke(main, ["conform", "gavel"])
    assert res.exit_code == 0, res.output  # a disagreement is a warning, not an error
    assert "WARNING" in res.output
    # the warning names both sides of the disagreement
    assert "This repo grades cheese" in res.output
    assert "This repo benchmarks agentic coding setups blind" in res.output


def test_agreement_modulo_normalisation_is_silent(runner, fake_gh, project_dir):
    _write_readme(project_dir, "This repo benchmarks   agentic coding setups blind.")
    # differs in case, internal whitespace, and trailing period only
    fake_gh.repos["/repos/meaurisch/gavel"] = {
        "description": "this repo Benchmarks agentic coding setups blind"
    }
    res = runner.invoke(main, ["conform", "gavel"])
    assert res.exit_code == 0, res.output
    assert "WARNING" not in res.output
