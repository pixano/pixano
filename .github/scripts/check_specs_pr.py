# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Check that a pull request which changes specs/ changes nothing else and carries the spec label.

The specifications in specs/ are the source of truth on how Pixano is built. A change to them is
agreed on its own, so it travels in its own pull request: never next to the code it allows.

The Specs workflow runs this in a checkout of the merge commit of the pull request.
"""

import json
import os
import subprocess
import sys


SPECS = "specs"
LABEL = "spec-change"
# How many paths a message names before it says "and N more".
SHOWN = 10


def is_spec(path: str) -> bool:
    """Tell whether a path is the top-level specs directory or inside it."""
    return path.split("/", 1)[0] == SPECS


def listing(paths: list[str]) -> str:
    """Quote paths on one line, so that a file name cannot start a workflow command."""
    more = f" and {len(paths) - SHOWN} more" if len(paths) > SHOWN else ""
    return ", ".join(json.dumps(path) for path in paths[:SHOWN]) + more


def violations(paths: list[str], labels: list[str]) -> list[str]:
    """List what a pull request gets wrong about the specifications.

    Args:
        paths: Every path the pull request changes on its base branch. A renamed file counts
            twice, under its old path and under its new one.
        labels: The labels the pull request carries.

    Returns:
        One message per broken rule, each saying what to do. Empty when the pull request complies.
    """
    inside = sorted(path for path in paths if is_spec(path))
    outside = sorted(path for path in paths if not is_spec(path))
    lookalikes = [path for path in outside if path.split("/", 1)[0].lower() == SPECS]
    messages = []
    if lookalikes:
        messages.append(
            f"The specifications directory is spelled {SPECS}/, in lower case. These paths are not in it, so its "
            f"code owner would not be asked to review them: {listing(lookalikes)}. Rename the directory to {SPECS}/."
        )
    if inside and outside:
        messages.append(
            f"This pull request changes {SPECS}/ and files outside {SPECS}/. A change to {SPECS}/ is its own pull "
            f"request: move one of the two groups to a separate pull request. Under {SPECS}/: {listing(inside)}. "
            f"Outside {SPECS}/: {listing(outside)}."
        )
    if inside and LABEL not in labels:
        messages.append(
            f'This pull request changes {SPECS}/ but does not carry the label "{LABEL}". Add the label, or ask a '
            "maintainer to add it: this check then runs again by itself."
        )
    return messages


def output(*command: str) -> str:
    """Return what a command prints. A command that fails raises, and the check fails with it."""
    return subprocess.run(
        command, check=True, stdout=subprocess.PIPE, encoding="utf-8", errors="backslashreplace"
    ).stdout


def changed_paths() -> list[str] | None:
    """List the paths that merging the pull request would change on its base branch.

    The checkout is the merge commit of the pull request: its first parent is the base branch.
    Rename detection is off, so a file moved across the border of specs/ shows on both sides.

    Returns:
        The paths, or None when the checkout is not a merge commit.
    """
    parents = output("git", "rev-list", "--parents", "-n", "1", "HEAD").split()[1:]
    if len(parents) != 2:
        return None
    diff = output("git", "diff", "--no-renames", "--name-only", "-z", "HEAD^1", "HEAD")
    return [path for path in diff.split("\0") if path]


def main() -> int:
    """Check the pull request whose merge commit is checked out, and return the exit code."""
    event = os.environ.get("GITHUB_EVENT_NAME")
    if event == "push":
        print("A push, not a pull request: nothing to check.")
        return 0
    if event != "pull_request":
        print(f"::error title=Specs::This check knows pull requests and pushes, not the event {json.dumps(event)}.")
        return 1

    paths = changed_paths()
    if paths is None:
        print(
            "::error title=Specs::This check reads the merge commit of the pull request, and the commit checked "
            "out is not a merge. Re-run this job."
        )
        return 1

    labels: list[str] = []
    if any(is_spec(path) for path in paths):
        # Read now, not taken from the event: a re-run after a label change must see the new labels.
        repository, number = os.environ["GITHUB_REPOSITORY"], os.environ["PR_NUMBER"]
        pull = json.loads(output("gh", "api", f"repos/{repository}/pulls/{number}"))
        labels = [label["name"] for label in pull["labels"]]

    messages = violations(paths, labels)
    for message in messages:
        print(f"::error title=Specs::{message}")
    if not messages:
        print(f"{sum(map(is_spec, paths))} of {len(paths)} changed files are under {SPECS}/: nothing to report.")
    return 1 if messages else 0


if __name__ == "__main__":
    sys.exit(main())
