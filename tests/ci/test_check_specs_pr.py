# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests of the Specs check, .github/scripts/check_specs_pr.py."""

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[2] / ".github" / "scripts" / "check_specs_pr.py"
_module_spec = importlib.util.spec_from_file_location("check_specs_pr", SCRIPT)
check_specs_pr = importlib.util.module_from_spec(_module_spec)
_module_spec.loader.exec_module(check_specs_pr)

LABELLED = ["spec-change"]


@pytest.mark.parametrize(
    ("paths", "labels", "fragments"),
    [
        # Nothing under specs/: the label does not matter.
        ([], [], []),
        (["src/a.py"], [], []),
        (["src/a.py"], LABELLED, []),
        # Only the top-level directory is the specifications.
        (["docs/specs/b.md", "specs.md", "src/specs/c.py"], [], []),
        # A spec pull request.
        (["specs/a.md", "specs/sub/b.md"], LABELLED, []),
        (["specs/a.md"], [], ["does not carry"]),
        (["specs/a.md"], ["Spec-Change"], ["does not carry"]),
        # A spec changed next to something else, with or without the label.
        (["specs/a.md", "README.md"], LABELLED, ["files outside"]),
        (["specs/a.md", "README.md"], [], ["files outside", "does not carry"]),
        # A file moved out of specs/, as a diff without rename detection lists it.
        (["specs/a.md", "docs/a.md"], LABELLED, ["files outside"]),
        # A spec deleted, and specs/ replaced by a file.
        (["specs/a.md"], LABELLED, []),
        (["specs"], [], ["does not carry"]),
        # A directory that only looks like specs/ escapes its code owner.
        (["Specs/a.md"], LABELLED, ["lower case"]),
    ],
)
def test_violations(paths, labels, fragments):
    messages = check_specs_pr.violations(paths, labels)
    assert len(messages) == len(fragments)
    assert all(fragment in message for fragment, message in zip(fragments, messages))


def test_a_message_names_the_paths_on_both_sides():
    (message,) = check_specs_pr.violations(["specs/jobs.md", "src/pixano/api/jobs.py"], LABELLED)
    assert '"specs/jobs.md"' in message
    assert '"src/pixano/api/jobs.py"' in message


def test_a_long_list_of_paths_is_cut():
    paths = ["specs/a.md"] + [f"src/{index:02}.py" for index in range(25)]
    (message,) = check_specs_pr.violations(paths, LABELLED)
    assert '"src/09.py"' in message
    assert '"src/10.py"' not in message
    assert "and 15 more" in message


def test_a_file_name_cannot_start_a_workflow_command():
    (message,) = check_specs_pr.violations(["specs/a\n::notice::b.md", "c"], LABELLED)
    assert "\n" not in message


def _git(repository: Path, *arguments: str) -> None:
    """Run git in a repository, away from the configuration of the machine."""
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
    )


def _commit(repository: Path, message: str) -> None:
    _git(repository, "add", "--all")
    _git(repository, "commit", "--message", message)


@pytest.fixture
def repository(tmp_path, monkeypatch):
    """A repository with one spec and one source file on main, and the tests running inside it."""
    repository = tmp_path / "repository"
    (repository / "specs").mkdir(parents=True)
    (repository / "specs" / "jobs.md").write_text("# Jobs\n\nA job runs in the worker.\n" * 10)
    (repository / "src.py").write_text("print('pixano')\n")
    _git(repository, "init", "--initial-branch=main")
    _commit(repository, "base")
    monkeypatch.chdir(repository)
    return repository


def _merge_a_pull_request(repository: Path, change) -> None:
    """Leave the repository on the merge commit of a pull request, as the Specs workflow finds it.

    The base branch moves on while the pull request is open: what it brings is not what the pull
    request changes.
    """
    _git(repository, "switch", "--create", "pull-request")
    change(repository)
    _commit(repository, "the pull request")
    _git(repository, "switch", "main")
    (repository / "meanwhile.py").write_text("print('main moved on')\n")
    _commit(repository, "main moves on")
    _git(repository, "merge", "--no-ff", "--message", "merge", "pull-request")


def _move_the_spec_out(repository: Path) -> None:
    (repository / "docs").mkdir()
    _git(repository, "mv", "specs/jobs.md", "docs/jobs.md")


def _edit_the_spec(repository: Path) -> None:
    (repository / "specs" / "jobs.md").write_text("# Jobs\n\nA job runs in the worker, never in the API.\n")


def _edit_the_code(repository: Path) -> None:
    (repository / "src.py").write_text("print('pixano 2')\n")


def test_changed_paths_lists_what_the_pull_request_changes(repository):
    _merge_a_pull_request(repository, _edit_the_code)
    assert check_specs_pr.changed_paths() == ["src.py"]


def test_changed_paths_lists_a_moved_file_on_both_sides(repository):
    _merge_a_pull_request(repository, _move_the_spec_out)
    assert check_specs_pr.changed_paths() == ["docs/jobs.md", "specs/jobs.md"]


def test_changed_paths_refuses_a_commit_that_is_not_a_merge(repository):
    assert check_specs_pr.changed_paths() is None


@pytest.fixture
def pull_request_event(monkeypatch):
    """The environment of the Specs job on a pull request, with the labels GitHub would answer."""
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_REPOSITORY", "pixano/pixano")
    monkeypatch.setenv("PR_NUMBER", "1")
    answered = {"labels": [], "calls": 0}
    run = check_specs_pr.output

    def output(*command: str) -> str:
        if command[0] != "gh":
            return run(*command)
        assert command == ("gh", "api", "repos/pixano/pixano/pulls/1")
        answered["calls"] += 1
        return json.dumps({"labels": [{"name": name} for name in answered["labels"]]})

    monkeypatch.setattr(check_specs_pr, "output", output)
    return answered


def test_a_code_pull_request_passes_without_asking_for_its_labels(repository, pull_request_event, capsys):
    _merge_a_pull_request(repository, _edit_the_code)
    assert check_specs_pr.main() == 0
    assert pull_request_event["calls"] == 0
    assert "::error" not in capsys.readouterr().out


def test_a_spec_pull_request_fails_without_the_label_and_passes_with_it(repository, pull_request_event, capsys):
    _merge_a_pull_request(repository, _edit_the_spec)

    assert check_specs_pr.main() == 1
    assert "::error title=Specs::" in capsys.readouterr().out

    pull_request_event["labels"] = ["spec-change"]
    assert check_specs_pr.main() == 0
    assert "::error" not in capsys.readouterr().out


def test_a_spec_moved_out_of_specs_fails_even_with_the_label(repository, pull_request_event, capsys):
    pull_request_event["labels"] = ["spec-change"]
    _merge_a_pull_request(repository, _move_the_spec_out)
    assert check_specs_pr.main() == 1
    assert "files outside" in capsys.readouterr().out


def test_a_commit_that_is_not_a_merge_fails(repository, pull_request_event, capsys):
    assert check_specs_pr.main() == 1
    assert "not a merge" in capsys.readouterr().out


def test_a_push_has_nothing_to_check(monkeypatch):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    assert check_specs_pr.main() == 0


def test_an_unknown_event_fails(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request_target")
    assert check_specs_pr.main() == 1
    assert "::error" in capsys.readouterr().out
