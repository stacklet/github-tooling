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
| `terraform-docs-image` | a digest-pinned terraform-docs 0.20.0 | Image used to parse the configuration. |

## Outputs

| Name | Description |
| --- | --- |
| `version` | The Terraform release the module declares as its floor. |

## How the floor is derived

`terraform-docs` parses the configuration and reports every `required_version` in the module. Terraform applies all of them at once, so the effective floor is the highest lower bound among them. Only `>=` and `~>` state that bound literally, and `<` and `<=` cannot move it.

The action fails rather than guessing on anything else. A constraint with no lower bound has no floor to test, and an operator such as `!=` or `=` can rule out the bound another term states, which would otherwise install a release the module excludes.

Running a real parser matters. A regex over `*.tf` misses a constraint in a `.tf.json`, misses a second `.tf` file, and reads a constraint split across lines as empty, which several published actions then treat as "any version".

The terraform-docs image is pinned by digest because the project publishes no immutable releases, so both a tag and a release checksum can change underneath us. Bumping the version means bumping the digest in `action.yml`.

## Known limitation

`terraform validate` run against a module directory treats every root variable as unknown, so it never evaluates `validation` blocks. A module whose floor is wrong only inside a variable validation still passes here. Closing that needs `terraform test` with `mock_provider`.
