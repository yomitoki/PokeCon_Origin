"""One-use, local state handoff for a user-confirmed PokeCon restart.

No function in this module starts, exits, kills, or execs a process.  The host
must finish its normal, recording-safe shutdown before creating a manifest,
then use the returned argv only after ``_process_exit_ready`` is true.  An
exec-style restart retains the current working directory and environment;
there is deliberately no launcher, runtime selection, device open, or retry.
"""

import contextlib
import json
import math
import os
import re
import stat
import sys
import time
import uuid


RESTART_STATE_VERSION = 1
RESTART_STATE_TTL = 120.0
MAX_RESTART_STATE_TTL = 600.0
MAX_RESTART_STATE_BYTES = 4 * 1024 * 1024
_MANIFEST_NAME = re.compile(r"\.pokecon-restart-([0-9a-f]{32})\.json\Z")
_PYTHON_NAME = re.compile(r"python(?:w)?(?:[0-9]+(?:\.[0-9]+)*)?(?:\.exe)?\Z", re.I)
_STATE_KEYS = frozenset(("input_set", "combined_set", "maximized", "input_set_data"))


class RestartStateError(ValueError):
    """A restart handoff cannot be safely prepared, used, or discarded."""


def _profiles_root(profiles_root):
    return os.path.abspath(profiles_root or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "profiles"))


def _profile_directory(profile, profiles_root=None):
    if (not isinstance(profile, str) or not profile or profile != profile.strip()
            or profile in (".", "..") or len(profile) > 128
            or any(char in profile for char in "/\\:\x00")
            or profile.endswith(".")):
        raise RestartStateError("Invalid restart profile")
    root = _profiles_root(profiles_root)
    directory = os.path.join(root, profile)
    try:
        directory_info = os.lstat(directory)
    except OSError as error:
        raise RestartStateError("Restart profile directory is missing") from error
    if (not os.path.isdir(directory) or os.path.islink(directory)
            or _is_reparse_point(directory_info)
            or os.path.normcase(os.path.dirname(os.path.realpath(directory)))
            != os.path.normcase(os.path.realpath(root))):
        raise RestartStateError("Restart profile directory is missing or redirected")
    return directory


def _is_reparse_point(info):
    # Python 3.7's Windows realpath does not resolve every junction type.
    return bool(getattr(info, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _manifest_path(path, profile, profiles_root=None):
    if not isinstance(path, str) or not path or "\x00" in path or not os.path.isabs(path):
        raise RestartStateError("Restart state must use an absolute local path")
    if ".." in re.split(r"[/\\]", path):
        raise RestartStateError("Restart state traversal is not permitted")
    directory = _profile_directory(profile, profiles_root)
    path = os.path.abspath(path)
    match = _MANIFEST_NAME.fullmatch(os.path.basename(path))
    if (match is None or os.path.normcase(os.path.dirname(path))
            != os.path.normcase(directory)):
        raise RestartStateError("Restart state must be a dedicated file in its profile")
    if (os.path.islink(path) or os.path.normcase(os.path.realpath(path))
            != os.path.normcase(os.path.join(os.path.realpath(directory), os.path.basename(path)))):
        raise RestartStateError("Redirected restart state is not permitted")
    return path, match.group(1)


def _timestamp(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RestartStateError("Invalid restart {}".format(name))
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise RestartStateError("Invalid restart {}".format(name))
    return value


def _state_copy(state):
    if not isinstance(state, dict) or set(state) != _STATE_KEYS:
        raise RestartStateError("Restart state has an unsupported schema")
    for key in ("input_set", "combined_set"):
        value = state[key]
        if (not isinstance(value, str) or len(value) > 256 or "\x00" in value
                or (key == "input_set" and not value.strip())):
            raise RestartStateError("Invalid restart {}".format(key))
    if type(state["maximized"]) is not bool:
        raise RestartStateError("Restart maximized flag must be bool")
    snapshot = state["input_set_data"]
    if not isinstance(snapshot, dict) or not snapshot:
        raise RestartStateError("Restart InputSet snapshot is empty")
    for key in ("camera", "serial", "audio", "recording", "all_tabs", "commands"):
        if not isinstance(snapshot.get(key), dict):
            raise RestartStateError("Restart InputSet snapshot is missing {}".format(key))
    try:
        return json.loads(json.dumps(state, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError, RecursionError) as error:
        raise RestartStateError("Restart state must be finite JSON data") from error


def prepare_restart_state(profile, state, profiles_root=None, now=None,
                          ttl_seconds=RESTART_STATE_TTL):
    """Write a fresh, exclusive manifest; never overwrite a named InputSet.

    ``state`` contains exactly ``input_set``, ``combined_set``, ``maximized``
    and ``input_set_data`` (the host's ``_current_input_set_data()`` result).
    Existing profile directories only; no caller-controlled filename is used.
    The hard-link publish is atomic and fails rather than overwriting a file.
    """
    directory = _profile_directory(profile, profiles_root)
    created = _timestamp(time.time() if now is None else now, "creation time")
    ttl = _timestamp(ttl_seconds, "TTL")
    if not 0 < ttl <= MAX_RESTART_STATE_TTL:
        raise RestartStateError("Restart TTL must be within 0..600 seconds")
    token = uuid.uuid4().hex
    payload = {"version": RESTART_STATE_VERSION, "profile": profile,
               "token": token, "created_at": created, "expires_at": created + ttl,
               "state": _state_copy(state)}
    try:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as error:
        raise RestartStateError("Restart state cannot be encoded") from error
    if len(encoded) > MAX_RESTART_STATE_BYTES:
        raise RestartStateError("Restart state exceeds 4 MiB")
    path = os.path.join(directory, ".pokecon-restart-{}.json".format(token))
    temporary = path + ".{}.tmp".format(uuid.uuid4().hex)
    descriptor = None
    temporary_created = False
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                             | getattr(os, "O_BINARY", 0), 0o600)
        temporary_created = True
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        # Unlike os.replace, link cannot overwrite an existing destination.
        os.link(temporary, path)
    except OSError as error:
        raise RestartStateError("Could not publish restart state") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary_created:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
    return path


def _regular_file_info(path):
    try:
        info = os.lstat(path)
    except OSError as error:
        raise RestartStateError("Restart state is missing or unavailable") from error
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or _is_reparse_point(info)
            or not 0 < info.st_size <= MAX_RESTART_STATE_BYTES):
        raise RestartStateError("Restart state is not a bounded private regular file")
    return info


def _same_file(left, right):
    return (left.st_dev, left.st_ino, left.st_size, left.st_mtime_ns) == (
        right.st_dev, right.st_ino, right.st_size, right.st_mtime_ns)


@contextlib.contextmanager
def _one_consumer(path):
    lock = path + ".lock"
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as error:
        raise RestartStateError("Restart state is already being consumed") from error
    try:
        os.close(descriptor)
        yield
    finally:
        os.unlink(lock)


def _load_manifest(path, profile, token, now=None, enforce_expiry=True):
    before = _regular_file_info(path)
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0)
                             | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            if not _same_file(before, os.fstat(stream.fileno())):
                raise RestartStateError("Restart state changed while opening")
            raw = stream.read(MAX_RESTART_STATE_BYTES + 1)
        if len(raw) > MAX_RESTART_STATE_BYTES:
            raise RestartStateError("Restart state exceeds 4 MiB")
        payload = json.loads(raw.decode("utf-8"), parse_constant=_reject_json_constant)
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError) as error:
        raise RestartStateError("Restart state is unreadable or invalid") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (not isinstance(payload, dict) or type(payload.get("version")) is not int
            or payload.get("version") != RESTART_STATE_VERSION
            or payload.get("profile") != profile or payload.get("token") != token):
        raise RestartStateError("Restart state identity or version does not match")
    created = _timestamp(payload.get("created_at"), "creation time")
    expires = _timestamp(payload.get("expires_at"), "expiry")
    if not 0 < expires - created <= MAX_RESTART_STATE_TTL:
        raise RestartStateError("Restart state lifetime is invalid")
    if enforce_expiry:
        current = _timestamp(time.time() if now is None else now, "current time")
        if created > current or current >= expires:
            raise RestartStateError("Restart state has expired or is future-dated")
    state = _state_copy(payload.get("state"))
    if not _same_file(before, _regular_file_info(path)):
        raise RestartStateError("Restart state changed during validation")
    return state


def _reject_json_constant(value):
    raise RestartStateError("Non-finite restart JSON constant: {}".format(value))


def consume_restart_state(path, profile, profiles_root=None, now=None):
    """Validate and consume exactly one dedicated manifest before devices open.

    Invalid/expired files are left untouched for explicit discard; another
    profile, traversal, symlink, hard link, and duplicate consume all fail.
    A stale lock after a process crash intentionally prevents automatic retry.
    """
    path, token = _manifest_path(path, profile, profiles_root)
    with _one_consumer(path):
        state = _load_manifest(path, profile, token, now=now)
        os.unlink(path)
    return state


def discard_restart_state(path, profile, profiles_root=None):
    """Discard only an identity-validated handoff, including an expired one.

    Intended for exec failure cleanup, not directory cleanup.  Never unlinks
    arbitrary files, other profiles' files, or an active consumer's lock.
    """
    path, token = _manifest_path(path, profile, profiles_root)
    if not os.path.lexists(path):
        return False
    with _one_consumer(path):
        _load_manifest(path, profile, token, enforce_expiry=False)
        os.unlink(path)
    return True


def build_restart_argv(executable, current_argv, restart_state_path,
                       profiles_root=None):
    """Return exec argv for this source Window.py, with exactly one handoff.

    Interpreter flags are the caller's responsibility (for example prepend
    ``-B`` after argv[0]).  Application argv is preserved except old restart
    handoffs.  Frozen binaries, non-Python executables and non-Window scripts
    fail closed.  Spaces stay within individual list elements; no shell runs.
    """
    if getattr(sys, "frozen", False):
        raise RestartStateError("Frozen PokeCon restart is not supported")
    if (not isinstance(executable, str) or not os.path.isabs(executable)
            or "\x00" in executable or not os.path.isfile(executable)
            or _PYTHON_NAME.fullmatch(os.path.basename(executable)) is None):
        raise RestartStateError("Restart requires the current Python executable")
    if (not isinstance(current_argv, (tuple, list)) or not current_argv
            or any(not isinstance(arg, str) or "\x00" in arg for arg in current_argv)):
        raise RestartStateError("Invalid source application argv")
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Window.py")
    if (not os.path.isfile(script) or not current_argv[0]
            or os.path.normcase(os.path.realpath(os.path.abspath(current_argv[0])))
            != os.path.normcase(os.path.realpath(script))):
        raise RestartStateError("Only this source Window.py can be restarted")
    if not isinstance(restart_state_path, str):
        raise RestartStateError("Invalid restart handoff path")
    profile = os.path.basename(os.path.dirname(os.path.abspath(restart_state_path)))
    path, _token = _manifest_path(restart_state_path, profile, profiles_root)
    _regular_file_info(path)
    result = [os.path.abspath(executable), script]
    args = list(current_argv[1:])
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--restart-state":
            if index + 1 >= len(args) or args[index + 1].startswith("--"):
                raise RestartStateError("Previous restart argument has no value")
            index += 2
        elif arg.startswith("--restart-state="):
            index += 1
        else:
            result.append(arg)
            index += 1
    result.extend(("--restart-state", path))
    return result
