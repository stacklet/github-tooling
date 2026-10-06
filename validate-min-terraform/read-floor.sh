#!/usr/bin/env bash
# Print the oldest Terraform release the module in the working directory
# supports, read out of its required_version constraints.
set -euo pipefail

: "${TERRAFORM_DOCS_IMAGE:?}"
: "${MINIMUM_FLOOR:?}"

# terraform-docs writes its own diagnostics to stderr, and merging those into
# the pipe below breaks the JSON parse. They are kept aside rather than
# discarded so that a failed pull or a parse error still says what went wrong
# instead of surfacing as empty output.
stderr=$(mktemp)
trap 'rm -f "$stderr"' EXIT

# --show overrides a .terraform-docs.yml that hides the requirements section,
# which would otherwise report a module that declares a constraint as one that
# declares none. --output-file keeps terraform-docs from writing its render
# into the mounted directory under a config-supplied output.file.
if ! parsed=$(docker run --rm --network none -u "$(id -u):$(id -g)" \
  -v "$PWD:/wd:ro" -w /wd "$TERRAFORM_DOCS_IMAGE" \
  json . --output-file '' --show requirements 2>"$stderr"); then
  echo "terraform-docs could not read this module:" >&2
  cat "$stderr" >&2
  exit 1
fi

constraints=$(printf '%s' "$parsed" \
  | jq -r '.requirements[] | select(.name == "terraform") | .version')
if [ -z "$constraints" ]; then
  echo "this module declares no required_version" >&2
  exit 1
fi

# Terraform applies every required_version in the directory at once, so the
# effective floor is the highest lower bound among them. Only >= and ~> state
# that bound literally, and an operator such as != or = can rule out the bound
# another term states. Resolving either needs the release list, so reject what
# this cannot read rather than guess at it.
bounds=""
while IFS= read -r term; do
  term=$(printf '%s' "$term" | tr -d '[:space:]')
  [ -n "$term" ] || continue
  case "$term" in
    '>='*|'~>'*) bound=${term#??} ;;
    # An upper bound cannot move the floor, so it needs no reading.
    '<'*) continue ;;
    *)
      echo "cannot resolve a Terraform floor from: $term" >&2
      echo "required_version may use >=, ~>, < and <= only" >&2
      exit 1
      ;;
  esac
  if ! printf '%s' "$bound" | grep -qE '^[0-9]+(\.[0-9]+){0,2}$'; then
    echo "not a version this can resolve: $term" >&2
    exit 1
  fi
  # Terraform reads a short bound as the lowest release matching it, so >= 1
  # means 1.0.0 and setup-terraform needs all three components.
  case "$bound" in
    *.*.*) ;;
    *.*) bound="$bound.0" ;;
    *) bound="$bound.0.0" ;;
  esac
  bounds=$(printf '%s\n%s' "$bounds" "$bound")
done <<EOF
$(printf '%s' "$constraints" | tr ',' '\n')
EOF

# grep exits non-zero on no match, which under -e would end the script before
# the message below gets to say why.
floor=$(printf '%s' "$bounds" | grep -v '^$' | sort -V | tail -1) || true
if [ -z "$floor" ]; then
  echo "required_version states no lower bound; found:" >&2
  printf '%s\n' "$constraints" | sed 's/^/  /' >&2
  exit 1
fi

# The floor comes out of the configuration under test, and on a pull request
# that configuration is whatever the pull request says. Without a clamp the
# branch picks which Terraform release CI runs, which is a way to reach an old
# release for the sake of its bugs rather than for support.
if [ "$(printf '%s\n%s' "$MINIMUM_FLOOR" "$floor" | sort -V | head -1)" != "$MINIMUM_FLOOR" ]; then
  echo "declared floor $floor is below the minimum this action will run: $MINIMUM_FLOOR" >&2
  exit 1
fi

printf '%s\n' "$floor"
