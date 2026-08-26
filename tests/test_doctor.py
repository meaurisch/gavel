import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import doctor  # noqa: E402


def test_probe_reports_missing_binary():
    ok, detail = doctor._probe(["definitely-not-a-real-binary-xyz", "--version"])
    assert ok is False
    assert "not found" in detail


def test_check_vendor_packs_covers_external_methodologies():
    rows = doctor.check_vendor_packs()
    names = {r.name for r in rows}
    # every methodology with an external source gets a row
    assert {"vendor pack ecc", "vendor pack karpathy", "vendor pack superpowers"} <= names
    # baseline/custom have no source -> no row
    assert not any("baseline" in n or "custom" in n for n in names)


def test_check_repo_context_builds_none_shipped():
    # Of the shipped repo contexts, only the E6 arms (studio#83) declare a
    # build: step today; the rest are hand-authored and contribute no rows.
    rows = doctor.check_repo_context_builds()
    names = {r.name for r in rows}
    assert names == {"repo-context build e6-decision-time", "repo-context build e6-index"}
    assert all(r.ok and not r.required for r in rows)


def test_check_repo_context_builds_is_informational(tmp_path):
    ctx_dir = tmp_path / "derived"
    ctx_dir.mkdir()
    (ctx_dir / "manifest.yaml").write_text(
        "id: derived\ndescription: derived\n"
        "build:\n  command: echo hi\n  source_ref: some-repo@some-ref\n",
        encoding="utf-8",
    )

    rows = doctor.check_repo_context_builds(tmp_path)
    assert len(rows) == 1
    row = rows[0]
    assert row.name == "repo-context build derived"
    assert row.ok is True
    assert row.required is False
    assert "some-repo@some-ref" in row.detail


def test_check_pricing_ok():
    row = doctor.check_pricing()
    assert row.ok
    assert "models priced" in row.detail


def test_check_node_and_frontend_rows_present():
    rows = doctor.run_all_checks()
    by_name = {r.name: r for r in rows}
    assert "node + npm" in by_name
    assert "web UI build" in by_name
    # Both are hard requirements of the documented quickstart.
    assert by_name["node + npm"].required
    assert by_name["web UI build"].required


def test_frontend_built_detects_dist():
    from frontend_setup import DIST_INDEX, frontend_built

    # In this repo the frontend is built during development; the check must
    # simply agree with the filesystem either way.
    assert frontend_built() == DIST_INDEX.is_file()
