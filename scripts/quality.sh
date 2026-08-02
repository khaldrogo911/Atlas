#!/usr/bin/env bash
#
# Project Atlas — local quality gate.
#
# Runs the same checks as the `quality` job in .github/workflows/ci.yml, in the
# same order, so that a green run here means a green run there. Any divergence
# between this file and that workflow is a bug in one of them.
#
# Usage:
#   scripts/quality.sh          # check only — what CI does
#   scripts/quality.sh --fix    # apply Ruff's safe fixes and Black's formatting
#
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

FIX=0
for arg in "$@"; do
    case "$arg" in
        --fix) FIX=1 ;;
        -h | --help)
            sed -n '3,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "unknown argument: $arg" >&2
            echo "usage: $0 [--fix]" >&2
            exit 64
            ;;
    esac
done

if ! command -v poetry > /dev/null 2>&1; then
    echo "poetry not found on PATH — see README.md § Development Setup" >&2
    exit 127
fi

step() {
    printf '\n\033[1m==> %s\033[0m\n' "$1"
}

if [[ $FIX -eq 1 ]]; then
    step "Ruff (fixing)"
    poetry run ruff check --fix .

    step "Black (formatting)"
    poetry run black .
else
    step "Ruff"
    poetry run ruff check .

    step "Black"
    poetry run black --check --diff .
fi

step "MyPy"
poetry run mypy .

step "Pytest"
poetry run pytest

printf '\n\033[1;32mQuality gate passed.\033[0m\n'
