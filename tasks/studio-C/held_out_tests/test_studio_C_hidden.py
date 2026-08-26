"""Hidden FAIL_TO_PASS tests for studio-C: PR-body assembly factored into
`build_pr_body` with a "## Verified" section (studio_worker/implementation.py).

The instruction pins the API (`build_pr_body(issue_number, summary, attempt,
check_cmd=None, check_passed=None)`) and the "Not verified." line; everything
else asserted here is behaviour the instruction states (exact command named,
outcome stated, existing body content kept, the worker call site uses it).
"""
from types import SimpleNamespace

from studio_worker import implementation as impl


def test_verified_section_names_command_and_passed_outcome():
    body = impl.build_pr_body(7, "summary text", 1,
                              check_cmd="python tasks.py check", check_passed=True)
    # existing body content is kept
    assert "Closes #7" in body
    assert "summary text" in body
    # the Verified section names the exact command and its outcome
    assert "## Verified" in body
    assert "python tasks.py check" in body
    assert "passed" in body.lower()


def test_verified_section_states_failed_outcome():
    body = impl.build_pr_body(3, "s", 2, check_cmd="npm test", check_passed=False)
    assert "## Verified" in body
    assert "npm test" in body
    assert "failed" in body.lower()


def test_not_verified_path():
    body = impl.build_pr_body(9, "summary text", 2)
    assert "Closes #9" in body
    assert "## Verified" in body
    assert "Not verified." in body


def test_push_and_pr_body_carries_verified_section(monkeypatch, tmp_path):
    """The worker's PR-opening call site routes its body through build_pr_body:
    the PR that reaches GitHub carries the Verified section."""
    seen = {}
    monkeypatch.setattr(impl.jobs, "push_branch", lambda dest, branch, token: None)
    monkeypatch.setattr(impl.gh_ops, "default_branch", lambda gh, repo: "main")

    def fake_create_pr(gh_obj, repo, head, base, title, body):
        seen["body"] = body
        return {"number": 42}

    monkeypatch.setattr(impl.gh_ops, "create_pr", fake_create_pr)
    proj = SimpleNamespace(name="demo", repo="o/demo", owner=None,
                           check="python tasks.py check")
    cfg = SimpleNamespace(workspace_root=tmp_path, gh_token="T")
    issue = {"number": 7, "title": "Fix the thing"}

    # the pre-refactor positional call shape must keep working
    impl.push_and_pr(cfg, None, proj, issue, "agent/issue-7", "summary", 1)

    assert "## Verified" in seen["body"]
