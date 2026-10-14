"""Private process ownership evidence for bounded CLI/MCP workers.

This module never discovers/terminates Renga by process name. A supervisor issues
a per-worker lease. The worker records an isolated Renga PID only after Session
has rejected every pre-existing PID. Timeout cleanup opens that exact PID and
compares its creation time and executable using the *same* retained handle before
terminating it. Unproven ownership leaves the model outcome unknown.

The manifest is local recovery evidence, not a security boundary against a
hostile process running as the same Windows user. No COM or UI is used here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
import json
import math
import os
import sys
import uuid

from .config import settings

MANIFEST_ENV = "RENGA_BRIDGE_OWNERSHIP_FILE"
TOKEN_ENV = "RENGA_BRIDGE_OWNERSHIP_TOKEN"
TIMEOUT_ENV = "RENGA_BRIDGE_COMMAND_TIMEOUT_SEC"
SCHEMA_VERSION = 1


def command_timeout_seconds(value: float | None = None) -> float:
    """Finite wall-clock limit; frontend/client timeout must exceed this + cleanup."""
    if value is None:
        value = os.environ.get(TIMEOUT_ENV, "180")
        try:
            value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{TIMEOUT_ENV} must be a finite number") from exc
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 1 <= value <= 3600:
        raise ValueError("Command timeout must be finite and between 1 and 3600 seconds")
    return float(value)


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    creation_time: int  # Exact Windows FILETIME ticks, not a rounded Unix float.
    executable: str

    def __post_init__(self):
        if isinstance(self.pid, bool) or not isinstance(self.pid, int) or self.pid <= 0:
            raise ValueError("Invalid process PID")
        if isinstance(self.creation_time, bool) or not isinstance(self.creation_time, int) or self.creation_time <= 0:
            raise ValueError("Invalid process creation time")
        if not isinstance(self.executable, str) or not self.executable.strip():
            raise ValueError("Missing process executable")


class ProcessHandle(Protocol):
    identity: ProcessIdentity

    def terminate(self) -> None: ...
    def close(self) -> None: ...


class ProcessBackend(Protocol):
    def open(self, pid: int, *, terminate: bool = False) -> ProcessHandle: ...


class _WindowsHandle:
    def __init__(self, kernel, handle, identity):
        self.kernel = kernel
        self.handle = handle
        self.identity = identity

    def terminate(self):
        import ctypes

        if not self.kernel.TerminateProcess(self.handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())
        # Do not wait indefinitely for a stuck native shutdown. A successful
        # TerminateProcess request alone is not proof that the process exited.
        wait_result = self.kernel.WaitForSingleObject(self.handle, 5000)
        if wait_result != 0:  # WAIT_OBJECT_0
            raise TimeoutError("Owned process termination requested; exit not confirmed within 5 seconds")

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class WindowsProcessBackend:
    """Kernel handles retained across identity verification and termination."""

    def __init__(self):
        if sys.platform != "win32":
            raise OSError("Windows process identity requires Windows")
        import ctypes
        from ctypes import wintypes

        self.ctypes = ctypes
        self.wintypes = wintypes
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        self.kernel.GetProcessTimes.restype = wintypes.BOOL
        self.kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self.kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.GetExitCodeProcess.restype = wintypes.BOOL
        self.kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel.TerminateProcess.restype = wintypes.BOOL
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD

    def open(self, pid, *, terminate=False):
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise ValueError("Invalid process PID")
        # Query limited information; add terminate/synchronize only for cleanup.
        access = 0x1000 | (0x0001 | 0x00100000 if terminate else 0)
        handle = self.kernel.OpenProcess(access, False, pid)
        if not handle:
            error = self.ctypes.get_last_error()
            if error == 87:  # ERROR_INVALID_PARAMETER: PID no longer exists.
                raise ProcessLookupError(pid)
            raise self.ctypes.WinError(error)
        try:
            exit_code = self.wintypes.DWORD()
            if not self.kernel.GetExitCodeProcess(handle, self.ctypes.byref(exit_code)):
                raise self.ctypes.WinError(self.ctypes.get_last_error())
            if exit_code.value != 259:  # STILL_ACTIVE
                raise ProcessLookupError(pid)
            times = [self.wintypes.FILETIME() for _ in range(4)]
            if not self.kernel.GetProcessTimes(handle, *(self.ctypes.byref(item) for item in times)):
                raise self.ctypes.WinError(self.ctypes.get_last_error())
            created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            buffer = self.ctypes.create_unicode_buffer(32768)
            length = self.wintypes.DWORD(len(buffer))
            if not self.kernel.QueryFullProcessImageNameW(handle, 0, buffer, self.ctypes.byref(length)):
                raise self.ctypes.WinError(self.ctypes.get_last_error())
            return _WindowsHandle(self.kernel, handle, ProcessIdentity(pid, created, buffer.value))
        except BaseException:
            self.kernel.CloseHandle(handle)
            raise


def _backend(backend=None):
    return backend if backend is not None else WindowsProcessBackend()


def capture_process_identity(pid: int, *, backend=None) -> ProcessIdentity | None:
    """Non-Windows frontends can still run pure commands, but cannot own Renga."""
    if backend is None and sys.platform != "win32":
        return None
    handle = _backend(backend).open(pid)
    try:
        return handle.identity
    finally:
        handle.close()


def _identity(value) -> ProcessIdentity:
    if not isinstance(value, dict) or set(value) != {"pid", "creation_time", "executable"}:
        raise ValueError("Malformed process identity")
    return ProcessIdentity(**value)


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, value: dict, *, new=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)
    if new:
        # Exclusive creation must not overwrite another lease or follow a link.
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        return
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class OwnershipLease:
    path: Path
    token: str
    supervisor_pid: int
    supervisor_identity: ProcessIdentity | None

    def environment(self) -> dict[str, str]:
        return {MANIFEST_ENV: str(self.path), TOKEN_ENV: self.token}

    def observe_worker(self, pid: int, *, backend=None) -> ProcessIdentity | None:
        # Capture and persist immediately after spawn, BEFORE sending stdin.
        # Windows venv python.exe can be a redirector launching the actual
        # interpreter as a child; this identity is the observed launcher.
        identity = capture_process_identity(pid, backend=backend)
        value = self.read()
        expected = asdict(identity) if identity else None
        if value.get("launch_identity") not in (None, expected):
            raise PermissionError("Lease is already bound to another launcher")
        value["launch_identity"] = expected
        _atomic_json(self.path, value)
        return identity

    def read(self) -> dict:
        value = json.loads(self.path.read_text(encoding="utf8"))
        if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION or value.get("token") != self.token:
            raise ValueError("Ownership manifest token/schema mismatch")
        expected = asdict(self.supervisor_identity) if self.supervisor_identity else None
        if value.get("supervisor_pid") != self.supervisor_pid or value.get("supervisor_identity") != expected:
            raise ValueError("Ownership manifest supervisor mismatch")
        if not isinstance(value.get("renga"), list):
            raise ValueError("Malformed Renga ownership list")
        return value


def create_ownership_lease(*, state_root: Path | None = None, backend=None) -> OwnershipLease:
    supervisor_pid = os.getpid()
    identity = capture_process_identity(supervisor_pid, backend=backend)
    token = uuid.uuid4().hex
    root = (Path(state_root) if state_root is not None else settings().state_root).resolve() / "ownership"
    root.mkdir(parents=True, exist_ok=True)
    lease = OwnershipLease(root / (token + ".json"), token, supervisor_pid, identity)
    _atomic_json(lease.path, {
        "schema_version": SCHEMA_VERSION, "token": token, "created_utc": _utc(),
        "supervisor_pid": supervisor_pid,
        "supervisor_identity": asdict(identity) if identity else None,
        "launch_identity": None, "worker_identity": None,
        "worker_parent_identity": None, "renga": [], "state": "issued",
    }, new=True)
    return lease


def _lease_from_environment() -> OwnershipLease | None:
    path, token = os.environ.get(MANIFEST_ENV), os.environ.get(TOKEN_ENV)
    if path is None and token is None:
        return None
    if not path or not token or len(token) != 32 or any(char not in "0123456789abcdef" for char in token):
        raise ValueError("Incomplete/malformed worker ownership environment")
    candidate = Path(path).resolve()
    expected_root = settings().state_root.resolve() / "ownership"
    if candidate.parent != expected_root or candidate.name != token + ".json":
        raise ValueError("Worker manifest is outside its private ownership directory")
    value = json.loads(candidate.read_text(encoding="utf8"))
    supervisor = _identity(value["supervisor_identity"]) if value.get("supervisor_identity") else None
    lease = OwnershipLease(candidate, token, value.get("supervisor_pid"), supervisor)
    lease.read()
    return lease


@dataclass(frozen=True)
class RengaRegistration:
    lease: OwnershipLease
    identity: ProcessIdentity


def register_worker_identity(*, backend=None) -> OwnershipLease:
    """Call after stdin parsing but BEFORE importing/entering native API work.

    Early ancestry proof lets a supervisor stop the actual Windows interpreter
    even when COM creation hangs before a Renga PID can be obtained. It does not
    authorize killing an undiscovered COM server.
    """
    lease = _lease_from_environment() or create_ownership_lease(backend=backend)
    worker_pid = os.getpid()
    if lease.supervisor_identity is None:
        if backend is None and sys.platform != "win32":
            return lease  # Pure non-Windows commands do not own native Renga.
        raise OSError("Worker ownership requires a verified Windows supervisor identity")
    observed_supervisor = capture_process_identity(lease.supervisor_pid, backend=backend)
    if observed_supervisor != lease.supervisor_identity:
        raise PermissionError("Ownership supervisor PID identity changed")
    worker = capture_process_identity(worker_pid, backend=backend)
    if worker is None:
        raise PermissionError("Actual worker process identity could not be confirmed")
    value = lease.read()
    launch = _identity(value["launch_identity"]) if value.get("launch_identity") else None
    prior_worker = value.get("worker_identity")
    if prior_worker is not None:
        if _identity(prior_worker) != worker:
            raise PermissionError("Lease is already bound to another worker identity")
        # The independently proven parent may have exited since bootstrap.
        # Keep its exact historical identity; never reinterpret a reused PID.
        prior_parent = _identity(value.get("worker_parent_identity"))
        valid_direct = worker == lease.supervisor_identity and launch == worker and prior_parent == worker
        valid_child = worker == launch and prior_parent == lease.supervisor_identity
        valid_redirector = launch is not None and worker.pid not in {launch.pid, lease.supervisor_pid} and prior_parent == launch
        if not (valid_direct or valid_child or valid_redirector):
            raise PermissionError("Previously recorded worker ancestry is inconsistent")
        return lease
    if worker_pid == lease.supervisor_pid:
        # Direct Session caller: local evidence only, no external supervisor.
        if launch is not None and launch != worker:
            raise PermissionError("Direct caller has an unrelated launcher identity")
        launch = worker
        worker_parent = worker
        value["launch_identity"] = asdict(worker)
    elif launch is None:
        raise PermissionError("Supervisor did not persist the independently observed worker launcher")
    elif worker == launch and os.getppid() == lease.supervisor_pid:
        worker_parent = observed_supervisor
    elif worker.pid != launch.pid and os.getppid() == launch.pid:
        if capture_process_identity(launch.pid, backend=backend) != launch:
            raise PermissionError("Worker launcher PID identity changed")
        worker_parent = launch
    else:
        raise PermissionError("Worker is not a proven child of the supervisor or observed launcher")
    value["worker_identity"] = asdict(worker)
    value["worker_parent_identity"] = asdict(worker_parent)
    value["worker_registered_utc"] = _utc()
    value["state"] = "worker_running"
    _atomic_json(lease.path, value)
    return lease


def register_owned_renga(pid: int, *, preexisting_pids: set[int], backend=None) -> RengaRegistration:
    """Call immediately after COM HWND/PID ownership check, before COM getters.

    Session must pass its snapshot taken before CreateObject. Direct Session
    calls get a self-owned local lease; bounded work needs the CLI/MCP supervisor.
    """
    if pid in preexisting_pids:
        raise PermissionError("Refusing to register a pre-existing Renga process")
    lease = register_worker_identity(backend=backend)
    renga = capture_process_identity(pid, backend=backend)
    if renga is None or _basename(renga.executable) != "renga.exe":
        raise PermissionError("Registered process is not a verified Renga executable")
    value = lease.read()
    if any(entry.get("identity") == asdict(renga) for entry in value["renga"]):
        raise PermissionError("Renga identity is already registered in this worker")
    value["renga"].append({"identity": asdict(renga), "state": "active", "registered_utc": _utc()})
    value["state"] = "running"
    _atomic_json(lease.path, value)
    return RengaRegistration(lease, renga)


def release_owned_renga(registration: RengaRegistration | None):
    """Call only after owned app.Quit returned; keep historical evidence on disk."""
    if registration is None:
        return
    value = registration.lease.read()
    for entry in value["renga"]:
        if entry.get("identity") == asdict(registration.identity) and entry.get("state") == "active":
            entry.update(state="quit_returned", released_utc=_utc())
            break
    _atomic_json(registration.lease.path, value)


def _basename(executable: str):
    return executable.replace("\\", "/").rsplit("/", 1)[-1].casefold()


def cleanup_after_timeout(lease: OwnershipLease, launch_identity: ProcessIdentity | None, *, backend=None) -> dict:
    """After stopping the launcher, stop its actual worker and identified Renga.

    No wildcard/process enumeration/COM is used. Missing or inconsistent
    evidence produces a refusal. Even confirmed termination never certifies
    the BIM file or rollback; outcome remains unknown.
    """
    result = {"outcome": "unknown", "manifest": str(lease.path), "terminated": [],
              "already_exited": [], "terminated_workers": [], "workers_already_exited": [], "refused": []}
    try:
        value = lease.read()
        if launch_identity is None or value.get("launch_identity") is None or _identity(value["launch_identity"]) != launch_identity:
            raise PermissionError("Launcher identity was not independently confirmed by its supervisor")
        worker_identity = _identity(value.get("worker_identity"))
        worker_parent = _identity(value.get("worker_parent_identity"))
        if lease.supervisor_identity is None:
            raise PermissionError("No verified Windows supervisor identity")
        if os.getpid() != lease.supervisor_pid or capture_process_identity(os.getpid(), backend=backend) != lease.supervisor_identity:
            raise PermissionError("Cleanup caller is not the original ownership supervisor")
        if worker_identity == lease.supervisor_identity:
            raise PermissionError("A direct Session has no external worker to terminate")
        if worker_identity == launch_identity:
            if worker_parent != lease.supervisor_identity:
                raise PermissionError("Worker does not have the confirmed supervisor parent")
        elif worker_parent != launch_identity or worker_identity.pid in {launch_identity.pid, lease.supervisor_pid}:
            raise PermissionError("Actual worker does not have the confirmed launcher parent")
        for entry in value["renga"]:
            # Check the entire manifest before touching *any* process.
            if not isinstance(entry, dict) or entry.get("state") not in {
                "active", "quit_returned", "terminated_after_timeout", "already_exited_after_timeout"
            }:
                raise ValueError("Malformed Renga ownership entry/state")
            identity = _identity(entry.get("identity"))
            if _basename(identity.executable) != "renga.exe":
                raise PermissionError("Manifest contains a non-Renga executable")
    except (OSError, ValueError, TypeError, KeyError, PermissionError) as exc:
        result["refused"].append({"reason": str(exc)})
        return result
    try:
        process_backend = _backend(backend)
    except OSError as exc:
        result["refused"].append({"reason": str(exc)})
        return result
    # Launcher.kill() can leave a Windows venv redirector's real interpreter
    # alive. Stop that exact verified process before terminating its COM server.
    worker_handle = None
    try:
        worker_handle = process_backend.open(worker_identity.pid, terminate=True)
        if worker_handle.identity != worker_identity:
            raise PermissionError("Actual worker PID identity changed; possible PID reuse")
        worker_handle.terminate()
        result["terminated_workers"].append(asdict(worker_identity))
        value["worker_state"] = "terminated_after_timeout"
    except ProcessLookupError:
        result["workers_already_exited"].append(asdict(worker_identity))
        value["worker_state"] = "already_exited_after_timeout"
    except (OSError, ValueError, PermissionError, TimeoutError) as exc:
        result["refused"].append({"pid": worker_identity.pid, "reason": str(exc)})
        return result  # Do not interrupt Renga while an unverified worker may be writing.
    finally:
        if worker_handle is not None:
            worker_handle.close()
    for entry in value["renga"]:
        if entry.get("state") != "active":
            continue
        expected = _identity(entry["identity"])
        handle = None
        try:
            handle = process_backend.open(expected.pid, terminate=True)
            if handle.identity != expected:
                raise PermissionError("Renga PID creation time/executable changed; possible PID reuse")
            handle.terminate()
            result["terminated"].append(asdict(expected))
            entry.update(state="terminated_after_timeout", cleanup_utc=_utc())
        except ProcessLookupError:
            result["already_exited"].append(asdict(expected))
            entry.update(state="already_exited_after_timeout", cleanup_utc=_utc())
        except (OSError, ValueError, PermissionError, TimeoutError) as exc:
            result["refused"].append({"pid": expected.pid, "reason": str(exc)})
        finally:
            if handle is not None:
                handle.close()
    value["state"] = "timeout_outcome_unknown"
    value["timeout_utc"] = _utc()
    try:
        _atomic_json(lease.path, value)
    except OSError as exc:
        result["refused"].append({"reason": "Could not persist timeout evidence: " + str(exc)})
    return result
