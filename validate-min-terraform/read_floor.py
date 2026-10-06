#!/usr/bin/env python3
"""Print the oldest Terraform release the module in the working directory supports.

The floor is read out of the module's required_version constraints rather than
passed in, so that editing a constraint moves what CI tests in the same commit.
"""

import json
import os
import re
import subprocess
import sys

# >= and ~> are the only operators that state a lower bound literally. < and <=
# cannot move the floor. Anything else either states no bound at all or can rule
# out the bound another term states, and resolving that needs the release list.
LOWER_BOUND = re.compile(r"^(?:>=|~>)\s*(\d+(?:\.\d+){0,2})$")
UPPER_BOUND = re.compile(r"^<=?\s*\S+$")


class FloorError(Exception):
    """A constraint this cannot resolve a floor from."""


def parse_version(text):
    """Read a version as a comparable tuple.

    Terraform reads a short bound as the lowest release matching it, so >= 1
    means 1.0.0.
    """
    parts = [int(part) for part in text.split(".")]
    return tuple(parts + [0] * (3 - len(parts)))


def format_version(version):
    return ".".join(str(part) for part in version)


def lower_bounds(constraints):
    """Yield the lower bound stated by each term of each constraint."""
    for constraint in constraints:
        for term in constraint.split(","):
            term = term.strip()
            if not term:
                continue
            match = LOWER_BOUND.match(term)
            if match:
                yield parse_version(match.group(1))
            elif not UPPER_BOUND.match(term):
                raise FloorError(
                    f"cannot resolve a Terraform floor from: {term}\n"
                    "required_version may use >=, ~>, < and <= only"
                )


def derive_floor(constraints, minimum):
    """Return the release to install, given every constraint in the directory.

    Terraform applies all of them at once, so the effective floor is the highest
    lower bound among them.
    """
    if not constraints:
        raise FloorError("this module declares no required_version")

    bounds = list(lower_bounds(constraints))
    if not bounds:
        found = "\n".join(f"  {constraint}" for constraint in constraints)
        raise FloorError(f"required_version states no lower bound; found:\n{found}")

    floor = max(bounds)
    # The floor comes out of the configuration under test, and on a pull request
    # that configuration is whatever the pull request says. Without a clamp the
    # branch picks which Terraform release CI runs, which is a way to reach an
    # old release for the sake of its bugs rather than for support.
    if floor < minimum:
        raise FloorError(
            f"declared floor {format_version(floor)} is below the minimum "
            f"this action will run: {format_version(minimum)}"
        )
    return floor


def read_constraints(image, directory):
    """Return every Terraform required_version terraform-docs finds in a directory.

    --show overrides a .terraform-docs.yml that hides the requirements section,
    which would otherwise report a module that declares a constraint as one that
    declares none. --output-file keeps terraform-docs from writing its render
    into the mounted directory under a config-supplied output.file.
    """
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "-u",
            f"{os.getuid()}:{os.getgid()}",
            "-v",
            f"{directory}:/wd:ro",
            "-w",
            "/wd",
            image,
            "json",
            ".",
            "--output-file",
            "",
            "--show",
            "requirements",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise FloorError(
            f"terraform-docs could not read this module:\n{result.stderr.rstrip()}"
        )
    requirements = json.loads(result.stdout).get("requirements") or []
    return [
        requirement["version"]
        for requirement in requirements
        if requirement.get("name") == "terraform"
    ]


def main():
    image = os.environ["TERRAFORM_DOCS_IMAGE"]
    minimum = parse_version(os.environ["MINIMUM_FLOOR"])
    try:
        constraints = read_constraints(image, os.getcwd())
        print(format_version(derive_floor(constraints, minimum)))
    except FloorError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
