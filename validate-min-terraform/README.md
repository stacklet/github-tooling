# validate-min-terraform

Runs `terraform validate` against a module at the oldest Terraform release the module says it supports.

A repository's lint job validates at the release pinned in `.tool-versions`, which is near the top of the supported range. Nothing covers the bottom of the range, so a module can declare `required_version = ">= 1.0"` and use syntax that no release below 1.8 parses. This action closes that gap.

## Usage

```yaml
jobs:
  validate-min-terraform:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - name: Checkout
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false

      - uses: stacklet/github-tooling/validate-min-terraform@<commit-sha>
```

## Inputs

| Name | Default | Description |
| --- | --- | --- |
| `working-directory` | `.` | Directory holding the module to validate. |
| `minimum-floor` | `1.2.2` | Refuse to run below this release. |
| `terraform-docs-image` | a digest-pinned terraform-docs 0.20.0 | Image used to parse the configuration. |

## Outputs

| Name | Description |
| --- | --- |
| `version` | The Terraform release the module declares as its floor. |

## How the floor is derived

`terraform-docs` parses the configuration and reports every `required_version` in the directory. Terraform applies all of them at once, so the effective floor is the highest lower bound among them. Only `>=` and `~>` state that bound literally, and `<` and `<=` cannot move it.

The action fails rather than guessing on anything else:

- A constraint with no lower bound, such as `< 2.0.0` alone, names no floor to test.
- `!=` and `=` can rule out the bound another term states, which would otherwise install a release the module excludes.
- `>` is exclusive, so it states no release to install. Write `>= 1.14.1` rather than `> 1.14.0`.

The action reads one directory. A repository with modules in subdirectories needs one call per directory, which a matrix over `working-directory` covers.

Running a real parser matters. A regex over `*.tf` misses a constraint in a `.tf.json`, misses a second `.tf` file, and reads a constraint split across lines as empty, which several published actions then treat as "any version".

The terraform-docs image is pinned by digest because the project publishes no immutable releases, so both a tag and a release checksum can change underneath us. Bumping the version means bumping the digest in `action.yml`.

## Why there is a floor on the floor

The release this installs comes out of the configuration under test, so on a pull request the branch decides which Terraform runs in CI. That is the point of the action, and it is also a way to reach an old release for the sake of its bugs rather than for support. `terraform init` installs providers and fetches module sources whatever `-backend=false` says, and Terraform 1.0.0 through 1.2.1 bundle a go-getter affected by HCSEC-2022-13, which HashiCorp never backported to those lines.

`minimum-floor` defaults to 1.2.2, the first release past that. Raise it to your own support floor if you would rather not run old releases at all.

Two things this does not solve. A pull request still chooses which providers `init` installs, and a provider plugin is a binary that `validate` executes to read its schema, so the job must hold no secrets and no write permission. The usage example above is the shape to keep. Committing `.terraform.lock.hcl` would pin provider checksums, but a pull request can edit the lock file in the same commit, so it narrows the window rather than closing it.

## Requirements

The runner needs Docker, since the parse runs in a container, and `python3`, which reads the result. `ubuntu-latest` has both. The macOS runners have no Docker.

## Tests

`just test` runs `test_read_floor.py`, and CI runs the same command. The constraint cases call the parser directly and need no container, so adding one for a constraint form the parser learns to read or to reject costs nothing. Only the cases that turn on what terraform-docs reports run the script end to end, against the fixtures under `testdata/`.

## Known limitation

`terraform validate` run against a module directory treats every root variable as unknown, so it never evaluates `validation` blocks. A module whose floor is wrong only inside a variable validation still passes here. Closing that needs `terraform test` with `mock_provider`.
