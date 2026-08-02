# Scripts

Developer and operator entrypoints. Everything here is a thin wrapper around a
command you could run by hand — nothing in this directory owns behaviour that
the application depends on.

| Script | Purpose |
|---|---|
| `quality.sh` | Run the CI quality gate locally (macOS / Linux) |
| `quality.ps1` | Run the CI quality gate locally (Windows) |

## `quality.sh` / `quality.ps1`

```bash
scripts/quality.sh            # check only — exactly what CI does
scripts/quality.sh --fix      # apply Ruff's safe fixes and Black's formatting
```

```powershell
scripts\quality.ps1
scripts\quality.ps1 -Fix
```

Both run **Ruff → Black → MyPy → Pytest**, in that order, stopping at the first
failure. That order is not arbitrary: lint errors are cheapest to fix, and a
type error usually explains a test failure that would otherwise be debugged
blind.

The two scripts and the `quality` job in `.github/workflows/ci.yml` must run
the same commands in the same order. **If they diverge, one of them is wrong** —
a local gate that is weaker than CI is worse than no local gate, because it
teaches you to trust a green run that means nothing.

## Rules for anything added here

1. **A script must be runnable from any working directory.** Both existing
   scripts `cd` to the repository root first.
2. **Exit codes are the interface.** Non-zero on failure, always. Scripts get
   called by CI and by hooks, neither of which reads prose.
3. **No credentials, and no defaults that stand in for one.** Scripts read the
   environment like everything else in this repository.
4. **A destructive script must say so and require confirmation.** There are
   none yet; the first one gets a `--yes` flag and refuses to act without it.
5. **Python scripts are linted like the rest of the repository.** `ruff.toml`
   permits `print()` here (`T201`) and nowhere else, because printing to stdout
   is the point of an operator script.
