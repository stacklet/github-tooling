# github-tooling

Reusable GitHub Actions and workflows shared across Stacklet repositories.

Each tool lives in its own top-level directory with an `action.yml` and a `README.md`.
Reference one by path:

```yaml
- uses: stacklet/github-tooling/<tool>@<commit-sha>
```

Pin by commit SHA. This repository cuts releases, but it cuts them by hand and most
commits never get one, so a SHA is what names the commit you meant.

## Tools

| Tool | Purpose |
| --- | --- |
| [validate-min-terraform](validate-min-terraform/) | Runs `terraform validate` at the floor a module's `required_version` declares, and fails when that floor is below a configured minimum. |

### Adding a tool

1. Create a directory named for the tool.
2. Add an `action.yml` and a `README.md` covering usage, inputs, and outputs.
3. Keep any non-trivial logic in its own script beside the `action.yml`, so that a
   linter reads it and a test can run it without a runner. Prefer Python over shell for
   anything that parses or compares.
4. Add a row to the table above.

## Reusable workflows

### `run-script`


Run a set of commands on the repository, with the required tools installed via `mise`.


```
  Lint:
    permissions:
      contents: read
    uses: stacklet/github-tooling/.github/workflows/run-script.yml@<commit-sha>
    secrets:
      STEP_SECURITY_API_KEY: ${{ secrets.STEP_SECURITY_API_KEY }}
    with:
      pre-commit-cache: true
      run: |
        just lint
```

### `cut-release`

Works out the next version from the tag history and publishes a GitHub release for it,
on a manual dispatch. The caller owns the `workflow_dispatch` trigger, because that is
the workflow a person picks in the Actions tab, and the `concurrency` group, because a
called workflow cannot serialise its caller. Copy this block whole rather than writing
one:

```yaml
name: Release

on:
  workflow_dispatch:
    inputs:
      bump:
        description: Which part of the version to raise.
        required: true
        type: choice
        options:
          - (choose one)
          - patch
          - minor
          - major
      dry_run:
        description: Work out the next version and stop without publishing
        required: false
        type: boolean
        default: false

concurrency: release

permissions: {}

jobs:
  release:
    uses: stacklet/github-tooling/.github/workflows/cut-release.yml@<commit-sha>
    permissions:
      contents: write
    secrets:
      STEP_SECURITY_API_KEY: ${{ secrets.STEP_SECURITY_API_KEY }}
    with:
      bump: ${{ inputs.bump }}
      dry_run: ${{ inputs.dry_run }}
```

The workflow refuses to run against anything but the calling repository's default
branch, refuses any re-run of a run it has already started, and refuses to publish over
a tag it did not create. A retry means dispatching again.

The `bump` dropdown opens on `(choose one)`, which the workflow rejects. The version
walk starts from 0.0.0, so on a repository with no tags patch opens at `v0.0.1`, minor
at `v0.1.0` and major at `v1.0.0`. Which of those a repository wants is its own call,
so the workflow asks rather than assumes.

`STEP_SECURITY_API_KEY` is optional. Without it the Harden Runner step is skipped and
the rest runs unchanged.
