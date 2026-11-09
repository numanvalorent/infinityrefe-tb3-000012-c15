"""Infinity witness runtime: the verifier that re-runs the deliverable.

A conventional Terminal-Bench verifier grades the artifact an agent left behind.
It cannot tell a program that computed the answer from a file that merely
contains it, which is why a forged ``output.json`` -- copied from a leaked
expectation, guessed from the instruction, or produced by a wrong method that
happens to coincide on the shipped fixture -- scores full reward.

This runtime grades behaviour instead. It runs inside the sealed verifier
container (Terminal-Bench 3 ``environment_mode = "separate"``, no network, agent
container already gone) and does three things in order:

1. **Artifact gate.** Restore the pristine inputs from ``tests/witness/fixtures``
   (never trusting the agent's copy), compute the reference expectation with the
   task's own ``reference.py``, and compare the declared outputs. Optionally run
   the author's pytest suite hermetically on top.
2. **Witnesses.** ``k`` times: restore the deliverable from a snapshot, generate a
   fresh input from a seed the agent never saw, compute the expectation *before*
   the deliverable runs, execute the deliverable with a timeout, and compare.
   One mismatch, timeout, missing output, or tampered input fails the trial.
3. **Reward record.** Write ``reward.txt`` / ``status.txt`` (Harbor), a
   Reward-Kit-shaped ``reward.json`` + ``reward-details.json``, and
   ``record.json``: a content-addressed record (artifact hashes, verifier tree
   hash, seeds, per-witness verdicts) that ``infinity record sign`` turns into a
   signed, offline-verifiable per-trial attestation.

Reward is 1.0 only when every gate and every witness passes; anything else is
0.0. ``status.txt`` separates "the agent was wrong" (``ok``) from "the verifier
could not run" (``errored``) so a broken container is retried, never scored.

This file is copied verbatim into a task's ``tests/`` directory by
``infinity witness init`` and must therefore stay standard-library only with no
``infinity`` imports. Every absolute path (/app, /tests, /logs/verifier) can be
rebased, which is how the unit tests exercise it on a developer machine.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

RUNTIME_VERSION = "2.0.0"
RECORD_SCHEMA_VERSION = 2

DEFAULT_APP_ROOT = "/app"
DEFAULT_TESTS_ROOT = "/tests"
DEFAULT_LOGS_ROOT = "/logs/verifier"
DEFAULT_PROGRAM_TIMEOUT_SEC = 120
DEFAULT_WITNESSES = 3
MAX_CAPTURE_CHARS = 4000
_SKIP_TREE_PARTS = frozenset({"__pycache__", ".pytest_cache"})
_SKIP_TREE_SUFFIXES = frozenset({".pyc", ".pyo"})


# ---------------------------------------------------------------------------
# Paths and hashing
# ---------------------------------------------------------------------------


def _linked(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def _relative_parts(value: str) -> tuple[str, ...]:
    # Validate the literal string before PurePath can collapse dots or turn a
    # Windows drive/UNC path into an absolute join on a Windows verifier host.
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or any(ord(char) < 32 for char in value)
            or any(part in {"", ".", ".."} or part.rstrip(" .") != part
                   or PureWindowsPath(part).is_reserved() for part in value.split("/"))):
        raise WitnessConfigError(f"unsafe witness path {value!r}")
    return tuple(value.split("/"))


def _confined(root: Path, relative: str) -> Path:
    parts = _relative_parts(relative)
    if _linked(root):
        raise WitnessConfigError(f"witness root is linked: {root}")
    candidate = root
    for part in parts:
        candidate = candidate / part
        if _linked(candidate):
            raise WitnessConfigError(f"witness path is linked: {candidate}")
    try:
        candidate.resolve().relative_to(root.resolve())
    except (OSError, ValueError) as exc:
        raise WitnessConfigError(f"witness path escapes its root: {relative}") from exc
    return candidate


def _assert_unlinked_tree(root: Path) -> None:
    if _linked(root):
        raise WitnessConfigError(f"witness tree is linked: {root}")
    if root.exists() and not root.is_dir():
        raise WitnessConfigError(f"witness tree is not a directory: {root}")
    for base, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            if _linked(Path(base) / name):
                raise WitnessConfigError(f"witness tree contains a linked path: {Path(base) / name}")


class Layout:
    """Where /app, /tests and /logs/verifier actually live for this run."""

    def __init__(self, app_root: Path, tests_root: Path, logs_root: Path) -> None:
        roots = [Path(app_root), Path(tests_root), Path(logs_root)]
        if any(_linked(root) for root in roots):
            raise WitnessConfigError("witness layout roots must not be links")
        roots = [root.resolve() for root in roots]
        if any(root == Path(root.anchor) for root in roots):
            raise WitnessConfigError("witness layout must not use a filesystem root")
        for index, root in enumerate(roots):
            if any(root.is_relative_to(other) or other.is_relative_to(root) for other in roots[index + 1:]):
                raise WitnessConfigError("witness app, tests and logs roots must not overlap")
        self.app_root, self.tests_root, self.logs_root = roots

    def rebase(self, posix: str) -> Path:
        """Map a declared absolute container path onto this layout."""
        for prefix, root in ((DEFAULT_APP_ROOT, self.app_root), (DEFAULT_TESTS_ROOT, self.tests_root)):
            if posix == prefix:
                return root
            if posix.startswith(prefix + "/"):
                return _confined(root, posix[len(prefix) + 1 :])
        return Path(posix)

    def argv(self, program: list[str]) -> list[str]:
        return [str(self.rebase(token)) if token.startswith((DEFAULT_APP_ROOT, DEFAULT_TESTS_ROOT)) else token for token in program]

    def app_relative(self, posix: str) -> PurePosixPath:
        if not posix.startswith(DEFAULT_APP_ROOT + "/"):
            raise WitnessConfigError(f"path {posix!r} is not under {DEFAULT_APP_ROOT}")
        return PurePosixPath(*_relative_parts(posix[len(DEFAULT_APP_ROOT) + 1 :]))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tree_sha256(root: Path) -> str:
    """Schema-2 directory identity with length-framed paths and content hashes.

    Caches and bytecode are skipped so a Python import during verification does
    not change the verifier's own identity. Mirrored by infinity.witness.record;
    the two are pinned equal by a test.
    """
    digest = hashlib.sha256(b"infinity-witness-tree-v2\0")
    if not root.is_dir():
        raise WitnessConfigError(f"verifier tree is not a directory: {root}")
    _assert_unlinked_tree(root)
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        relative = path.relative_to(root)
        if _SKIP_TREE_PARTS.intersection(relative.parts) or path.suffix.lower() in _SKIP_TREE_SUFFIXES:
            continue
        if not path.is_file():
            continue
        name = relative.as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


class WitnessConfigError(ValueError):
    """The manifest or reference module is unusable. This is the author's bug, so status is errored."""


@dataclass(slots=True)
class Manifest:
    task: str
    program: list[str]
    inputs: list[str]
    outputs: list[str]
    reference: str
    fixtures: str
    witnesses: int = DEFAULT_WITNESSES
    program_timeout_sec: int = DEFAULT_PROGRAM_TIMEOUT_SEC
    pytest: list[str] = field(default_factory=list)
    pytest_ctrf: bool = True
    tolerances: dict[str, dict[str, dict[str, float]]] = field(default_factory=dict)
    tolerance_provenance: dict[str, Any] = field(default_factory=dict)
    text_normalise: str = "strip"
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Manifest:
        def need(key: str, kind: type) -> Any:
            value = data.get(key)
            if not isinstance(value, kind) or (kind in (list, str) and not value):
                raise WitnessConfigError(f"witness.json: {key!r} must be a non-empty {kind.__name__}")
            return value

        program = [str(x) for x in need("program", list)]
        outputs = [str(x) for x in need("outputs", list)]
        inputs = [str(x) for x in data.get("inputs", []) if isinstance(x, str)]
        witnesses = data.get("witnesses", DEFAULT_WITNESSES)
        if isinstance(witnesses, bool) or not isinstance(witnesses, int) or witnesses < 1:
            raise WitnessConfigError("witness.json: 'witnesses' must be a positive integer")
        timeout = data.get("program_timeout_sec", DEFAULT_PROGRAM_TIMEOUT_SEC)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout < 1:
            raise WitnessConfigError("witness.json: 'program_timeout_sec' must be a positive number")
        pytest_targets = data.get("pytest") or []
        if not isinstance(pytest_targets, list):
            raise WitnessConfigError("witness.json: 'pytest' must be a list of test paths")
        tolerances = data.get("tolerances") or {}
        if not isinstance(tolerances, dict):
            raise WitnessConfigError("witness.json: 'tolerances' must be an object")
        for output in outputs:
            if not output.startswith(DEFAULT_APP_ROOT + "/"):
                raise WitnessConfigError(f"witness.json: output {output!r} must be an absolute /app path")
            _relative_parts(output[len(DEFAULT_APP_ROOT) + 1:])
        for inp in inputs:
            if not inp.startswith(DEFAULT_APP_ROOT + "/"):
                raise WitnessConfigError(f"witness.json: input {inp!r} must be an absolute /app path")
            _relative_parts(inp[len(DEFAULT_APP_ROOT) + 1:])
        for key, default in (("reference", "witness/reference.py"), ("fixtures", "witness/fixtures")):
            _relative_parts(data.get(key, default))
        for token in program:
            for prefix in (DEFAULT_APP_ROOT, DEFAULT_TESTS_ROOT):
                if token.startswith(prefix + "/"):
                    _relative_parts(token[len(prefix) + 1:])
        for target in pytest_targets:
            if not isinstance(target, str) or not target.startswith(DEFAULT_TESTS_ROOT + "/"):
                raise WitnessConfigError("pytest targets must be absolute /tests paths")
            _relative_parts(target[len(DEFAULT_TESTS_ROOT) + 1:])
        return cls(
            task=str(data.get("task", "")),
            program=program,
            inputs=inputs,
            outputs=outputs,
            reference=str(data.get("reference", "witness/reference.py")),
            fixtures=str(data.get("fixtures", "witness/fixtures")),
            witnesses=witnesses,
            program_timeout_sec=int(timeout),
            pytest=[str(x) for x in pytest_targets],
            pytest_ctrf=bool(data.get("pytest_ctrf", True)),
            tolerances={str(k): v for k, v in tolerances.items() if isinstance(v, dict)},
            tolerance_provenance=data.get("tolerance_provenance") or {},
            text_normalise=str(data.get("text_normalise", "strip")),
            raw=data,
        )


def load_manifest(path: Path) -> Manifest:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WitnessConfigError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise WitnessConfigError("witness.json must be a JSON object")
    return Manifest.from_dict(data)


def load_reference(path: Path) -> Any:
    """Import the task's reference module (generate / expected) from its file."""
    if not path.is_file():
        raise WitnessConfigError(f"reference module {path} is missing")
    spec = importlib.util.spec_from_file_location("infinity_witness_reference", path)
    if spec is None or spec.loader is None:
        raise WitnessConfigError(f"cannot import reference module {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 -- author code; report, do not crash the verifier
        raise WitnessConfigError(f"reference module failed to import: {type(exc).__name__}: {exc}") from exc
    for name in ("generate", "expected"):
        if not callable(getattr(module, name, None)):
            raise WitnessConfigError(f"reference module must define a callable {name}()")
    return module


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _tolerance_for(tolerances: dict[str, dict[str, float]], location: str) -> tuple[float, float]:
    band = tolerances.get(location) or {}
    abs_tol = band.get("abs", 0.0)
    rel_tol = band.get("rel", 0.0)
    try:
        return max(0.0, float(abs_tol)), max(0.0, float(rel_tol))
    except (TypeError, ValueError):
        return 0.0, 0.0


def compare_values(expected: Any, actual: Any, tolerances: dict[str, dict[str, float]], location: str = "") -> list[str]:
    """Structural comparison with per-leaf numeric tolerance. Returns mismatch descriptions."""
    here = location or "$"
    if isinstance(expected, bool) or isinstance(actual, bool):
        if expected is actual or (isinstance(expected, bool) and isinstance(actual, bool) and expected == actual):
            return []
        return [f"{here}: expected {expected!r}, got {actual!r}"]
    if _is_number(expected):
        if not _is_number(actual):
            return [f"{here}: expected a number, got {type(actual).__name__}"]
        if not (math.isfinite(expected) and math.isfinite(actual)):
            return [f"{here}: non-finite value (expected {expected!r}, got {actual!r})"]
        abs_tol, rel_tol = _tolerance_for(tolerances, location)
        if isinstance(expected, int) and isinstance(actual, int) and abs_tol == 0.0 and rel_tol == 0.0:
            return [] if expected == actual else [f"{here}: expected {expected}, got {actual}"]
        allowed = max(abs_tol, rel_tol * abs(expected))
        if abs(actual - expected) <= allowed:
            return []
        return [f"{here}: expected {expected!r} (+/- {allowed:g}), got {actual!r}"]
    if isinstance(expected, str):
        if not isinstance(actual, str):
            return [f"{here}: expected a string, got {type(actual).__name__}"]
        return [] if expected == actual else [f"{here}: expected {expected[:80]!r}, got {actual[:80]!r}"]
    if expected is None:
        return [] if actual is None else [f"{here}: expected null, got {type(actual).__name__}"]
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{here}: expected an object, got {type(actual).__name__}"]
        mismatches: list[str] = []
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        if missing:
            mismatches.append(f"{here}: missing key(s) {', '.join(missing)}")
        if extra:
            mismatches.append(f"{here}: unexpected key(s) {', '.join(extra)}")
        for key in sorted(set(expected) & set(actual)):
            child = f"{location}.{key}" if location else key
            mismatches.extend(compare_values(expected[key], actual[key], tolerances, child))
        return mismatches
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return [f"{here}: expected an array, got {type(actual).__name__}"]
        if len(expected) != len(actual):
            return [f"{here}: expected {len(expected)} element(s), got {len(actual)}"]
        mismatches = []
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            mismatches.extend(compare_values(left, right, tolerances, f"{location}[{index}]"))
        return mismatches
    return [] if expected == actual else [f"{here}: expected {expected!r}, got {actual!r}"]


def normalise_expected(value: Any, outputs: list[str]) -> dict[str, Any]:
    """Accept either ``{output_path: value}`` or, for a single output, the bare value."""
    if isinstance(value, dict) and value and set(value) <= set(outputs):
        return {str(k): v for k, v in value.items()}
    if len(outputs) == 1:
        return {outputs[0]: value}
    raise WitnessConfigError("expected() must return a dict keyed by every declared output path")


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class WitnessOutcome:
    index: int
    seed: int
    matched: bool
    reasons: list[str]
    duration_ms: int
    exit_code: int | None = None
    timed_out: bool = False
    stdout_tail: str = ""
    stderr_tail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "seed": self.seed,
            "matched": self.matched,
            "reasons": self.reasons,
            "duration_ms": self.duration_ms,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
        }


@dataclass(slots=True)
class Verdict:
    reward: float
    status: str
    master_seed: int
    gate_passed: bool
    gate_reasons: list[str]
    pytest_exit_code: int | None
    witnesses: list[WitnessOutcome]
    artifacts: dict[str, str]
    tests_tree_sha256: str
    manifest_sha256: str
    program: list[str]
    task: str
    started_at: float
    finished_at: float
    error: str = ""

    @property
    def witnesses_passed(self) -> int:
        return sum(1 for w in self.witnesses if w.matched)

    def record(self) -> dict[str, Any]:
        return {
            "schema_version": RECORD_SCHEMA_VERSION,
            "kind": "infinity-witness-reward-record",
            "runtime_version": RUNTIME_VERSION,
            "task": self.task,
            "reward": self.reward,
            "status": self.status,
            "master_seed": self.master_seed,
            "witness_seeds": [w.seed for w in self.witnesses],
            "witnesses_required": len(self.witnesses),
            "witnesses_passed": self.witnesses_passed,
            "program": self.program,
            "artifacts": self.artifacts,
            "tests_tree_sha256": self.tests_tree_sha256,
            "manifest_sha256": self.manifest_sha256,
            "artifact_gate": {
                "passed": self.gate_passed,
                "reasons": self.gate_reasons,
                "pytest_exit_code": self.pytest_exit_code,
            },
            "witnesses": [w.as_dict() for w in self.witnesses],
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    def details(self) -> dict[str, Any]:
        return {
            "reward": self.reward,
            "status": self.status,
            "summary": self.summary(),
            "criteria": [
                {
                    "name": "artifact_gate",
                    "kind": "deterministic",
                    "required": True,
                    "passed": self.gate_passed,
                    "reasons": self.gate_reasons,
                },
                *(
                    {
                        "name": f"witness_{w.index}",
                        "kind": "re-execution",
                        "required": True,
                        "passed": w.matched,
                        "seed": w.seed,
                        "reasons": w.reasons,
                    }
                    for w in self.witnesses
                ),
            ],
            "aggregation": "required-pass",
        }

    def summary(self) -> str:
        if self.status != "ok":
            return f"errored: {self.error or 'verifier could not run'}"
        gate = "passed" if self.gate_passed else "failed"
        return (
            f"reward={self.reward:g} artifact gate {gate}; "
            f"{self.witnesses_passed}/{len(self.witnesses)} witnesses matched"
        )


def derive_seed(master: int, index: int) -> int:
    digest = hashlib.sha256(f"{master}:{index}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _tail(text: str) -> str:
    return text[-MAX_CAPTURE_CHARS:] if len(text) > MAX_CAPTURE_CHARS else text


def _clear_directory(root: Path) -> None:
    _assert_unlinked_tree(root)
    for child in root.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


def _copy_tree_over(source: Path, target: Path) -> None:
    _assert_unlinked_tree(source)
    _assert_unlinked_tree(target)
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        destination = _confined(target, relative.as_posix())
        if path.is_dir() and not path.is_symlink():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink() or destination.exists():
            destination.unlink()
        shutil.copy2(path, destination, follow_symlinks=False)


class Runner:
    def __init__(self, manifest: Manifest, layout: Layout, *, python: str, master_seed: int) -> None:
        self.manifest = manifest
        self.layout = layout
        self.python = python
        self.master_seed = master_seed
        # Dataclass callers must meet the same path contract as parsed JSON.
        for path in manifest.inputs + manifest.outputs:
            layout.app_relative(path)
            layout.rebase(path)
        layout.argv(manifest.program)
        for path in manifest.pytest:
            if not path.startswith(DEFAULT_TESTS_ROOT + "/"):
                raise WitnessConfigError("pytest targets must be absolute /tests paths")
            layout.rebase(path)
        self.reference_path = _confined(layout.tests_root, manifest.reference)
        self.fixtures_root = _confined(layout.tests_root, manifest.fixtures)
        self._snapshot: Path | None = None
        self._tests_tree_before = ""

    # -- helpers ----------------------------------------------------------

    def _output_path(self, output: str) -> Path:
        return self.layout.rebase(output)

    def _read_output(self, output: str) -> tuple[Any, str | None]:
        path = self._output_path(output)
        if path.is_symlink():
            return None, f"{output} is a symlink"
        if not path.is_file():
            return None, f"{output} was not produced"
        try:
            resolved = path.resolve()
            resolved.relative_to(self.layout.app_root.resolve())
        except (OSError, ValueError):
            return None, f"{output} resolves outside {DEFAULT_APP_ROOT}"
        try:
            raw = path.read_bytes()
        except OSError as exc:
            return None, f"{output} could not be read: {exc}"
        if path.suffix.casefold() == ".json":
            try:
                return json.loads(raw.decode("utf-8")), None
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                return None, f"{output} is not valid JSON: {exc}"
        text = raw.decode("utf-8", errors="replace")
        if self.manifest.text_normalise == "strip":
            text = text.strip()
        return text, None

    def _compare_outputs(self, expected: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        for output in self.manifest.outputs:
            actual, error = self._read_output(output)
            if error:
                reasons.append(error)
                continue
            tolerances = self.manifest.tolerances.get(output, {})
            reasons.extend(f"{output} {m}" for m in compare_values(expected[output], actual, tolerances))
        return reasons

    def _expected(self, module: Any) -> dict[str, Any]:
        try:
            value = module.expected(self.layout.app_root)
        except Exception as exc:  # noqa: BLE001
            raise WitnessConfigError(f"reference expected() raised {type(exc).__name__}: {exc}") from exc
        return normalise_expected(value, self.manifest.outputs)

    def _input_hashes(self) -> dict[str, str]:
        hashes: dict[str, str] = {}
        for inp in self.manifest.inputs:
            path = self.layout.rebase(inp)
            hashes[inp] = sha256_file(path) if path.is_file() else ""
        return hashes

    def _snapshot_app(self) -> None:
        # An agent that produced nothing leaves no /app at all; that is a zero,
        # not a verifier error, so the snapshot of "nothing" must still succeed.
        _assert_unlinked_tree(self.layout.app_root)
        self.layout.app_root.mkdir(parents=True, exist_ok=True)
        self._snapshot = Path(tempfile.mkdtemp(prefix="infinity-witness-snapshot-")) / "app"
        shutil.copytree(self.layout.app_root, self._snapshot, symlinks=True)

    def _restore_app(self) -> None:
        assert self._snapshot is not None
        self.layout.app_root.mkdir(parents=True, exist_ok=True)
        _clear_directory(self.layout.app_root)
        _copy_tree_over(self._snapshot, self.layout.app_root)

    def _restore_fixtures(self) -> None:
        if not self.fixtures_root.is_dir():
            raise WitnessConfigError(f"fixtures directory {self.fixtures_root} is missing")
        for inp in self.manifest.inputs:
            relative = self.layout.app_relative(inp)
            if not (self.fixtures_root / relative).is_file():
                raise WitnessConfigError(f"fixtures lack the pristine copy of {inp} ({relative})")
        _copy_tree_over(self.fixtures_root, self.layout.app_root)

    def _remove_outputs(self) -> None:
        for output in self.manifest.outputs:
            path = self._output_path(output)
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path, ignore_errors=True)

    def _program_env(self) -> dict[str, str]:
        # Deliberately minimal and deliberately free of any marker that this is a
        # witness run: a deliverable that could tell the re-execution apart from
        # the original run could behave honestly only when watched.
        env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/root"),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        for key in ("SYSTEMROOT", "SystemRoot", "TEMP", "TMP", "PATHEXT", "COMSPEC"):
            if key in os.environ:
                env[key] = os.environ[key]
        return env

    def _run_program(self) -> tuple[int | None, bool, str, str]:
        argv = self.layout.argv(self.manifest.program)
        try:
            proc = subprocess.run(
                argv,
                cwd=self.layout.app_root,
                env=self._program_env(),
                capture_output=True,
                text=True,
                errors="replace",
                timeout=self.manifest.program_timeout_sec,
                check=False,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            err = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            return None, True, _tail(out), _tail(err)
        except OSError as exc:
            return None, False, "", f"could not start {argv[0]!r}: {exc}"
        return proc.returncode, False, _tail(proc.stdout), _tail(proc.stderr)

    def _tests_tampered(self) -> str | None:
        after = tree_sha256(self.layout.tests_root)
        if after != self._tests_tree_before:
            return "verifier tree changed while the deliverable ran (tampering)"
        return None

    # -- phases ------------------------------------------------------------

    def artifact_gate(self, module: Any) -> tuple[bool, list[str], int | None]:
        reasons: list[str] = []
        self._restore_app()
        self._restore_fixtures()
        expected = self._expected(module)
        reasons.extend(self._compare_outputs(expected))
        pytest_rc: int | None = None
        if self.manifest.pytest:
            pytest_rc = self._run_pytest()
            if pytest_rc == 1:
                reasons.append("pytest suite failed")
            elif pytest_rc != 0:
                raise WitnessConfigError(f"pytest exited {pytest_rc}: harness failure, not an agent failure")
        return not reasons, reasons, pytest_rc

    def _run_pytest(self) -> int:
        targets = [str(self.layout.rebase(t)) for t in self.manifest.pytest]
        cmd = [
            self.python,
            "-I",
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-c",
            os.devnull,
            f"--rootdir={self.layout.tests_root}",
            "-q",
            "-rA",
        ]
        if self.manifest.pytest_ctrf:
            cmd.append(f"--ctrf={self.layout.logs_root / 'ctrf.json'}")
        cmd.extend(targets)
        env = dict(os.environ)
        env["PYTEST_ADDOPTS"] = ""
        env["PYTHONPATH"] = ""
        proc = subprocess.run(cmd, cwd=self.layout.tests_root, env=env, capture_output=True, text=True, check=False)
        (self.layout.logs_root / "pytest.log").write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
        return proc.returncode

    def witness(self, module: Any, index: int) -> WitnessOutcome:
        seed = derive_seed(self.master_seed, index)
        started = time.monotonic()
        reasons: list[str] = []
        self._restore_app()
        self._remove_outputs()
        try:
            module.generate(seed, self.layout.app_root)
        except Exception as exc:  # noqa: BLE001
            raise WitnessConfigError(f"reference generate() raised {type(exc).__name__}: {exc}") from exc
        before = self._input_hashes()
        expected = self._expected(module)
        missing = [t for t in self.manifest.program if t.startswith(DEFAULT_APP_ROOT + "/") and not self.layout.rebase(t).is_file()]
        if missing:
            return WitnessOutcome(
                index=index,
                seed=seed,
                matched=False,
                reasons=[f"deliverable {token} is missing: nothing to re-run" for token in missing],
                duration_ms=int((time.monotonic() - started) * 1000),
                exit_code=None,
                timed_out=False,
                stdout_tail="",
                stderr_tail="",
            )
        exit_code, timed_out, out, err = self._run_program()
        if timed_out:
            reasons.append(f"deliverable exceeded {self.manifest.program_timeout_sec}s")
        elif exit_code is None:
            reasons.append(err or "deliverable could not be started")
        elif exit_code != 0:
            reasons.append(f"deliverable exited {exit_code}")
        tampered = self._tests_tampered()
        if tampered:
            reasons.append(tampered)
        after = self._input_hashes()
        for inp in self.manifest.inputs:
            if before.get(inp) != after.get(inp):
                reasons.append(f"{inp} was modified by the deliverable")
        if not reasons or exit_code == 0:
            reasons.extend(self._compare_outputs(expected))
        return WitnessOutcome(
            index=index,
            seed=seed,
            matched=not reasons,
            reasons=reasons,
            duration_ms=int((time.monotonic() - started) * 1000),
            exit_code=exit_code,
            timed_out=timed_out,
            stdout_tail=out,
            stderr_tail=err,
        )

    def run(self) -> Verdict:
        started = time.time()
        _assert_unlinked_tree(self.layout.app_root)
        _assert_unlinked_tree(self.layout.tests_root)
        _assert_unlinked_tree(self.layout.logs_root)
        self.layout.logs_root.mkdir(parents=True, exist_ok=True)
        manifest_hash = sha256_bytes(json.dumps(self.manifest.raw, sort_keys=True, separators=(",", ":")).encode())
        self._tests_tree_before = tree_sha256(self.layout.tests_root)
        artifacts = self._hash_artifacts()
        verdict = Verdict(
            reward=0.0,
            status="ok",
            master_seed=self.master_seed,
            gate_passed=False,
            gate_reasons=[],
            pytest_exit_code=None,
            witnesses=[],
            artifacts=artifacts,
            tests_tree_sha256=self._tests_tree_before,
            manifest_sha256=manifest_hash,
            program=list(self.manifest.program),
            task=self.manifest.task,
            started_at=started,
            finished_at=started,
        )
        try:
            module = load_reference(self.reference_path)
            self._snapshot_app()
            verdict.gate_passed, verdict.gate_reasons, verdict.pytest_exit_code = self.artifact_gate(module)
            for index in range(1, self.manifest.witnesses + 1):
                verdict.witnesses.append(self.witness(module, index))
            all_matched = verdict.gate_passed and all(w.matched for w in verdict.witnesses)
            verdict.reward = 1.0 if all_matched else 0.0
        except WitnessConfigError as exc:
            verdict.status = "errored"
            verdict.error = str(exc)
            verdict.reward = 0.0
        except Exception:  # noqa: BLE001 -- the verifier must never die without a verdict
            verdict.status = "errored"
            verdict.error = traceback.format_exc()[-MAX_CAPTURE_CHARS:]
            verdict.reward = 0.0
        finally:
            if self._snapshot is not None:
                shutil.rmtree(self._snapshot.parent, ignore_errors=True)
        verdict.finished_at = time.time()
        return verdict

    def _hash_artifacts(self) -> dict[str, str]:
        hashes: dict[str, str] = {}
        for output in self.manifest.outputs:
            path = self._output_path(output)
            hashes[output] = sha256_file(path) if path.is_file() and not path.is_symlink() else ""
        for token in self.manifest.program:
            if token.startswith(DEFAULT_APP_ROOT + "/"):
                path = self.layout.rebase(token)
                hashes[token] = sha256_file(path) if path.is_file() and not path.is_symlink() else ""
        return hashes


def write_verdict(verdict: Verdict, logs_root: Path) -> None:
    logs_root.mkdir(parents=True, exist_ok=True)
    reward_text = "1" if verdict.reward >= 1.0 else "0"
    (logs_root / "reward.txt").write_text(reward_text + "\n", encoding="utf-8")
    (logs_root / "status.txt").write_text(verdict.status + "\n", encoding="utf-8")
    (logs_root / "reward.json").write_text(json.dumps({"reward": verdict.reward}, indent=2) + "\n", encoding="utf-8")
    (logs_root / "reward-details.json").write_text(json.dumps(verdict.details(), indent=2) + "\n", encoding="utf-8")
    (logs_root / "record.json").write_text(
        json.dumps(verdict.record(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="infinity_witness", description=__doc__.split("\n\n")[0])
    parser.add_argument("--manifest", default=f"{DEFAULT_TESTS_ROOT}/witness.json")
    parser.add_argument("--app-root", default=DEFAULT_APP_ROOT)
    parser.add_argument("--tests-root", default=DEFAULT_TESTS_ROOT)
    parser.add_argument("--logs", default=DEFAULT_LOGS_ROOT)
    parser.add_argument("--seed", type=int, default=None, help="master seed (default: fresh entropy; recorded for replay)")
    parser.add_argument("--python", default=sys.executable, help="interpreter used for the optional pytest gate")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    layout = Layout(Path(args.app_root), Path(args.tests_root), Path(args.logs))
    master_seed = args.seed if args.seed is not None else int.from_bytes(os.urandom(8), "big")
    try:
        manifest = load_manifest(Path(args.manifest))
    except WitnessConfigError as exc:
        verdict = Verdict(
            reward=0.0,
            status="errored",
            master_seed=master_seed,
            gate_passed=False,
            gate_reasons=[],
            pytest_exit_code=None,
            witnesses=[],
            artifacts={},
            tests_tree_sha256=tree_sha256(layout.tests_root),
            manifest_sha256="",
            program=[],
            task="",
            started_at=time.time(),
            finished_at=time.time(),
            error=str(exc),
        )
        write_verdict(verdict, layout.logs_root)
        print(f"infinity-witness: {verdict.summary()}")
        return 0
    verdict = Runner(manifest, layout, python=args.python, master_seed=master_seed).run()
    write_verdict(verdict, layout.logs_root)
    print(f"infinity-witness: {verdict.summary()}")
    # Always 0: the reward file carries the verdict. A non-zero exit reads as harness failure.
    return 0


if __name__ == "__main__":
    sys.exit(main())
