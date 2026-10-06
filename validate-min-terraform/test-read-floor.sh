#!/usr/bin/env bash
# Exercise read-floor.sh. Most cases are one constraint in one generated
# module; the cases that need more than that live under testdata/.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
export TERRAFORM_DOCS_IMAGE=${TERRAFORM_DOCS_IMAGE:-$(
  sed -n 's|.*default: \(quay.io/terraform-docs.*\)|\1|p' "$here/action.yml"
)}
export MINIMUM_FLOOR=${MINIMUM_FLOOR:-1.2.2}

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
failures=0

check() {
  local label=$1 expected=$2 actual=$3 rc=$4
  if [ "$expected" = FAIL ]; then
    if [ "$rc" -eq 0 ]; then
      echo "FAIL  $label: expected a non-zero exit, got $actual"
      failures=$((failures + 1))
      return
    fi
  elif [ "$actual" != "$expected" ]; then
    echo "FAIL  $label: expected $expected, got ${actual:-nothing} (exit $rc)"
    failures=$((failures + 1))
    return
  fi
  echo "ok    $label"
}

# One constraint per generated module. FAIL means the script must reject it.
while IFS='|' read -r constraint expected; do
  [ -n "$constraint" ] || continue
  dir="$work/$(printf '%s' "$constraint" | tr -c 'a-zA-Z0-9.' '_')"
  mkdir -p "$dir"
  printf 'terraform {\n  required_version = "%s"\n}\n' "$constraint" > "$dir/main.tf"
  actual=$(cd "$dir" && "$here/read-floor.sh" 2>/dev/null)
  check "$constraint" "$expected" "$actual" "$?"
done <<'CASES'
>= 1.14.0|1.14.0
>= 1.14.0, < 2.0.0|1.14.0
~> 1.14|1.14.0
>= 1.9, >= 1.14.0, < 2.0.0|1.14.0
>= 1.2.2|1.2.2
>= 1|FAIL
~> 1|FAIL
< 2.0.0|FAIL
1.14.0|FAIL
> 1.14.0|FAIL
>= 1.14.0, != 1.14.0|FAIL
>= 1.14.0-beta1|FAIL
CASES

# A short bound resolves rather than failing; it only trips the clamp.
dir="$work/short-bound" && mkdir -p "$dir"
printf 'terraform {\n  required_version = ">= 1"\n}\n' > "$dir/main.tf"
actual=$(cd "$dir" && MINIMUM_FLOOR=1.0.0 "$here/read-floor.sh" 2>/dev/null)
check "the floor pads a short bound" 1.0.0 "$actual" "$?"

# Terraform applies every constraint in the directory, including one in a
# .tf.json and one split across lines, so the highest lower bound wins.
actual=$(cd "$here/testdata/several-files" && "$here/read-floor.sh" 2>/dev/null)
check "several files in one directory" 1.99.0 "$actual" "$?"

# A config that hides the requirements section must not make a module that
# declares a constraint look like one that declares none.
actual=$(cd "$here/testdata/hidden-requirements" && "$here/read-floor.sh" 2>/dev/null)
check "a config hiding requirements" 1.14.0 "$actual" "$?"

# A module with no constraint at all is the one case that reports nothing.
dir="$work/no-constraint" && mkdir -p "$dir"
printf 'output "a" {\n  value = 1\n}\n' > "$dir/main.tf"
actual=$(cd "$dir" && "$here/read-floor.sh" 2>/dev/null)
check "no required_version" FAIL "$actual" "$?"

if [ "$failures" -gt 0 ]; then
  echo "$failures case(s) failed"
  exit 1
fi
echo "all cases passed"
