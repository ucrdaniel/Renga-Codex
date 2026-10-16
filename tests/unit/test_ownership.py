"""Real private manifests, fake kernel handles: never open/kill a live process."""

from dataclasses import asdict
import json
from types import SimpleNamespace

import pytest

from renga_codex_bridge import ownership


class FakeHandle:
    def __init__(self, backend, identity):
        self.backend = backend
        self.identity = identity
        self.closed = False

    def terminate(self):
        if self.backend.termination_error:
            raise self.backend.termination_error
        if self.identity.pid in self.backend.termination_errors:
            raise self.backend.termination_errors[self.identity.pid]
        self.backend.terminated.append(self.identity)
        if self.backend.identities.get(self.identity.pid) == self.identity:
            del self.backend.identities[self.identity.pid]

    def close(self):
        self.closed = True
        self.backend.closed.append(self.identity)


class FakeBackend:
    def __init__(self, identities):
        self.identities = {item.pid: item for item in identities}
        self.opened = []
        self.closed = []
        self.terminated = []
        self.termination_error = None
        self.termination_errors = {}
        self.open_errors = {}
        self.after_open = None

    def open(self, pid, *, terminate=False):
        self.opened.append((pid, terminate))
        if pid in self.open_errors:
            raise self.open_errors[pid]
        if pid not in self.identities:
            raise ProcessLookupError(pid)
        # This snapshot represents a retained kernel process handle. A later
        # PID-map change must not turn it into a handle to another process.
        handle = FakeHandle(self, self.identities[pid])
        if self.after_open:
            self.after_open(pid, terminate)
        return handle


@pytest.fixture
def owned(tmp_path, monkeypatch):
    state_root = tmp_path / "private-state"
    monkeypatch.setenv("RENGA_BRIDGE_STATE_ROOT", str(state_root))
    monkeypatch.setenv("RENGA_BRIDGE_WRITE_ROOT", str(tmp_path / "test-models"))
    monkeypatch.delenv(ownership.MANIFEST_ENV, raising=False)
    monkeypatch.delenv(ownership.TOKEN_ENV, raising=False)
    supervisor = ownership.ProcessIdentity(101, 10000000001, r"C:\Synthetic\python.exe")
    worker = ownership.ProcessIdentity(102, 10000000002, r"C:\Synthetic\python.exe")
    renga = ownership.ProcessIdentity(103, 10000000003, r"C:\Synthetic\Renga.exe")
    unrelated = ownership.ProcessIdentity(900, 90000000000, r"C:\Synthetic\Renga.exe")
    backend = FakeBackend([supervisor, worker, renga, unrelated])
    caller = {"pid": supervisor.pid, "parent": 99}
    monkeypatch.setattr(ownership.os, "getpid", lambda: caller["pid"])
    monkeypatch.setattr(ownership.os, "getppid", lambda: caller["parent"])
    lease = ownership.create_ownership_lease(backend=backend)
    independently_observed_worker = lease.observe_worker(worker.pid, backend=backend)
    for key, value in lease.environment().items():
        monkeypatch.setenv(key, value)
    caller.update(pid=worker.pid, parent=supervisor.pid)
    registration = ownership.register_owned_renga(renga.pid, preexisting_pids={unrelated.pid}, backend=backend)
    caller.update(pid=supervisor.pid, parent=99)
    backend.opened.clear()
    backend.closed.clear()
    return SimpleNamespace(backend=backend, lease=lease, worker=independently_observed_worker,
                           supervisor=supervisor, renga=renga, unrelated=unrelated,
                           registration=registration, caller=caller, state_root=state_root)


def replace_manifest(lease, change):
    data = json.loads(lease.path.read_text(encoding="utf8"))
    change(data)
    lease.path.write_text(json.dumps(data), encoding="utf8")


def test_manifest_contains_exact_process_creation_times_and_private_token(owned):
    data = owned.lease.read()
    assert data["worker_identity"] == asdict(owned.worker)
    assert data["renga"][0]["identity"] == asdict(owned.renga)
    assert data["supervisor_identity"] == asdict(owned.supervisor)
    assert owned.lease.path.parent == owned.state_root / "ownership"
    assert data["state"] == "running"
    assert len(data["token"]) == 32


def test_timeout_terminates_only_confirmed_owned_renga_and_still_reports_unknown(owned):
    result = ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)
    assert owned.backend.terminated == [owned.worker, owned.renga]
    assert owned.unrelated not in owned.backend.terminated
    assert result["outcome"] == "unknown"
    assert result["terminated"] == [asdict(owned.renga)]
    assert result["terminated_workers"] == [asdict(owned.worker)]
    assert result["refused"] == []
    assert owned.lease.read()["state"] == "timeout_outcome_unknown"


def test_pid_reuse_with_different_creation_time_refuses_termination(owned):
    replacement = ownership.ProcessIdentity(owned.renga.pid, owned.renga.creation_time + 1, owned.renga.executable)
    owned.backend.identities[replacement.pid] = replacement
    result = ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)
    assert result["terminated"] == []
    assert owned.backend.terminated == [owned.worker]
    assert "PID" in result["refused"][0]["reason"]
    assert replacement in owned.backend.closed


def test_changed_executable_on_same_pid_cannot_be_terminated(owned):
    owned.backend.identities[owned.renga.pid] = ownership.ProcessIdentity(
        owned.renga.pid, owned.renga.creation_time, r"C:\Synthetic\unrelated.exe"
    )
    result = ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)
    assert result["refused"]
    assert owned.backend.terminated == [owned.worker]


def test_already_exited_owned_process_is_recorded_without_killing_other_processes(owned):
    del owned.backend.identities[owned.renga.pid]
    result = ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)
    assert result["already_exited"] == [asdict(owned.renga)]
    assert owned.backend.terminated == [owned.worker]
    assert result["outcome"] == "unknown"


def test_access_denied_is_a_refusal_not_a_fallback_to_name_based_kill(owned):
    owned.backend.open_errors[owned.renga.pid] = PermissionError("access denied")
    result = ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)
    assert result["refused"][0]["pid"] == owned.renga.pid
    assert owned.backend.terminated == [owned.worker]
    assert all(pid != owned.unrelated.pid for pid, _ in owned.backend.opened)


def test_process_is_verified_and_terminated_using_a_single_retained_handle(owned):
    replacement = ownership.ProcessIdentity(owned.renga.pid, owned.renga.creation_time + 1, owned.renga.executable)

    def simulate_reuse_after_open(pid, terminate):
        if pid == owned.renga.pid and terminate:
            owned.backend.identities[pid] = replacement

    owned.backend.after_open = simulate_reuse_after_open
    ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)
    assert owned.backend.terminated == [owned.worker, owned.renga]
    assert replacement not in owned.backend.terminated
    assert owned.backend.opened.count((owned.renga.pid, True)) == 1


def test_launcher_identity_mismatch_refuses_before_opening_any_renga_handle(owned):
    wrong_worker = ownership.ProcessIdentity(owned.worker.pid, owned.worker.creation_time + 1, owned.worker.executable)
    result = ownership.cleanup_after_timeout(owned.lease, wrong_worker, backend=owned.backend)
    assert result["refused"]
    assert not any(terminate for _, terminate in owned.backend.opened)


def test_missing_independent_launcher_identity_cannot_authorize_cleanup(owned):
    result = ownership.cleanup_after_timeout(owned.lease, None, backend=owned.backend)
    assert result["refused"]
    assert owned.backend.terminated == []


@pytest.mark.parametrize("kind", ["token", "supervisor", "malformed_entry", "non_renga"])
def test_corrupt_or_inconsistent_manifest_never_authorizes_any_termination(owned, kind):
    def corrupt(data):
        if kind == "token":
            data["token"] = "0" * 32
        elif kind == "supervisor":
            data["supervisor_identity"]["creation_time"] += 1
        elif kind == "malformed_entry":
            data["renga"].append("not a process record")
        else:
            data["renga"].append({"identity": asdict(owned.worker), "state": "active"})

    replace_manifest(owned.lease, corrupt)
    result = ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)
    assert result["refused"]
    assert owned.backend.terminated == []
    assert not any(terminate for _, terminate in owned.backend.opened)


def test_invalid_json_and_missing_manifest_are_refusals(owned):
    owned.lease.path.write_text("{incomplete", encoding="utf8")
    assert ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)["refused"]
    owned.lease.path.unlink()
    assert ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)["refused"]
    assert owned.backend.terminated == []


def test_other_caller_cannot_use_the_supervisors_lease(owned):
    owned.caller["pid"] = 999
    result = ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)
    assert result["refused"]
    assert owned.backend.terminated == []


def test_reused_supervisor_pid_cannot_use_old_lease(owned):
    owned.backend.identities[owned.supervisor.pid] = ownership.ProcessIdentity(
        owned.supervisor.pid, owned.supervisor.creation_time + 1, owned.supervisor.executable
    )
    result = ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)
    assert result["refused"]
    assert owned.backend.terminated == []


def test_quit_returned_registration_is_not_terminated_by_later_timeout(owned):
    ownership.release_owned_renga(owned.registration)
    result = ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)
    assert result["terminated"] == []
    assert owned.backend.terminated == [owned.worker]
    assert (owned.renga.pid, True) not in owned.backend.opened


def test_failed_quit_record_never_claims_success_or_terminates_by_recording(owned):
    ownership.release_owned_renga(owned.registration, quit_returned=False)
    entry = owned.lease.read()["renga"][0]
    assert entry["identity"] == asdict(owned.renga)
    assert entry["state"] == "quit_failed"
    assert "released_utc" in entry
    assert owned.backend.terminated == []


def test_failed_quit_remains_eligible_only_for_confirmed_owned_timeout_cleanup(owned):
    ownership.release_owned_renga(owned.registration, quit_returned=False)
    result = ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)
    assert owned.backend.terminated == [owned.worker, owned.renga]
    assert owned.unrelated not in owned.backend.terminated
    assert (owned.unrelated.pid, True) not in owned.backend.opened
    assert result["terminated"] == [asdict(owned.renga)]
    assert result["refused"] == [] and result["outcome"] == "unknown"


@pytest.mark.parametrize("replacement_field", ["creation_time", "executable"])
def test_failed_quit_does_not_weaken_pid_creation_time_or_executable_check(owned, replacement_field):
    ownership.release_owned_renga(owned.registration, quit_returned=False)
    replacement = ownership.ProcessIdentity(
        owned.renga.pid,
        owned.renga.creation_time + int(replacement_field == "creation_time"),
        r"C:\Synthetic\unrelated.exe" if replacement_field == "executable" else owned.renga.executable,
    )
    owned.backend.identities[replacement.pid] = replacement
    result = ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)
    assert result["refused"] and result["terminated"] == []
    assert owned.backend.terminated == [owned.worker]
    assert replacement in owned.backend.closed
    assert result["outcome"] == "unknown"


def test_repeated_release_does_not_upgrade_failed_quit_to_returned(owned):
    ownership.release_owned_renga(owned.registration, quit_returned=False)
    before = owned.lease.read()["renga"][0]
    ownership.release_owned_renga(owned.registration)
    assert owned.lease.read()["renga"][0] == before


@pytest.mark.parametrize("invalid", [None, 0, 1, "false"])
def test_quit_outcome_requires_an_explicit_boolean(owned, invalid):
    with pytest.raises(ValueError, match="strict boolean"):
        ownership.release_owned_renga(owned.registration, quit_returned=invalid)
    assert owned.lease.read()["renga"][0]["state"] == "active"


def test_repeated_timeout_cleanup_does_not_repeat_termination(owned):
    ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)
    result = ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)
    assert owned.backend.terminated == [owned.worker, owned.renga]
    assert result["terminated"] == []


def test_unconfirmed_termination_is_not_reported_as_exited(owned):
    owned.backend.termination_error = TimeoutError("exit not confirmed")
    result = ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)
    assert result["terminated"] == []
    assert result["refused"][0]["reason"] == "exit not confirmed"
    assert owned.worker in owned.backend.closed
    assert (owned.renga.pid, True) not in owned.backend.opened


def test_unconfirmed_renga_exit_is_not_reported_as_terminated(owned):
    owned.backend.termination_errors[owned.renga.pid] = TimeoutError("native exit not confirmed")
    result = ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)
    assert result["terminated"] == []
    assert result["terminated_workers"] == [asdict(owned.worker)]
    assert result["refused"][0]["pid"] == owned.renga.pid
    assert owned.renga in owned.backend.closed


def test_reused_actual_worker_pid_prevents_termination_of_worker_and_renga(owned):
    replacement = ownership.ProcessIdentity(owned.worker.pid, owned.worker.creation_time + 1, owned.worker.executable)
    owned.backend.identities[owned.worker.pid] = replacement
    result = ownership.cleanup_after_timeout(owned.lease, owned.worker, backend=owned.backend)
    assert result["refused"][0]["pid"] == owned.worker.pid
    assert owned.backend.terminated == []
    assert (owned.renga.pid, True) not in owned.backend.opened


def test_preexisting_renga_cannot_be_registered(owned):
    before = owned.lease.path.read_bytes()
    with pytest.raises(PermissionError, match="pre-existing"):
        ownership.register_owned_renga(owned.unrelated.pid, preexisting_pids={owned.unrelated.pid}, backend=owned.backend)
    assert owned.lease.path.read_bytes() == before
    assert owned.backend.opened == []


def test_unrelated_worker_parent_cannot_register_under_another_lease(owned, monkeypatch):
    fresh = ownership.create_ownership_lease(backend=owned.backend)
    fresh.observe_worker(owned.worker.pid, backend=owned.backend)
    for key, value in fresh.environment().items():
        monkeypatch.setenv(key, value)
    owned.caller.update(pid=owned.worker.pid, parent=999)
    with pytest.raises(PermissionError, match="child"):
        ownership.register_owned_renga(owned.unrelated.pid, preexisting_pids=set(), backend=owned.backend)
    assert owned.backend.terminated == []


def test_capture_closes_readonly_process_handle(owned):
    assert ownership.capture_process_identity(owned.worker.pid, backend=owned.backend) == owned.worker
    assert owned.backend.opened == [(owned.worker.pid, False)]
    assert owned.backend.closed == [owned.worker]


def redirector_context(owned, monkeypatch, *, observe_launcher=True):
    launcher = ownership.ProcessIdentity(104, 10000000004, r"C:\SyntheticVenv\python.exe")
    worker = ownership.ProcessIdentity(106, 10000000006, r"C:\SyntheticBasePython\python.exe")
    renga = ownership.ProcessIdentity(105, 10000000005, r"C:\Synthetic\Renga.exe")
    for item in (launcher, worker, renga):
        owned.backend.identities[item.pid] = item
    lease = ownership.create_ownership_lease(backend=owned.backend)
    if observe_launcher:
        assert lease.observe_worker(launcher.pid, backend=owned.backend) == launcher
    for key, value in lease.environment().items():
        monkeypatch.setenv(key, value)
    owned.caller.update(pid=worker.pid, parent=launcher.pid)
    return SimpleNamespace(lease=lease, launcher=launcher, worker=worker, renga=renga)


def test_redirector_launcher_is_persisted_before_actual_worker_runs(owned, monkeypatch):
    context = redirector_context(owned, monkeypatch)
    data = context.lease.read()
    assert data["launch_identity"] == asdict(context.launcher)
    assert data["worker_identity"] is None
    assert data["renga"] == []


def test_bootstrap_records_actual_worker_before_native_pid_is_available(owned, monkeypatch):
    context = redirector_context(owned, monkeypatch)
    ownership.register_worker_identity(backend=owned.backend)
    data = context.lease.read()
    assert data["worker_identity"] == asdict(context.worker)
    assert data["renga"] == []
    owned.caller.update(pid=owned.supervisor.pid, parent=99)
    del owned.backend.identities[context.launcher.pid]
    result = ownership.cleanup_after_timeout(context.lease, context.launcher, backend=owned.backend)
    assert result["terminated_workers"] == [asdict(context.worker)]
    assert result["terminated"] == []
    assert result["outcome"] == "unknown"
    assert owned.backend.terminated == [context.worker]


def test_bootstrap_proof_keeps_exact_historical_parent_after_launcher_exits(owned, monkeypatch):
    context = redirector_context(owned, monkeypatch)
    ownership.register_worker_identity(backend=owned.backend)
    del owned.backend.identities[context.launcher.pid]
    ownership.register_owned_renga(context.renga.pid, preexisting_pids=set(), backend=owned.backend)
    data = context.lease.read()
    assert data["worker_parent_identity"] == asdict(context.launcher)
    assert data["renga"][0]["identity"] == asdict(context.renga)


def test_windows_venv_redirector_chain_proves_actual_worker_and_cleans_only_its_processes(owned, monkeypatch):
    context = redirector_context(owned, monkeypatch)
    ownership.register_owned_renga(context.renga.pid, preexisting_pids={owned.renga.pid, owned.unrelated.pid}, backend=owned.backend)
    proof = context.lease.read()
    assert proof["worker_identity"] == asdict(context.worker)
    assert proof["worker_parent_identity"] == asdict(context.launcher)
    owned.caller.update(pid=owned.supervisor.pid, parent=99)
    del owned.backend.identities[context.launcher.pid]  # Popen launcher.kill() already returned.
    result = ownership.cleanup_after_timeout(context.lease, context.launcher, backend=owned.backend)
    assert result["terminated_workers"] == [asdict(context.worker)]
    assert result["terminated"] == [asdict(context.renga)]
    assert owned.backend.terminated == [context.worker, context.renga]
    assert owned.worker not in owned.backend.terminated
    assert owned.renga not in owned.backend.terminated
    assert owned.unrelated not in owned.backend.terminated


def test_redirector_registration_refuses_reused_launcher_identity(owned, monkeypatch):
    context = redirector_context(owned, monkeypatch)
    owned.backend.identities[context.launcher.pid] = ownership.ProcessIdentity(
        context.launcher.pid, context.launcher.creation_time + 1, context.launcher.executable
    )
    with pytest.raises(PermissionError, match="launcher PID identity"):
        ownership.register_owned_renga(context.renga.pid, preexisting_pids=set(), backend=owned.backend)
    assert context.lease.read()["renga"] == []


def test_worker_cannot_use_a_token_without_independent_launcher_proof(owned, monkeypatch):
    context = redirector_context(owned, monkeypatch, observe_launcher=False)
    with pytest.raises(PermissionError, match="independently observed"):
        ownership.register_owned_renga(context.renga.pid, preexisting_pids=set(), backend=owned.backend)
    assert context.lease.read()["renga"] == []


def test_worker_with_wrong_parent_cannot_claim_the_observed_redirector(owned, monkeypatch):
    context = redirector_context(owned, monkeypatch)
    owned.caller["parent"] = owned.supervisor.pid
    with pytest.raises(PermissionError, match="proven child"):
        ownership.register_owned_renga(context.renga.pid, preexisting_pids=set(), backend=owned.backend)


def test_corrupted_redirector_ancestry_refuses_worker_and_renga_termination(owned, monkeypatch):
    context = redirector_context(owned, monkeypatch)
    ownership.register_owned_renga(context.renga.pid, preexisting_pids=set(), backend=owned.backend)
    replace_manifest(context.lease, lambda data: data["worker_parent_identity"].update(creation_time=1))
    owned.caller.update(pid=owned.supervisor.pid, parent=99)
    result = ownership.cleanup_after_timeout(context.lease, context.launcher, backend=owned.backend)
    assert result["refused"]
    assert owned.backend.terminated == []


def test_non_windows_frontend_identity_capture_never_loads_native_backend(monkeypatch):
    monkeypatch.setattr(ownership.sys, "platform", "linux")
    assert ownership.capture_process_identity(123) is None


@pytest.mark.parametrize("value", [True, 0, -1, 3601, float("nan"), float("inf"), "180"])
def test_invalid_explicit_timeout_is_rejected(value):
    with pytest.raises(ValueError):
        ownership.command_timeout_seconds(value)


def test_default_and_environment_timeout_are_bounded(monkeypatch):
    monkeypatch.delenv(ownership.TIMEOUT_ENV, raising=False)
    assert ownership.command_timeout_seconds() == 180
    monkeypatch.setenv(ownership.TIMEOUT_ENV, "240.5")
    assert ownership.command_timeout_seconds() == 240.5
    monkeypatch.setenv(ownership.TIMEOUT_ENV, "forever")
    with pytest.raises(ValueError):
        ownership.command_timeout_seconds()


@pytest.mark.parametrize("pid,created", [(True, 1), (0, 1), (1, 0), (1, 1.5)])
def test_process_identity_requires_positive_integer_pid_and_exact_creation_time(pid, created):
    with pytest.raises(ValueError):
        ownership.ProcessIdentity(pid, created, "Renga.exe")
