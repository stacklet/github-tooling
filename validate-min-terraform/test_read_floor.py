#!/usr/bin/env python3
"""Exercise read_floor.py.

The constraint cases run against the parser directly, so they need no container.
The cases that turn on what terraform-docs reports run the script against the
fixtures under testdata/.
"""

import os
import pathlib
import re
import subprocess
import unittest

import read_floor

HERE = pathlib.Path(__file__).parent
DEFAULT_MINIMUM = (1, 2, 2)

# The image the action defaults to, so the tests and the action cannot drift.
IMAGE = os.environ.get("TERRAFORM_DOCS_IMAGE") or re.search(
    r"default: (quay\.io/terraform-docs/\S+)", (HERE / "action.yml").read_text()
).group(1)


RESOLVES = [
    ([">= 1.14.0"], "1.14.0"),
    ([">= 1.14.0, < 2.0.0"], "1.14.0"),
    (["~> 1.14"], "1.14.0"),
    ([">= 1.9, >= 1.14.0, < 2.0.0"], "1.14.0"),
    ([">= 1.2.2"], "1.2.2"),
    # Terraform applies every constraint in the directory at once.
    ([">= 1.99.0", ">= 1.2.0", ">= 1.14.0"], "1.99.0"),
    # A short bound is the lowest release matching it.
    ([">= 1"], "1.0.0"),
    (["~> 1"], "1.0.0"),
]

REJECTS = [
    # No lower bound to test.
    (["< 2.0.0"], "states no lower bound"),
    (["<= 2.0.0"], "states no lower bound"),
    # An operator that can rule out the bound another term states.
    (["1.14.0"], "cannot resolve"),
    ([">= 1.14.0, != 1.14.0"], "cannot resolve"),
    ([">= 1.14.0, = 1.15.0"], "cannot resolve"),
    # Exclusive, so it names no release to install.
    (["> 1.14.0"], "cannot resolve"),
    ([">= 1.14.0-beta1"], "cannot resolve"),
    ([], "declares no required_version"),
]


class DeriveFloorTest(unittest.TestCase):
    def test_resolves(self):
        for constraints, expected in RESOLVES:
            with self.subTest(constraints=constraints):
                minimum = (1, 0, 0) if expected == "1.0.0" else DEFAULT_MINIMUM
                floor = read_floor.derive_floor(constraints, minimum)
                self.assertEqual(read_floor.format_version(floor), expected)

    def test_rejects(self):
        for constraints, message in REJECTS:
            with self.subTest(constraints=constraints):
                with self.assertRaises(read_floor.FloorError) as caught:
                    read_floor.derive_floor(constraints, DEFAULT_MINIMUM)
                self.assertIn(message, str(caught.exception))

    def test_a_floor_below_the_minimum_is_refused(self):
        with self.assertRaises(read_floor.FloorError) as caught:
            read_floor.derive_floor([">= 1.1.0"], DEFAULT_MINIMUM)
        self.assertIn("below the minimum", str(caught.exception))

    def test_the_minimum_itself_is_allowed(self):
        floor = read_floor.derive_floor([">= 1.2.2"], DEFAULT_MINIMUM)
        self.assertEqual(floor, DEFAULT_MINIMUM)


class ReadFloorScriptTest(unittest.TestCase):
    """End to end, including the terraform-docs run. These need Docker."""

    def run_script(self, directory, minimum="1.2.2"):
        return subprocess.run(
            [str(HERE / "read_floor.py")],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
            env={
                **os.environ,
                "TERRAFORM_DOCS_IMAGE": IMAGE,
                "MINIMUM_FLOOR": minimum,
            },
        )

    def test_several_files_in_one_directory(self):
        """The highest bound wins, and here it is the one in the .tf.json."""
        result = self.run_script(HERE / "testdata" / "several-files")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "1.99.0")

    def test_a_constraint_split_across_lines_decides(self):
        """The multiline form is the one a regex over the file reads as empty."""
        result = self.run_script(HERE / "testdata" / "multiline-constraint")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "1.14.0")

    def test_a_config_hiding_requirements(self):
        """A module that declares a constraint must not look like one that does not."""
        result = self.run_script(HERE / "testdata" / "hidden-requirements")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "1.14.0")

    def test_no_required_version(self):
        result = self.run_script(HERE / "testdata" / "no-constraint")
        self.assertEqual(result.returncode, 1)
        self.assertIn("declares no required_version", result.stderr)

    def test_a_container_that_cannot_run_says_so(self):
        result = self.run_script(HERE / "testdata" / "several-files")
        self.assertEqual(result.returncode, 0, result.stderr)
        broken = subprocess.run(
            [str(HERE / "read_floor.py")],
            cwd=HERE / "testdata" / "several-files",
            capture_output=True,
            text=True,
            check=False,
            env={
                **os.environ,
                "TERRAFORM_DOCS_IMAGE": "quay.io/terraform-docs/terraform-docs:no-such-tag",
                "MINIMUM_FLOOR": "1.2.2",
            },
        )
        self.assertEqual(broken.returncode, 1)
        self.assertIn("could not read this module", broken.stderr)


if __name__ == "__main__":
    unittest.main()
