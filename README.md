# github-tooling

Reusable GitHub Actions and workflows shared across Stacklet repositories.

Each tool lives in its own top-level directory with an `action.yml` and a `README.md`. Reference one by path:

```yaml
- uses: stacklet/github-tooling/<tool>@<commit-sha>
```

Pin by commit SHA. This repository publishes no release tags, so a SHA is the only reference that cannot move.

## Tools

| Tool | Purpose |
| --- | --- |
| [validate-min-terraform](validate-min-terraform/) | Runs `terraform validate` at the floor a module's `required_version` declares, and fails when that floor is below a configured minimum. |

## Adding a tool

1. Create a directory named for the tool.
2. Add an `action.yml` and a `README.md` covering usage, inputs, and outputs.
3. Keep any non-trivial logic in its own script beside the `action.yml`, so that a linter reads it and a test can run it without a runner. Prefer Python over shell for anything that parses or compares.
4. Add a row to the table above.
