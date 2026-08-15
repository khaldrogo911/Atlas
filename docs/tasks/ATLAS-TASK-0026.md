# ATLAS-TASK-0026 — Enforce the ADR-0016 broker startup validation boundary

**Status:** Specified, not implemented
**Date:** 2026-08-15
**Baseline:** `47c69f2f9eaa26f0fd4cdef4cfaeea4c79eb665b`
**Decision record:** [ADR 0016](../adr/0016-unusable-broker-configuration-refuses-startup.md) —
*Unusable broker configuration refuses startup; the terminal path is not
probed* (Proposed, 2026-08-15).

This task implements ADR-0016 and nothing else. ADR-0016 decided that broker
configuration which cannot open a session is refused where the session is
assembled, and that the refusal is confined to properties holding
independently of the machine performing the validation. It issued four
verdicts on four fields: `login` and `server` unchanged, an empty `password`
refused in every environment, and `terminal_path` refused only when it is the
not-configured sentinel `Path(".")`.

This task adds those two invariants to `MT5Config` and proves them. It probes
no filesystem, adds no field, adds no environment variable, creates no error
type, changes no exit code, and moves no rule into `atlas.config`.

ADR-0016 named its site and left the mechanism open. This task settles the
mechanism, because a specification cannot be implemented without one.
Everything ADR-0016 left open stays open and is listed in §19.

`docs/ROADMAP.md` is not modified by this task. See §22.

---

## 1. Title

**ATLAS-TASK-0026 — Enforce the ADR-0016 broker startup validation boundary.**

---

## 2. Status

Specified, not implemented. No branch, pull request or CI run exists for the
implementation of this task, and none is cited anywhere in this document.

The baseline is `47c69f2f9eaa26f0fd4cdef4cfaeea4c79eb665b` on `main`, with a
clean working tree and level with `origin/main`. That commit indexed ADR-0016;
`843c12033d72528902723fc690174c984d0d1fed` specified it. The implementer must
confirm that state before making any change (§17.1).

At the baseline the full suite collects **3699 tests**: 217 in
`tests/contract`, 757 across the four package boundary tests, 227 in
`tests/unit/test_core_broker_boundary.py`, 86 in
`tests/unit/broker/mt5/test_mt5_connection.py`, 66 in
`tests/unit/test_config_settings.py`, 17 in
`tests/unit/test_core_broker_ownership.py`, 11 in
`tests/unit/test_core_composition.py` and 9 in
`tests/unit/test_core_entrypoint.py`.

### 2.1 The record this task implements is `Proposed`, not `Accepted`

Every previous ADR in this repository was `Accepted` before the task
implementing it was specified, and every previous task specification cites an
accepted record. ADR-0016 is `Proposed`, and the owner's decision was that it
remains so.

This is stated rather than smoothed over. The implementation authority for
this task is the owner's decision to implement ADR-0016 as written; it is not
an inference from the record's status, and it is not a licence to change that
status. **ADR-0016 is not edited by this task, and its status is not advanced
to `Accepted` by this task** (§20.2). If the repository's lifecycle requires
acceptance before or after implementation, that is a separate step performed by
the owner, and stop condition 12 applies if the implementer believes this task
cannot proceed without it.

---

## 3. Architectural authority

**ADR-0016 is the sole decision this task implements.** Its Decision reads:

> **Broker configuration that cannot open a session is refused where the
> session is assembled, and the refusal is confined to properties that hold
> independently of the machine performing the validation.**

Its four verdicts, and where this task discharges each:

| Field | ADR-0016 verdict | This task |
|---|---|---|
| `login` | "Nothing here changes either constraint, widens it or narrows it" | Untouched. §7.4, §18 AC-7 |
| `server` | as above | Untouched. §7.4, §18 AC-8 |
| `password` | "An empty password is refused, in every environment" | §7 |
| `terminal_path` | "The not-configured terminal path is refused, and nothing else about it is" | §8 |

ADR-0016 also fixes five properties that this task must preserve rather than
re-derive:

| Property | ADR-0016 | This task |
|---|---|---|
| No filesystem I/O in validation | "This is a rule of this record and not merely a consequence of the fields it declines to check" (`:113-114`) | §9 |
| The refusal already exists | "No new error surface, exit code, stream or record is created" (`:141`) | §10 |
| The site is `MT5Config` | "The rules belong to `MT5Config` … and not to `AtlasSettings._enforce_production_invariants`" (`:155-156`) | §12 BP-1, BP-2 |
| Credentials reach neither stream | "`SecretStr` masks in Pydantic's error output" (`:148-149`) | §11 |
| No new field or variable | "This record adds none. It constrains only values the existing four fields already accept" (`:257-258`) | §6.5, §18 AC-14 |

Four further ADRs constrain this task and none is amended, footnoted or
superseded by it: ADR-0003, ADR-0012, ADR-0013, ADR-0014 and ADR-0015. Their
bearing is set out in §21.

---

## 4. Problem statement

`MT5Config` refuses two of the four values a session cannot be opened without,
and accepts the other two in exactly the state that means nobody supplied
them.

```
BrokerSettings()  →  MT5Config(...)

  login          0            →  REFUSED   gt=0
  server         ""           →  REFUSED   min_length=1
  password       SecretStr('')→  accepted  ← opens nothing
  terminal_path  Path('.')    →  accepted  ← a directory, and the default
```

The consequence is a deployment that sets `ATLAS_BROKER__LOGIN` and
`ATLAS_BROKER__SERVER`, leaves the other two unset, starts cleanly, emits its
startup record, exits `0`, and could never have traded. ADR-0015 decided that
such a process must not start; it did not add the invariant that would stop
it.

ATLAS-TASK-0023 named this precisely and declined to close it. Its **§15**
recorded, as verified evidence, that "an empty password and `terminal_path='.'`
are accepted", and its **§21.2** listed "the unusable-but-accepted
configuration gap" as a gap "recorded, not closed", because closing it "means
adding a validation rule, which is a new invariant and a new configuration
requirement" that ADR-0015 forbade. ADR-0016 has now added exactly that
invariant, and only that one.

**The problem this task removes is that two not-configured broker values are
accepted as configuration.** It does not remove the absence of a run loop, a
supervisor, a session, or any guarantee that a started process can reach its
terminal, and it must not appear to.

---

## 5. Scope

This task adds two field constraints to one model, proves them at the model
and at the process entrypoint, proves that validation touches no filesystem,
and corrects the one deployer-facing statement the change falsifies.

In scope:

1. **S-1.** `packages/broker/src/atlas/broker/mt5/connection.py` — a
   `min_length=1` constraint on `MT5Config.password` (§7) and a field
   validator rejecting the `Path(".")` sentinel on `MT5Config.terminal_path`
   (§8).
2. **S-2.** `tests/unit/broker/mt5/test_mt5_connection.py` — new cases in the
   existing `TestConfig` class, beside the `login` and `server` cases already
   there. §15.1.
3. **S-3.** `tests/unit/test_core_composition.py` — new cases proving the
   refusal reaches `ConfigurationError` through the existing translation.
   §15.2.
4. **S-4.** `tests/unit/test_core_entrypoint.py` — new cases proving the exit
   code, the streams and the credential silence. §15.3.
5. **S-5.** `.env.example` — the broker paragraph at lines 99-101 corrected so
   that it describes all four validation requirements. Authorised by the owner
   as an implementation documentation target. §14 DOC-2.
6. **S-6.** Nothing else.

Five files. If a sixth needs to change, §16 applies.

---

## 6. Non-goals

Each of these is out of scope because ADR-0016 leaves it open or forbids it,
not because it is merely unbuilt. Nothing in this task's diff may decide,
prepare for, or read as presuming any of them.

- **6.1 Any filesystem check.** Existence, executability, accessibility,
  readability, mount state, file type and size are each refused as invariants
  by ADR-0016 `:93-97`. §9.
- **6.2 Absoluteness.** `terminal_path.is_absolute()` is not called, asserted
  or required. ADR-0016 `:99-107` refuses it because it is platform-dependent
  and the shipped container is Linux. §13.
- **6.3 Platform-specific path validity.** No drive-letter check, no
  extension check, no `terminal64.exe` name check, no `PureWindowsPath`
  conversion.
- **6.4 Path normalisation.** No `resolve()`, `absolute()`, `expanduser()`,
  `as_posix()` or `os.path.normpath`. The value `BrokerSettings` resolved is
  the value `MT5Config` holds; ATLAS-TASK-0023 **TC-3** stays in force.
- **6.5 New configuration.** No new field on `BrokerSettings` or `MT5Config`,
  no new environment variable, no change to any default, no change to any
  file under `config/`.
- **6.6 A production-scoped rule.** The password invariant applies in every
  environment. `_enforce_production_invariants` is not touched, extended,
  called or referenced. §12 BP-2.
- **6.7 Password strength, length, character class or format.** The rule is
  non-empty. A minimum longer than one character would be a policy ADR-0016
  did not decide.
- **6.8 Authentication.** Whether the trade server accepts the password is not
  anticipated, cached, pre-checked or reported. ADR-0016 `:218-219`.
- **6.9 `server_utc_offset`, `timeout_ms`, `portable`.** All three keep their
  defaults and gain no constraint. ADR-0016 `:255-256`.
- **6.10 `BrokerOwner`, the run loop, supervision, health checks, reconnect
  and failover.** ADR-0016 `:243-245` withholds every one.
- **6.11 The execution consumer, risk composition and `PIPELINE_PACKAGES`.**
  ADR-0016 `:249-250`, `:286-288`.
- **6.12 A general `apps/` import rule.** ADR-0016 `:247-248`. No
  `PERMITTED_*` tuple, and no new import under `apps/` at all — this task adds
  none. §18 AC-17.
- **6.13 Any change to `apps/`.** Not one file, not one line. The refusal
  reaches `main()` through machinery ATLAS-TASK-0023 already built.
- **6.14 Any change to `packages/config`.** §12 BP-1.
- **6.15 ADR modification.** Every ADR is immutable once accepted
  (`docs/adr/README.md:4-6`), the index included, and ADR-0016 is not edited
  or re-statused regardless (§2.1, §20.2).
- **6.16 Task specification modification.** ATLAS-TASK-0023 §15 and §21.2
  become historical when this task merges. They are records of what was true
  when written and are not edited. ADR-0016 `:231-234`.
- **6.17 Unrelated architectural and documentation debt.** The one
  documentation correction this task carries is `.env.example`'s broker
  paragraph (§14 DOC-2), authorised because it describes the exact contract
  this task implements. Everything else stays where it is, and three are named
  because they are the ones an implementer will be tempted by while editing
  nearby prose: **the "owns the event loop" contradiction in the architecture
  documentation**, **any ADR-0011 inaccuracy**, and **general architecture or
  run-loop questions**. None is touched here. They are real, they are separate
  work, and a task that fixes them in passing makes its own diff impossible to
  review against ADR-0016. §14 DOC-1, §20.2.
- **6.18 Roadmap bookkeeping.** §22.

---

## 7. Decision A — the password invariant

### 7.1 The rule

`MT5Config.password` must not be empty. The rule applies in every
environment.

### 7.2 The mechanism

A declarative constraint on the existing field, in the idiom the neighbouring
field already uses:

```python
password: SecretStr = Field(
    min_length=1, description="Account password, held so it cannot be logged."
)
```

- **PW-1.** `min_length=1`, not a `field_validator`. Verified in §13: Pydantic
  2.13 applies `min_length` to a `SecretStr` through its length protocol and
  rejects `SecretStr("")` with `too_short`. The constraint therefore reads the
  same way as `server: str = Field(min_length=1)` three lines below it, which
  is what makes the two refusals visibly the same kind of thing — the point
  ADR-0016 `:68-70` makes in prose.
- **PW-2.** The description is unchanged.
- **PW-3.** No other constraint. No `max_length`, no `pattern`, no
  strip-whitespace, no strength rule. §6.7.
- **PW-4.** A password of `" "` — one space — is accepted. It is a value
  somebody supplied, not an absent one, and refusing it would be the
  format policy §6.7 excludes. The distinction ADR-0016 `:125-131` draws is
  between *not configured* and *configured but wrong*, and a space is the
  second.

### 7.3 The error the rule produces

Pydantic reports `too_short` at location `password`. Verified in §13, the
rendered message is:

```
password
  Value should have at least 1 item after validation, not 0
  [type=too_short, input_value=SecretStr(''), input_type=SecretStr]
```

- **PW-5.** The field name `password` appears; the credential does not.
- **PW-6.** **Tests assert on the field name and the exception type, never on
  Pydantic's wording.** "at least 1 item after validation" is Pydantic's
  phrasing for a length constraint on a non-`str` type and may change across
  releases. A test that pins it fails on a dependency bump and reports it as a
  broker-configuration defect. The existing `login` and `server` cases match
  on `"greater than 0"` and `"at least 1 character"` because those are stable
  core-schema messages; this one is not treated the same way, deliberately.

### 7.4 What is not touched

`login` keeps `gt=0`. `server` keeps `min_length=1`. Neither constraint is
widened, narrowed, restated, moved or re-described. ADR-0016 `:60-61`: "Any
description of them elsewhere that is more generous than this paragraph is
wrong."

---

## 8. Decision B — the terminal-path invariant

### 8.1 The rule

`MT5Config.terminal_path` is refused when, and only when, it equals
`Path(".")`.

### 8.2 The mechanism

`Path(".")` is not expressible as a `Field` constraint, so this one rule
introduces the model's first validator:

```python
@field_validator("terminal_path")
@classmethod
def _reject_the_unconfigured_path(cls, value: Path) -> Path:
    if value == Path("."):
        msg = "terminal_path is not configured"
        raise ValueError(msg)
    return value
```

- **TP-1.** The comparison is `== Path(".")`. Not `str(value) == "."`, not
  `value.name == ""`, not a truthiness test. §13 verifies that `Path` collapses
  `"."`, `""`, `"./"`, `".//"` and `".\"` to the same object, so one equality
  catches every spelling of the sentinel including the empty string, on both
  path flavours.
- **TP-2.** `".."` and `"a/.."` are **accepted**. §13 verifies neither equals
  `Path(".")`. They are odd, and they are values somebody chose; refusing them
  would require reasoning about what a path resolves to, which is §6.4.
- **TP-3.** The validator's body is the comparison, the raise and the return.
  It calls nothing on the filesystem, imports nothing, logs nothing and
  normalises nothing. §9.
- **TP-4.** `field_validator` is imported from `pydantic` on the existing
  import line (`connection.py:52`). No new dependency; `pydantic` is already
  the module's import.
- **TP-5.** The validator is private, `_`-prefixed, and not listed in
  `__all__` or referenced outside the class.
- **TP-6.** The field's `description` is unchanged. It still says "Absolute
  path to terminal64.exe", and that remains an operator's obligation rather
  than an enforced invariant — ADR-0016 `:103-107` states exactly this and
  declines to promote it.

### 8.3 The error the rule produces

Pydantic wraps a validator's `ValueError` as `value_error` at location
`terminal_path`, rendering `Value error, terminal_path is not configured`.

- **TP-7.** The field name appears in the error, which is what the entrypoint
  test asserts on.
- **TP-8.** The rendered `input_value` is a path, not a credential. It is the
  value the deployment supplied, and reporting it is what lets a deployer see
  which value to fix.

### 8.4 Why the sentinel and not the field's absence

`BrokerSettings.terminal_path` has a default of `Path()`. A process that never
sets `ATLAS_BROKER__TERMINAL_PATH` therefore presents a *value*, not a missing
key, and `MT5Config` cannot distinguish "defaulted" from "explicitly set to
`.`" — nor should it need to, because both mean the same thing. §13 verifies
`BrokerSettings().terminal_path == Path(".")`, which is what makes the
sentinel rule catch the unconfigured deployment.

---

## 9. Decision C — no filesystem I/O

**Configuration validation performs no filesystem I/O.** ADR-0016 `:113-114`
states this as a rule of the record rather than as a consequence of the fields
it declines to check, and this task must prove it rather than assert it.

- **FS-1.** No call to `Path.exists`, `is_file`, `is_dir`, `stat`, `lstat`,
  `resolve`, `open`, `iterdir`, `glob`, `owner`, `samefile` or `absolute`
  anywhere in `MT5Config` or its validators.
- **FS-2.** No call to `os.stat`, `os.access`, `os.path.exists`,
  `os.path.isfile`, `os.path.realpath` or `builtins.open`.
- **FS-3.** No import of `shutil`, `subprocess`, `platform` or `sys.platform`
  branching in the validation path.
- **FS-4.** The proof is §15.4, and it has two halves: a runtime half that
  intercepts the syscall layer while a valid `MT5Config` is constructed, and a
  control proving the interception actually fires. **A patch that the
  implementation never reaches passes vacuously; the control is what makes the
  test evidence.** This is the requirement the authorisation stated as "do not
  create tests that merely mock a filesystem call that the implementation does
  not make".

---

## 10. Decision D — failure semantics are unchanged

Nothing in this section is new work. It is the path the refusal travels, and
the task's obligation is to leave every step of it exactly as it is.

```
MT5Config(...)            raises pydantic.ValidationError
  ↓  composition.py:73-75 catches, raises ConfigurationError
  ↓  __main__.py          except ConfigurationError
  ↓                       stderr ← {"event": "atlas.core.startup_failed", ...}
  ↓                       stdout ← nothing
  ↓                       return EXIT_CONFIG_ERROR   (2)
```

- **FC-1.** **No new exception type.** The two new refusals raise the same
  `pydantic.ValidationError` that `login` and `server` already raise.
- **FC-2.** **No new exit code.** `EXIT_CONFIG_ERROR` is 2 and stays 2.
- **FC-3.** **No new event name.** `atlas.core.startup_failed` is reused
  verbatim.
- **FC-4.** **`composition.py` is not modified.** Its `except
  PydanticValidationError` already narrows every `MT5Config` rejection, and
  its message prefix already names `broker`. A refusal added in
  `packages/broker` reaches `main()` with no change under `apps/` at all.
- **FC-5.** **No adapter, owner or session is created on the failing path.**
  `MT5Config(...)` raises inside `build_broker_owner`'s `try`, before
  `MT5BrokerAdapter(config)` and before `BrokerOwner(...)` are reached
  (`composition.py:66-77`). This is a property of the existing statement
  order, and §15.2 pins it.
- **FC-6.** Translation still precedes the startup record, so stdout stays
  empty on the failing path.

---

## 11. Security and secret handling

- **SEC-1.** `SecretStr` stays. The field's type is unchanged.
- **SEC-2.** `get_secret_value()` is not called in `packages/broker/src`, and
  not added anywhere under `apps/`. ATLAS-TASK-0023's `grep -rn
  "get_secret_value" apps/` check stays clean (§17.4).
- **SEC-3.** The password is not interpolated into any message, docstring,
  comment, log line or exception. The `min_length` mechanism is chosen partly
  because it constructs no message from the value at all.
- **SEC-4.** §13 verifies that Pydantic renders a rejected `SecretStr` as
  `SecretStr('')` when empty and `SecretStr('**********')` when non-empty and
  too short — the value never reaches the rendered error in either case.
- **SEC-5.** Tests use a sentinel named for what it is, following the
  established convention at `test_core_composition.py:36-38`: a constant
  called `SENTINEL`, not `PASSWORD`, so the line is not a hardcoded-credential
  finding in every scanner.
- **SEC-6.** `tests/unit/risk/test_risk_boundary.py` is not modified.

---

## 12. Boundary preservation

- **BP-1.** `packages/config/**` is not modified. Not one file, not one line.
  `atlas.config` gains no knowledge of what a MetaTrader session requires,
  which is ADR-0014 held exactly as ADR-0016 `:276-281` requires.
- **BP-2.** `AtlasSettings._enforce_production_invariants` is not modified,
  extended or referenced. The mechanical proof is that
  `tests/unit/test_config_settings.py::TestBrokerConfigurationSources::test_production_starts_with_no_broker_configuration`
  passes **unmodified**: it is "the pin that stops a broker production
  invariant arriving by accident", it asserts that `load_settings()` resolves
  in production with no broker configuration at all, and it fails if a broker
  invariant is ever added to the settings layer. Its continuing to pass is the
  difference between implementing ADR-0016 and implementing the alternative
  ADR-0016 rejected.
- **BP-3.** `apps/**` is not modified. §6.13.
- **BP-4.** No `atlas.config → atlas.broker` import edge is created.
- **BP-5.** `PIPELINE_PACKAGES` at `tests/unit/test_core_broker_boundary.py:73`
  is unchanged, and that file is not modified at all — this task adds no
  module and no import under `apps/`, so no scanner's premise moves.
- **BP-6.** `tests/contract` reports exactly 217 and is unchanged. No source
  file is added, removed or renamed.
- **BP-7.** The four package boundary tests report exactly 757 and are
  unchanged.
- **BP-8.** `pyproject.toml`, `.github/workflows/ci.yml`, `Dockerfile`,
  `docker-compose.yml`, `config/**` and `scripts/**` are not modified. No new
  dependency, source root, job, marker or script.
- **BP-9.** `docker-compose.yml`'s `restart: "no"` and its comment stay
  correct without edit. ADR-0016 `:209-211` observes that the comment becomes
  true of one further class of configuration, which requires no change to its
  wording.

---

## 13. Verified evidence this specification rests on

Each of these was measured against the baseline on this host, not inferred. An
implementer who finds any of them false has hit stop condition 10 or 11.

**`MT5Config` accepts all four unusable values today.** Constructing it with
`password=SecretStr("")` succeeds; with `terminal_path=Path(".")` succeeds;
with `Path("")` succeeds; with a non-existent path succeeds; with a relative
path succeeds.

**`BrokerSettings()` resolves to exactly the not-configured four.**
`login=0`, `password=SecretStr('')`, `server=''`, and
`terminal_path == Path('.')` is `True`.

**`Path` collapses every spelling of the sentinel.** `Path(".")`, `Path("")`,
`Path("./")`, `Path(".//")` and `Path(".\")` all compare equal to `Path(".")`.
`Path("..")` and `Path("a/..")` do not, and `Path("terminal64.exe")` does not.

**`min_length` constrains a `SecretStr`, and does not leak it.** Under Pydantic
2.13, `Field(min_length=1)` on a `SecretStr` rejects `SecretStr("")` with
`type=too_short` and renders `input_value=SecretStr('')`. A `min_length=8`
field rejecting a four-character secret renders
`input_value=SecretStr('**********')` — the value is absent from the message in
both cases.

**Absoluteness is platform-dependent, which is why §6.2 exists.** For
`"C:/Program Files/MetaTrader 5/terminal64.exe"`, `PureWindowsPath.is_absolute()`
is `True` and `PurePosixPath.is_absolute()` is `False`. `atlas-core` ships in
`python:3.12-slim-bookworm` (`Dockerfile:49`), so an absoluteness invariant
would reject correct production configuration inside the container this
repository builds.

**`MT5Config` currently has no validator.** `connection.py:52` imports
`BaseModel, ConfigDict, Field, SecretStr` and nothing else from `pydantic`;
there is no `field_validator`, `model_validator` or `@validator` in the file.
The validator in §8.2 is the model's first.

**No existing test constructs an `MT5Config` this task would newly reject.**
All eight construction sites — `tests/unit/broker/mt5/conftest.py:421`, four in
`test_mt5_connection.py`, two in `test_adapter_heartbeat.py`, one each in
`test_adapter_retry.py` and `test_base_adapter.py` — pass a non-empty password
and a `terminal_path` that is not the sentinel. `test_the_offset_defaults_to_utc`
uses the *relative* path `Path("terminal64.exe")`, which §8 continues to
accept; had this task required absoluteness, that test would have broken, which
is a second reading of the same evidence.

**No existing test asserting startup success omits any of the four values.**
`test_core_entrypoint.py`'s `configured_broker` fixture and
`test_core_composition.py`'s `broker_env` fixture each set all four. Every
test that omits one already expects `EXIT_CONFIG_ERROR`. **This task therefore
modifies no pre-existing test** (§15.5); if one appears to require
modification, stop condition 6 applies.

---

## 14. Required documentation truths

After implementation these must be true, and the implementer must not create
them by editing a document this task forbids (§20.2):

- **DOC-1.** **`docs/architecture/overview.md` requires no change, and must
  not receive a cosmetic one.** This was checked rather than assumed: the file
  names no broker field anywhere, and its startup sentence at `:194-198` —
  "configuration it cannot resolve, or a broker section it cannot translate,
  leaves stdout empty and exits `2` instead" — describes the behaviour after
  this task as accurately as before it, because two more values now fall under
  "cannot translate". `:120-121` is likewise unaffected. The authorisation
  permitted an overview correction "only where required"; the evidence is that
  none is required, and the correct discharge of that permission is to make no
  edit. **The owner reviewed this finding and declined the change**, directing
  that the permission not be consumed merely because it was granted. AC-20 is
  therefore satisfied by the absence of an architecture-overview change, not
  by an edit.
- **DOC-2.** **`.env.example` is an authorised implementation documentation
  target, and its broker paragraph must describe all four requirements.** The
  text at `:99-101` reads: "All four are required. Start-up builds the trading
  adapter these values describe, and a login of 0 or an empty server name is
  rejected there, so a process without usable ones exits 2 before it reports
  anything else." After this task all four values are rejected there, not two.
  A deployer who uncomments the block and leaves `ATLAS_BROKER__PASSWORD=`
  empty will fail startup while this file tells them only `login` and `server`
  are checked. The precedent is ATLAS-TASK-0023 §16 DOC-1, which corrected
  these same three lines for the same reason: "this file is instruction to a
  deployer rather than commentary — shipping a false one is a configuration
  hazard, not documentation drift." The requirements on the correction are
  DOC-2.1 through DOC-2.4 below, and they are binding.
- **DOC-2.1 — what it must say.** The corrected paragraph must state each of
  the four requirements accurately: `login` must be greater than `0`; `server`
  must be non-empty; `password` must be non-empty; and `terminal_path` must be
  configured rather than left at the `Path(".")` sentinel. All four are
  rejected at start-up, and a process without usable ones exits `2` before it
  reports anything else.
- **DOC-2.2 — what it must not say.** The corrected text must not state or
  imply that `terminal_path` is required to be **absolute**, to **exist**, to
  be **executable**, to be **filesystem-accessible**, or to be **valid for the
  platform** at configuration time. Each of those is refused as an invariant by
  ADR-0016 `:93-97`, and a deployer instruction that promises them would be
  false in the opposite direction — describing a check the process does not
  perform. This is DOC-3 applied to the one file this task edits, and AC-28
  proves it mechanically.

  One case is ruled on explicitly because it will otherwise be argued both
  ways. The placeholder at `:113` reads
  `# ATLAS_BROKER__TERMINAL_PATH=/absolute/path/to/your/trading-terminal`.
  **It stays exactly as it is.** An example showing an absolute path is the
  operator's obligation being illustrated, which ADR-0016 `:103-107` and
  `:220-221` keep as an obligation stated in the field's description; it is not
  prose claiming the validator enforces absoluteness. DOC-2.2 governs what the
  paragraph *asserts about validation*, not what an example value looks like.
  An implementer must neither rewrite this placeholder to a relative path nor
  cite it as a DOC-2.2 violation.
- **DOC-2.3 — what it must not do.** No new environment variable is added. No
  existing variable is renamed. The block's structure, its commented-out
  examples at `:111-113` and `:117`, its ordering, the password note at
  `:115-116`, and the `docker compose config` paragraph at `:103-109` are left
  alone. **The edit is confined to the paragraph that is wrong; this task is
  not a licence to restructure or tidy `.env.example`.**
- **DOC-2.4 — what stays true.** The four values still ship commented out, are
  still set only in the process environment, and are still absent from every
  layer under `config/`. ADR-0003 is untouched (§21), and no credential value
  appears in the file.
- **DOC-3.** No statement is added anywhere claiming that the terminal path is
  validated, checked, verified or probed; that a started process can reach its
  terminal; that the password is correct; or that a session is opened. None of
  the four is true after this task.
- **DOC-4.** `config/README.md` is not modified. Its rules already cover the
  broker section without amendment, and no field changes.
- **DOC-5.** `docs/ROADMAP.md:1368` states that "`0` and an empty server name
  are the not-configured values". That sentence becomes incomplete when this
  task merges. It is roadmap prose about a completed task, §22 excludes the
  roadmap from this task, and it is recorded in §19.3 rather than fixed here.

---

## 15. Test requirements

**No pre-existing test is modified, renamed, moved, deleted or
re-parameterised.** §13 establishes that none needs to be; §16 stop condition 6
covers the case where the implementer finds otherwise.

### 15.1 The model — `tests/unit/broker/mt5/test_mt5_connection.py`

New cases in the existing `TestConfig` class, beside
`test_an_impossible_account_number_is_rejected` and
`test_an_empty_server_name_is_rejected`, which they are deliberately shaped
after.

- **M-1.** An empty password is rejected. Asserts `ValidationError` and that
  the error names `password`; does **not** match on Pydantic's wording
  (§7.3 PW-6). *(AC-1)*
- **M-2.** `terminal_path=Path(".")` is rejected, and the error names
  `terminal_path`. *(AC-2)*
- **M-3.** The sentinel's other spellings are rejected too, parameterised over
  `"."`, `""`, `"./"` — the spellings §13 verifies collapse to `Path(".")`.
  This is what proves TP-1 was implemented as an equality on the normalised
  value rather than as a string comparison.
- **M-4.** A non-empty password is accepted when the other three values are
  valid. *(AC-3)*
- **M-5.** A single-space password is accepted. §7.2 PW-4 — the test that
  catches a strength rule arriving by accident.
- **M-6.** `terminal_path="C:/Program Files/MetaTrader 5/terminal64.exe"` is
  accepted, and the assertion is written so that it holds on POSIX, where that
  string is a *relative* path. **This is the test that fails if an absoluteness
  requirement is ever introduced**, and it must be able to run on the Linux CI
  runner, which is the host that matters here. *(AC-4)*
- **M-7.** A path that does not exist is accepted. Use a path that certainly
  does not exist on either flavour, and assert the constructed
  `config.terminal_path` equals what was passed — proving the value was neither
  rejected nor normalised (§6.4). *(AC-5)*
- **M-8.** `Path("..")` is accepted. TP-2 — the boundary of the sentinel rule,
  and the test that catches it being widened to "any relative path" or "any
  path without a filename".
- **M-9.** `login=0` is still rejected, and `login=-1` with it. The existing
  parameterised case already asserts this and is not modified; M-9 is
  satisfied by that test continuing to pass. *(AC-7)*
- **M-10.** `server=""` is still rejected. As M-9, by the existing test.
  *(AC-8)*

### 15.2 The translation — `tests/unit/test_core_composition.py`

New cases in the existing
`TestTheTranslationRefusesWhatCannotOpenASession` class, shaped after
`test_an_unset_login_is_refused_and_the_field_is_named`.

- **C-1.** A process with `login`, `server` and `terminal_path` set and no
  password raises `ConfigurationError`, and the message names both `broker`
  and `password`.
- **C-2.** A process with `login`, `password` and `server` set and no terminal
  path raises `ConfigurationError`, and the message names both `broker` and
  `terminal_path`.
- **C-3.** With a sentinel password set and the terminal path unset — so the
  failure sees a real credential and rejects a different field — the raised
  message contains neither the sentinel nor the string `SecretStr(`.
  *(AC-10, at the translation)*
- **C-4.** On the C-1 path, no adapter and no owner are constructed. Assert by
  patching `MT5BrokerAdapter` and `BrokerOwner` as they are named in
  `atlas.apps.core.composition` with objects that fail the test if called,
  then confirming `ConfigurationError` is still raised. Include the control:
  the same patches on a *valid* configuration must record that both were
  called, or the test proves only that patching happened. *(AC-11, AC-12)*
- **C-5.** On the C-1 path no session is opened: `MetaTrader5` is absent from
  `sys.modules` afterwards. The existing fresh-interpreter probe at
  `test_core_composition.py:218-248`, with its control, is the pattern to
  follow. *(AC-13)*

### 15.3 The entrypoint — `tests/unit/test_core_entrypoint.py`

New cases in the existing
`TestStartUpNeedsABrokerSectionASessionCouldBeOpenedFrom` class.

- **E-1.** A process configured except for its password returns
  `EXIT_CONFIG_ERROR`, writes **nothing** to stdout, and writes one
  `atlas.core.startup_failed` JSON object to stderr whose `error` names
  `broker` and `password`. *(AC-9)*
- **E-2.** The same for a process configured except for its terminal path,
  naming `terminal_path`. *(AC-9)*
- **E-3.** With a sentinel password supplied and the terminal path unset, the
  sentinel appears on neither stdout nor stderr. *(AC-10)*
- **E-4.** With all four supplied, `main()` still returns `EXIT_OK` and the
  record still has exactly the eight `RECORD_KEYS` and no `broker` key. The
  existing `test_a_configured_broker_adds_nothing_to_the_startup_record`
  already asserts this and is not modified; E-4 is satisfied by it continuing
  to pass.

### 15.4 No filesystem I/O — where it belongs

**Site.** `tests/unit/broker/mt5/test_mt5_connection.py`, in `TestConfig`,
beside the rules it is about. The invariant is a property of `MT5Config`, not
of the application, so it is asserted where the model is.

- **F-1.** *(runtime)* Construct a **valid** `MT5Config` — including a
  terminal path that does not exist — inside a context that replaces the
  syscall layer with functions that raise: at minimum `os.stat`, `os.lstat`,
  `os.access` and `builtins.open`. `pathlib` delegates `exists`, `is_file`,
  `is_dir`, `stat` and `resolve` to those, so patching them covers the
  surface FS-1 and FS-2 name without enumerating every `Path` method.
  Construction must succeed. *(AC-6, AC-16)*
- **F-2.** *(the control, mandatory)* Inside the same patched context, call
  `Path("anything").exists()` and assert that it raises. **Without this, F-1
  passes whether or not the patches are reachable, and proves nothing.**
  ADR-0016 makes a claim about what the code does not do; the only honest
  proof is an instrument shown to fire.
- **F-3.** Scope the patching to the construction call alone, not to the whole
  test function and not to a fixture. `pytest`'s own machinery reads files
  during assertion rewriting and reporting, and a broadly-scoped patch turns a
  clean failure into a confusing one.
- **F-4.** *(static)* Assert that the source of `MT5Config` and its validators
  contains no call to any name in FS-1 or FS-2. Read the class's source with
  `inspect.getsource` and walk it with `ast`, following the scanner idiom
  `test_core_broker_boundary.py` establishes. Include a can-fire case: the
  same scanner run over a small module that *does* call `Path.exists` must
  report it. A scanner that cannot be shown to fail is not a test.

### 15.5 What must still pass, unmodified

- **T-1.** `tests/unit/test_config_settings.py` — 66 tests, byte-identical, and
  in particular `test_production_starts_with_no_broker_configuration` (§12
  BP-2).
- **T-2.** `tests/contract/test_repository_structure.py` — 217, unchanged, and
  still 217.
- **T-3.** The four package boundary tests — 757, unchanged.
- **T-4.** `tests/unit/test_core_broker_boundary.py` — 227, byte-identical.
- **T-5.** `tests/unit/test_core_broker_ownership.py` — 17, byte-identical.
- **T-6.** Every pre-existing test in the three files this task adds to,
  including all four `TestConnecting` fixtures that build a session from the
  `config` fixture.

---

## 16. Stop conditions

Stop and report rather than deciding, if:

1. **A filesystem check appears necessary** to make any test pass. §6.1.
   ADR-0016 forbids it as a rule, not as a preference.
2. **An absoluteness or platform check appears necessary.** §6.2, §6.3.
3. **`min_length` turns out not to constrain `SecretStr`** in the installed
   Pydantic, contradicting §13. Report the observed behaviour; do not
   substitute a `field_validator` that builds a message from the value.
4. **A rejection message is found to contain the password** on any path.
   §11. This is a stop, not a fix-and-continue.
5. **`packages/config` or `apps/` requires modification.** §12 BP-1, BP-3.
   A refusal that cannot reach `main()` without changing `composition.py`
   contradicts FC-4 and the evidence in §10.
6. **Any pre-existing test appears to require modification**, contradicting
   §13. Report which test and which of §13's statements it falsifies.
7. **`_enforce_production_invariants` appears to be the right site.** §12
   BP-2. ADR-0016 `:155-161` decided against it on ADR-0014 grounds.
8. **A password rule stronger than non-empty appears necessary.** §6.7.
9. **The sentinel rule appears to need widening** — to relative paths, to
   directories, to paths without a suffix. §8.2 TP-2.
10. **The baseline has moved** from
    `47c69f2f9eaa26f0fd4cdef4cfaeea4c79eb665b`, or ADR-0016 is absent, edited,
    or no longer `Proposed`.
11. **The collected test count before any change is not 3699.**
12. **The `Proposed` status of ADR-0016 appears to block implementation.**
    §2.1. This is the owner's call, not the implementer's.
13. **Anything in §6 or §19 would be decided in passing** to finish the work.

In every case: report both pieces of conflicting evidence and explain the
conflict. Do not silently reconcile them.

---

## 17. Verification commands

Existing tooling only. No new script, target, marker or CI job is added.

### 17.1 Before making any change

```bash
git rev-parse HEAD                      # 47c69f2f9eaa26f0fd4cdef4cfaeea4c79eb665b
git status --porcelain                  # empty
./.venv/Scripts/python.exe -m pytest -q --collect-only | tail -1   # 3699 tests
```

### 17.2 After implementation

```bash
./.venv/Scripts/python.exe -m pytest -q

./.venv/Scripts/python.exe -m pytest tests/contract -q                       # 217
./.venv/Scripts/python.exe -m pytest \
  tests/unit/broker/test_adapter_contract.py \
  tests/unit/risk/test_risk_boundary.py \
  tests/unit/strategy/test_strategy_boundary.py \
  tests/unit/execution/test_execution_boundary.py -q                         # 757
./.venv/Scripts/python.exe -m pytest tests/unit/test_config_settings.py -q   # 66
./.venv/Scripts/python.exe -m pytest tests/unit/test_core_broker_boundary.py -q   # 227
./.venv/Scripts/python.exe -m pytest tests/unit/test_core_broker_ownership.py -q  # 17
./.venv/Scripts/python.exe -m pytest tests/unit/broker/mt5/test_mt5_connection.py -q
./.venv/Scripts/python.exe -m pytest tests/unit/test_core_composition.py -q
./.venv/Scripts/python.exe -m pytest tests/unit/test_core_entrypoint.py -q

./.venv/Scripts/python.exe -m ruff check .
./.venv/Scripts/python.exe -m black --check --diff .
./.venv/Scripts/python.exe -m mypy .
```

### 17.3 Diff verification

```bash
git diff --stat -- packages/config/ apps/ config/                    # empty
git diff --stat -- docs/ .github/ pyproject.toml scripts/            # empty
git diff --stat -- Dockerfile docker-compose.yml                     # empty
git diff -- tests/unit/test_config_settings.py                       # empty
git diff -- tests/unit/test_core_broker_boundary.py                  # empty
git diff -- tests/unit/test_core_broker_ownership.py                 # empty
git diff -- tests/contract/                                          # empty
git diff --stat -- packages/                # connection.py only
git diff --stat -- .env.example             # expected: one paragraph
```

The `.env.example` diff is the one entry in this section that is **not**
expected to be empty. It must touch only the paragraph DOC-2 names, add no
line beginning `# ATLAS_`, and remove none.

```bash
git diff -U0 -- .env.example | grep -c '^[+-]# ATLAS_'                # 0
```

### 17.4 Secret and probe verification

```bash
grep -rn "get_secret_value" apps/                            # no matches
grep -rn "get_secret_value" packages/broker/src/             # no matches
grep -rnE "\.(exists|is_file|is_dir|resolve|stat|absolute)\(" \
  packages/broker/src/atlas/broker/mt5/connection.py         # no matches
grep -rn "is_absolute" packages/                             # no matches
```

### 17.5 Documentation verification

The variable names are unchanged and none is added — four matches, the same
four as at the baseline:

```bash
grep -c '^# ATLAS_BROKER__' .env.example                     # 4
grep -n 'ATLAS_BROKER__' .env.example
```

The corrected paragraph names each of the four requirements (DOC-2.1), and
claims none of the refused properties (DOC-2.2). The second check is run
against the **prose of the broker block**, excluding the `:113` placeholder
that DOC-2.2 rules on explicitly:

```bash
awk '/^# Broker —/{f=1} f && /^# ATLAS_BROKER__/{exit} f' .env.example | \
  grep -inE 'absolute|exist|executable|accessible|readable|installed|platform'
                                                             # no matches
```

The block is extracted by its header and terminated at the first variable line
rather than by line number, so the check survives the paragraph changing
length — which it will.

A match is not automatically a defect — it is a sentence to read against
DOC-2.2 and either rewrite or justify. It is written this way because a
greppable tripwire that an implementer must answer to is worth more here than
a wording rule nobody checks.

---

## 18. Acceptance criteria

AC-1 through AC-20 are the owner's required coverage, kept at their original
numbers so the mapping is auditable. AC-21 through AC-26 are the mechanical
checks this specification adds. AC-27 through AC-29 are the documentation
criteria the owner added when authorising `.env.example` as an implementation
target; they are numbered after the existing set so that no earlier number
moves.

- **AC-1.** An empty broker password is rejected by `MT5Config`. §15.1 M-1.
- **AC-2.** The unconfigured `terminal_path` sentinel `Path(".")` is rejected.
  §15.1 M-2, M-3.
- **AC-3.** A non-empty password is accepted when all other required values
  are valid. §15.1 M-4.
- **AC-4.** `C:/Program Files/MetaTrader 5/terminal64.exe` is accepted even
  when validation executes under POSIX, proving no absolute-path requirement
  was introduced. §15.1 M-6.
- **AC-5.** A path that does not exist is not rejected by configuration
  validation. §15.1 M-7.
- **AC-6.** Configuration validation performs no filesystem I/O, proven by an
  instrument shown to fire. §15.4 F-1, F-2, F-4.
- **AC-7.** `login <= 0` continues to fail, by the existing unmodified test.
  §15.1 M-9.
- **AC-8.** `server == ""` continues to fail, by the existing unmodified test.
  §15.1 M-10.
- **AC-9.** For both new failures the process exits `2`, `startup_failed` is
  emitted on stderr, and stdout remains empty. §15.3 E-1, E-2.
- **AC-10.** No credential value appears on stdout or stderr, or in any raised
  message. §15.2 C-3, §15.3 E-3.
- **AC-11.** No `MT5BrokerAdapter` is constructed when `MT5Config` validation
  fails. §15.2 C-4.
- **AC-12.** No `BrokerOwner` is constructed when `MT5Config` validation
  fails. §15.2 C-4.
- **AC-13.** No session is opened when `MT5Config` validation fails. §15.2
  C-5.
- **AC-14.** No new configuration field or environment variable is introduced.
  `BrokerSettings` and `MT5Config` have the same field names, in the same
  order, as at the baseline; `.env.example` gains no variable; `config/**` is
  unchanged.
- **AC-15.** `AtlasSettings._enforce_production_invariants` is unchanged, and
  `test_production_starts_with_no_broker_configuration` passes unmodified.
  §12 BP-2.
- **AC-16.** No filesystem probing is introduced, by the greps in §17.4 and
  the scanner in §15.4 F-4.
- **AC-17.** No new import is introduced under `apps/` — `git diff --stat --
  apps/` is empty.
- **AC-18.** ADR-0014, ADR-0015, every other ADR, and every file under
  `docs/tasks/` other than this one are untouched: `git diff --stat --
  docs/adr/ docs/tasks/` is empty.
- **AC-19.** The diff decides nothing about `BrokerOwner` lifecycle, the run
  loop, supervision, health checks, reconnect/failover, execution
  consumption, risk composition or the general `apps/` import rule — including
  in a docstring, a comment, a `TODO` or a name.
- **AC-20.** The architecture documentation is corrected only where necessary,
  which §14 DOC-1 establishes is nowhere, and which the owner confirmed on
  review: `git diff --stat -- docs/architecture/` is empty. **This criterion is
  satisfied by the absence of a change, not by an edit.**
- **AC-21.** The full suite is green and collects 3699 + N. No pre-existing
  test is skipped, renamed, deleted or modified.
- **AC-22.** `ruff check .`, `black --check .` and `mypy .` are clean under the
  repository's strict configuration, with no `# type: ignore` added.
- **AC-23.** The diff under `packages/` touches exactly one file,
  `mt5/connection.py`, and within it exactly the `password` field, the
  `terminal_path` validator and the `pydantic` import line.
- **AC-24.** `MT5Config` remains `frozen=True`, `extra="forbid"`, and its
  `clock` property, `timeout_ms`, `portable` and `server_utc_offset` are
  unchanged.
- **AC-25.** The diff touches exactly the files §20.1 lists, and none of the
  paths §20.2 prohibits.
- **AC-26.** ADR-0016 still reads `**Status:** Proposed`.
- **AC-27.** **`.env.example` accurately describes all four broker
  startup-validation requirements.** Its broker paragraph states that `login`
  must be greater than `0`, that `server` must be non-empty, that `password`
  must be non-empty, and that `terminal_path` must be configured rather than
  left at its `Path(".")` default — and that a process without all four exits
  `2` at start-up. No requirement is omitted, and none is described more
  generously or more strictly than §7 and §8 implement. §14 DOC-2.1.
- **AC-28.** **`.env.example` claims no property of the terminal path that
  ADR-0016 refuses to validate.** The prose of the broker block asserts no
  requirement that the path be absolute, exist, be executable, be
  filesystem-accessible, or be valid for the platform, and describes no
  start-up check that the implementation does not perform. Verified by the
  extraction in §17.5, read against DOC-2.2; the `:113` placeholder is out of
  scope by DOC-2.2's explicit ruling. §14 DOC-2.2.
- **AC-29.** **The `.env.example` edit is confined to the paragraph that was
  wrong.** No `# ATLAS_` line is added or removed — `git diff -U0 --
  .env.example | grep -c '^[+-]# ATLAS_'` is `0` — `grep -c '^#
  ATLAS_BROKER__' .env.example` is still `4`, no variable is renamed, and the
  block's examples, ordering, password note and `docker compose config`
  paragraph are unchanged. §14 DOC-2.3, DOC-2.4; §17.5.

---

## 19. Deferred decisions and known gaps

### 19.1 What ADR-0016 left open, and what this task does with each

| ADR-0016 open item | This task |
|---|---|
| The mechanism of the password rule | **Resolved.** §7 — `Field(min_length=1)`. |
| The mechanism of the terminal-path rule | **Resolved.** §8 — a `field_validator` on an equality with `Path(".")`. |
| How "no filesystem I/O" is proved | **Resolved.** §15.4 — interception with a control, plus a source scan. |
| Whether the terminal path can be reached | **Open, permanently by this record.** §19.2. |
| Whether the password is correct | **Open.** Authentication is the server's verdict. |
| `BrokerOwner` lifecycle, the run loop, supervision | **Open.** §6.10. |
| Reconnect, failover, health checks | **Open.** §6.10. |
| Multiple adapters, venues or accounts | **Open.** ADR-0016 `:246`. |
| How risk obtains its limits | **Open.** ADR-0012's revisit condition stays satisfied and unexercised. |
| The general `apps/` import rule | **Open.** §6.12. |
| DI, registries, factories, service locators | **Open.** ADR-0016 `:251`. |
| External secrets mechanisms | **Open.** ADR-0003 governs unchanged. |
| Order lifecycle, routing, reconciliation | **Open.** ADR-0016 `:253`. |
| `server_utc_offset` | **Open.** §6.9. |

### 19.2 Gaps this task preserves, deliberately

- **The terminal path is still not known to be reachable.** A path that is
  absolute, well-formed and points at nothing still starts the process and
  fails at `connect()`. This is ADR-0016's decision, not an oversight: the
  check cannot be made portably or without I/O, and a validator that made it
  would be reporting the state of a filesystem rather than the validity of a
  configuration.
- **A wrong password still starts the process.** Only its absence is refused.
- **`server_utc_offset` is still unreachable through configuration.**
  Inherited unchanged from ATLAS-TASK-0022 §21.3 and ATLAS-TASK-0023 §21.2.
- **The discarded owner.** `build_broker_owner`'s result is still not retained,
  because no run loop and no downstream recipient exist. Unchanged by this
  task and not addressed by it.

### 19.3 Created by this task, and named here

- **ATLAS-TASK-0023 §15 and §21.2 become historical.** Its verified statement
  that "an empty password and `terminal_path='.'` are accepted" was true when
  written and is what this task changes. Task specifications are immutable
  records; the statement stands as written. ADR-0016 `:231-234`.
- **`docs/ROADMAP.md:1368` becomes incomplete.** §14 DOC-5. Roadmap
  bookkeeping, excluded by §22. This is now the **only** documentation
  statement this task knowingly leaves inaccurate; `.env.example` was the
  other, and the owner authorised its correction (§14 DOC-2).
- **A behavioural change for existing deployments.** A deployment that today
  starts with an empty password or an unset terminal path will stop starting.
  ADR-0016 `:227-230` calls this "the decision rather than a side effect", and
  places it in the roadmap when implemented.

---

## 20. Files expected to change

### 20.1 Expected

| Path | Change |
|---|---|
| `packages/broker/src/atlas/broker/mt5/connection.py` | `min_length=1` on `password`; a `field_validator` on `terminal_path`; `field_validator` added to the `pydantic` import. §7, §8. |
| `tests/unit/broker/mt5/test_mt5_connection.py` | New cases in `TestConfig`. §15.1, §15.4. |
| `tests/unit/test_core_composition.py` | New cases in the existing refusal class. §15.2. |
| `tests/unit/test_core_entrypoint.py` | New cases in the existing start-up class. §15.3. |
| `.env.example` | **Authorised.** The broker paragraph at lines 99-101, corrected to describe all four requirements. Nothing else in the file. §14 DOC-2.1–DOC-2.4; AC-27, AC-28, AC-29. |

Five files. If a sixth needs to change, §16 applies.

`.env.example` is the only documentation file in this list, and it is here
because it instructs a deployer rather than describing the system. The
architecture overview is not here: §14 DOC-1 found no correction was required,
and the owner confirmed that finding rather than spending the permission
(§20.2).

### 20.2 Prohibited

| Path | Why |
|---|---|
| `packages/config/**` | §12 BP-1. ADR-0014's boundary. Zero lines. |
| `packages/broker/**` other than `mt5/connection.py` | §20.1. One file. |
| `apps/**` | §6.13, §12 BP-3. The refusal reaches `main()` unaided. |
| `tests/unit/test_config_settings.py` | §12 BP-2 — this file passing unmodified *is* the proof. |
| `tests/unit/test_core_broker_boundary.py` | §12 BP-5. No module or import is added under `apps/`. |
| `tests/unit/test_core_broker_ownership.py` | Nothing about ownership changes. |
| `tests/unit/risk/test_risk_boundary.py` | §11 SEC-6. |
| The four package boundary test files | §12 BP-7. |
| `tests/contract/**` | §12 BP-6. |
| `config/**` | §6.5, §14 DOC-4. |
| `docs/adr/**` | ADRs are immutable; ADR-0016 is not edited or re-statused. §2.1, §6.15. |
| `docs/tasks/**` other than this file | §6.16. |
| `docs/architecture/**`, `overview.md` included | §14 DOC-1 — no correction is required, and the owner declined the change on review. AC-20 is satisfied by the empty diff. |
| `docs/ROADMAP.md` | §22. |
| `.env.example` outside the broker paragraph | §14 DOC-2.3. The file is an authorised target for one paragraph, not for tidying. |
| `Dockerfile`, `docker-compose.yml` | §12 BP-8, BP-9. |
| `pyproject.toml`, `.github/workflows/ci.yml`, `scripts/**` | §12 BP-8. |

---

## 21. Relationship to the ADRs

**Sixteen ADRs exist. This task implements one, and edits none.**

| ADR | Bearing on this task | Effect |
|---|---|---|
| ADR-0003 | Secrets live in the process environment; fail fast at start-up | Preserved. Requiring a password to be non-empty adds no file, field or route; `ATLAS_BROKER__PASSWORD` is unchanged |
| ADR-0006 | Business logic cannot discover which adapter it holds | Untouched. Nothing outside `MT5Config` learns anything new |
| ADR-0007 | Two locks; `connect`/`disconnect` finality | Untouched; no session is opened and no lock is taken |
| ADR-0012 | Revisit condition satisfied by `composition.py` | Stays exactly as satisfied, and as unexercised, as ATLAS-TASK-0023 left it. Not exercised here |
| ADR-0013 | The application constructs, holds, governs and sequences the adapter | Untouched. Sequencing and supervision stay unimplemented |
| ADR-0014 | The section is restated, not imported; no `atlas.config → atlas.broker` edge | **Preserved, and the reason for the site.** §12 BP-1, BP-2 |
| ADR-0015 | Unusable broker configuration fails startup at the translation | **Completed, not amended.** Its sentence "`MT5Config` refuses them" becomes accurate for all four values without ADR-0015 being edited |
| ADR-0016 | The decision this task implements | §3 |

ADR-0015's guarantee "No new field, no new invariant, no new environment
variable" stays true of ADR-0015. ADR-0016 lifted the invariant half
deliberately, and only that half: this task adds no field and no environment
variable either.

---

## 22. Roadmap

`docs/ROADMAP.md` is not modified by this task, and was not modified by its
specification.

The precedent is ATLAS-TASK-0021, whose specification commit `ad766252` staged
exactly one file, ATLAS-TASK-0022's `e9596ac3`, and ATLAS-TASK-0023's
`9b9e3df`, which did the same. The roadmap's status table records completed
work citing the commit it reached `main` on, and this task has no
implementation and no commit to cite. Its row is written when it is
implemented and merged, the way every row above it was.

Two consequences are recorded rather than fixed. `docs/ROADMAP.md:1368`
becomes incomplete when this task merges (§14 DOC-5). And the behavioural
change in §19.3 — that a deployment with an empty password or an unset
terminal path stops starting — belongs in the roadmap at merge time, where
ADR-0016 `:230` places it.
