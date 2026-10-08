# validate-min-terraform

Runs `terraform validate` against a Terraform module at the oldest release its
`required_version` allows, so the bottom of the declared range gets tested
rather than assumed.

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

> [!WARNING]
> `terraform init` installs the providers the module names, and `validate` runs
> each provider binary to read its schema. On a pull request that configuration
> is untrusted, so give the job `contents: read`, and no secrets.

## Inputs

| Name | Default | Description |
| --- | --- | --- |
| `working-directory` | `.` | Directory holding the module. One directory per call, with no descent into subdirectories. |
| `minimum-floor` | `1.14.0` | Refuse to run below this release. The default is the oldest release HashiCorp still ships fixes for. |
| `terraform-docs-image` | a digest-pinned terraform-docs 0.20.0 | Image used to parse the configuration. |

## Outputs

| Name | Description |
| --- | --- |
| `version` | The Terraform release the module declares as its floor. |

## Requirements

The runner needs Docker and `python3`. `ubuntu-latest` has both, and the macOS
runners have no Docker.

## Version constraints

`required_version` must state a lower bound with `>=`, `~>` or `=`, or name an
exact version such as `1.14.0`. Upper bounds are allowed and ignored. The action
rejects any constraint it cannot resolve to a definite release, and fails when
the floor it resolves falls below `minimum-floor`.

Every `required_version` in the directory counts, including one in a `.tf.json`
or split across lines. The floor is the highest lower bound among them, which
is what Terraform itself applies.

## Known limitation

> [!NOTE]
> `terraform validate` treats every root variable as unknown, so it never
> evaluates `validation` blocks. A floor that is wrong only inside a variable
> validation still passes here.

## Tests

`just test` runs `test_read_floor.py`, and CI runs the same command.
