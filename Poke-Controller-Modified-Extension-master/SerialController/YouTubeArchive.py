#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Persistent, sequential YouTube archive queue for PokeCon recordings."""
from __future__ import annotations

import base64
import contextlib
import datetime
import hashlib
import http.server
import json
import math
import mimetypes
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser


REMOTE_FILE_NAME = "youtube_remote.json"
CHANNEL_STORE_NAME = "youtube_channels.json"
QUEUE_DIRECTORY_NAME = "youtube_upload_queue"
DEFAULT_SEGMENT_SECONDS = 2 * 60 * 60
MAX_CLEANUP_ATTEMPTS = 30
MAX_UPLOAD_ATTEMPTS = 30
RESUMABLE_PUT_TRACKING_VERSION = 1
COMMANDS_VIDEO_MODE_COMPOSITE = "composite"
COMMANDS_VIDEO_MODE_VIDEO_ONLY = "video_only"
COMMANDS_VIDEO_MODE_POKECON_WINDOW = "pokecon_window"
COMMANDS_VIDEO_MODE_CHOICES = (
    (COMMANDS_VIDEO_MODE_COMPOSITE, "画像検知枠＋ログ（既存録画）"),
    (COMMANDS_VIDEO_MODE_VIDEO_ONLY, "ゲーム映像のみ"),
    (COMMANDS_VIDEO_MODE_POKECON_WINDOW, "PokeCon画面全体"),
)
YOUTUBE_SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
)
REMOTE_VERIFICATION_REQUIRED = "remote_verification_required"
REMOTE_PROCESSING_FAILED = "remote_processing_failed"
CLEANUP_ATTENTION_REQUIRED = "cleanup_attention_required"
UPLOAD_ATTENTION_REQUIRED = "upload_attention_required"
QUOTA_WAITING = "quota_waiting"
UPLOAD_INSERT_PAUSED = "upload_insert_paused"
QUOTA_PAUSE_FILE = "youtube_quota_pause.state"
SOURCE_VERIFICATION_REQUIRED = "source_verification_required"
INVALID_JOB = "invalid_job"
LOCAL_COMMIT_SUFFIX = ".local-commit"
UPLOAD_JOB_IDENTITY_VERSION = 2
NON_ACTIONABLE_UPLOAD_STATUSES = frozenset((
    "completed", "cancelled", "authentication_required",
    REMOTE_VERIFICATION_REQUIRED, REMOTE_PROCESSING_FAILED,
    CLEANUP_ATTENTION_REQUIRED, UPLOAD_ATTENTION_REQUIRED,
    SOURCE_VERIFICATION_REQUIRED, INVALID_JOB,
))
KNOWN_UPLOAD_STATUSES = frozenset((
    "pending", "waiting_media", "uploading", "awaiting_processing",
    "failed", "authentication_required", "cleanup_pending", QUOTA_WAITING,
)) | NON_ACTIONABLE_UPLOAD_STATUSES


class UploadSessionExpired(RuntimeError):
    pass


class UploadSourceChanged(RuntimeError):
    """Raised before a PUT when its pinned local byte source changed."""


class YouTubeAuthenticationRequired(RuntimeError):
    """Raised when a saved OAuth grant must be authorized again."""

    def __init__(self, message, profile_name="", oauth_error="invalid_grant"):
        super().__init__(str(message or "YouTubeの再認証が必要です。"))
        self.profile_name = str(profile_name or "")
        self.oauth_error = str(oauth_error or "invalid_grant")


class YouTubeVideoInsertQuotaExceeded(RuntimeError):
    """Raised only when creation of a new videos.insert session hits quota."""


def upload_job_is_actionable(job, now_epoch=None):
    """Return whether a durable job should be handed to an upload worker."""
    if not isinstance(job, dict):
        return True
    status = str(job.get("status", "pending") or "pending")
    if status == QUOTA_WAITING:
        try:
            retry_epoch = float(job.get("quota_retry_after_epoch", 0.0) or 0.0)
        except (TypeError, ValueError):
            return False
        now_epoch = time.time() if now_epoch is None else float(now_epoch)
        return bool(retry_epoch and now_epoch >= retry_epoch)
    if status == UPLOAD_ATTENTION_REQUIRED:
        error = str(job.get("error", "") or "")
        if (_is_invalid_description_error(error)
                and not job.get("permanent_request_error_at")):
            # One worker run migrates this legacy state to a sanitized retry.
            return True
        if _is_youtube_quota_error(error):
            # Legacy jobs did not persist a retry timestamp.  Let one worker
            # migrate them to quota_waiting; that durable state (plus the
            # queue-wide pause file) controls when the next API call is due.
            return True
    return status not in NON_ACTIONABLE_UPLOAD_STATUSES


def _job_can_progress_during_quota_pause(job):
    """Return whether work other than a new videos.insert remains."""
    if not isinstance(job, dict):
        return False
    status = str(job.get("status", "pending") or "pending")
    if status == "cleanup_pending":
        return True
    if status == QUOTA_WAITING:
        return False
    return any(
        str(segment.get("video_id", "") or "").strip()
        or str(segment.get("upload_url", "") or "").strip()
        for segment in job.get("segments", [])
        if isinstance(segment, dict))


def normalize_commands_video_mode(value):
    """Return the stable key stored in InputSets and upload jobs."""
    text = str(value or "").strip()
    aliases = {
        key: key for key, _label in COMMANDS_VIDEO_MODE_CHOICES
    }
    aliases.update({
        label: key for key, label in COMMANDS_VIDEO_MODE_CHOICES
    })
    # Accept early wording used while the setting was being developed.
    aliases.update({
        "Detection + logs": COMMANDS_VIDEO_MODE_COMPOSITE,
        "Video only": COMMANDS_VIDEO_MODE_VIDEO_ONLY,
        "PokeCon window": COMMANDS_VIDEO_MODE_POKECON_WINDOW,
    })
    return aliases.get(text, COMMANDS_VIDEO_MODE_COMPOSITE)


def commands_video_mode_label(value):
    key = normalize_commands_video_mode(value)
    return dict(COMMANDS_VIDEO_MODE_CHOICES)[key]


def _atomic_json(path, payload):
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = "{}.{}.tmp".format(path, uuid.uuid4().hex)
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            try:
                os.fsync(stream.fileno())
            except OSError:
                pass
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            try:
                os.remove(temporary)
            except OSError:
                pass


def _read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as stream:
            value = json.load(stream)
        return value
    except (OSError, ValueError):
        return default


def _is_youtube_quota_error(error):
    text = str(error or "").lower()
    if "youtube api http 403" in text:
        # YouTube reports project/daily upload exhaustion as HTTP 403 on some
        # API paths.  Match the documented quota reasons rather than every
        # 403 so ordinary permission/ownership failures remain actionable.
        return any(reason in text for reason in (
            "quotaexceeded",
            "uploadlimitexceeded",
            "dailylimitexceeded",
        ))
    exhausted = (
        "youtube api http 429" in text
        or "resource_exhausted" in text
        or "ratelimitexceeded" in text
        or "rate_limit_exceeded" in text)
    daily_insert = any(marker in text for marker in (
        "video uploads per day",
        "defaultvideoinsertperdayperproject",
        "video_insert",
        "quota_unit 1/d",
        '"quota_unit":"1/d"',
        "'quota_unit': '1/d'",
    ))
    # Other 429s (for example requests/minute) should use the ordinary bounded
    # retry/backoff path rather than freezing every upload for a full day.
    return bool(exhausted and daily_insert)


def _is_invalid_description_error(error):
    text = str(error or "").lower()
    return ("invaliddescription" in text
            or "invalid video description" in text)


def _is_permanent_youtube_request_error(error):
    """Return deterministic API request errors that retries cannot repair."""
    text = str(error or "").lower()
    return _is_invalid_description_error(error) or \
        "youtube api http 400" in text


def _quota_window_retry_after_epoch(error):
    """Return Google's guarded daily-window boundary, or zero if absent."""
    text = str(error or "")
    match = re.search(r'["\']window_start_time["\']\s*:\s*["\']?(\d+)',
                      text, flags=re.IGNORECASE)
    if match:
        # YouTube's daily video-insert response identifies the beginning of
        # the current 24-hour quota window.  Add a five-minute boundary guard
        # so several PokeCon instances do not all retry at the exact reset.
        return float(match.group(1)) + 24.0 * 60.0 * 60.0 + 5.0 * 60.0
    return 0.0


def _quota_retry_after_epoch(error, now_epoch=None):
    """Resolve the next safe retry without spending daily insert quota."""
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    window_retry = _quota_window_retry_after_epoch(error)
    if window_retry:
        return max(now_epoch, window_retry)
    # The quota response seen in production is a daily video-insert limit.
    # If Google omits its window metadata, prefer one conservative day over a
    # short polling loop which can consume more insert attempts in that day.
    return now_epoch + 24.0 * 60.0 * 60.0 + 5.0 * 60.0


def _quota_pause_path(queue_dir):
    return os.path.join(os.path.abspath(queue_dir), QUOTA_PAUSE_FILE)


def _write_quota_pause(queue_dir, retry_epoch, error):
    retry_epoch = float(retry_epoch)
    payload = {
        "version": 1,
        "reason": "youtube_video_insert_quota",
        "retry_after_epoch": retry_epoch,
        "retry_after": datetime.datetime.fromtimestamp(retry_epoch).isoformat(
            timespec="seconds"),
        "recorded_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "error": str(error or "")[-2000:],
    }
    _atomic_json(_quota_pause_path(queue_dir), payload)
    return payload


def _active_quota_pause(queue_dir, now_epoch=None):
    pause = _read_json(_quota_pause_path(queue_dir), {})
    if not isinstance(pause, dict):
        return {}
    try:
        retry_epoch = float(pause.get("retry_after_epoch", 0.0) or 0.0)
    except (TypeError, ValueError):
        return {}
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    return pause if retry_epoch > now_epoch else {}


def _mark_job_quota_waiting(path, job, error, now_epoch=None,
                            retry_epoch=None):
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    if retry_epoch is None:
        retry_epoch = _quota_retry_after_epoch(error, now_epoch=now_epoch)
    else:
        retry_epoch = max(now_epoch, float(retry_epoch))
    now = datetime.datetime.fromtimestamp(now_epoch).isoformat(
        timespec="seconds")
    job.setdefault("legacy_quota_attempts", int(
        job.get("attempts", 0) or 0))
    if job.get("updated_at"):
        job.setdefault("legacy_quota_updated_at", job.get("updated_at"))
    job["status"] = QUOTA_WAITING
    job["error"] = str(error)
    job["updated_at"] = now
    job["quota_waiting_at"] = now
    job["quota_retry_after_epoch"] = retry_epoch
    job["quota_retry_after"] = datetime.datetime.fromtimestamp(
        retry_epoch).isoformat(timespec="seconds")
    job["quota_attempts"] = int(job.get("quota_attempts", 0) or 0) + 1
    job.pop("upload_attention_required_at", None)
    job.pop("upload_attention_error", None)
    _atomic_json(path, job)
    return retry_epoch


def _archive_active_upload_error(job):
    """Move a superseded active error into durable diagnostic history."""
    error = str(job.get("error", "") or "").strip()
    if not error:
        job.pop("error", None)
        return False
    previous_at = str(job.get("updated_at", "") or "").strip()
    job["previous_upload_error"] = error[-4000:]
    if previous_at:
        job["previous_upload_error_at"] = previous_at
    job.pop("error", None)
    return True


def _recover_retryable_legacy_errors(queue_dir, paths, now_epoch=None):
    """Migrate jobs created before permanent-error/quota classification."""
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    quota_retry = 0.0
    # Some responses in the same quota wave include window_start_time while
    # others omit it.  Reuse the known daily boundary for all of them instead
    # of letting a conservative now+24h fallback postpone the whole queue.
    known_quota_retry = 0.0
    has_legacy_quota = False
    for path in paths:
        snapshot = _read_json(path, {})
        if not isinstance(snapshot, dict):
            continue
        status = str(snapshot.get("status", "") or "")
        error = str(snapshot.get("error", "") or "")
        if (status in ("failed", UPLOAD_ATTENTION_REQUIRED)
                and _is_youtube_quota_error(error)):
            has_legacy_quota = True
            known_quota_retry = max(
                known_quota_retry,
                _quota_window_retry_after_epoch(error))
    if has_legacy_quota:
        quota_retry = max(
            now_epoch,
            known_quota_retry or _quota_retry_after_epoch(
                "", now_epoch=now_epoch))
        # Fail safely: publish the queue-wide stop before rewriting any job.
        # If this durable write fails, every job retains its old actionable
        # state and a later watchdog run can retry the migration.
        _write_quota_pause(
            queue_dir, quota_retry,
            "Recovered YouTube daily video-insert quota state")
    for path in paths:
        # The GUI can cancel/re-enqueue a job while a worker is starting.
        # Serialize this one-time migration with those short state updates.
        with _upload_job_state_lock(path):
            job = _read_json(path, {})
            if not isinstance(job, dict):
                continue
            status = str(job.get("status", "") or "")
            error = str(job.get("error", "") or "")
            if (status in ("failed", UPLOAD_ATTENTION_REQUIRED)
                    and _is_youtube_quota_error(error)):
                quota_retry = max(
                    quota_retry,
                    _mark_job_quota_waiting(
                        path, job, error, now_epoch=now_epoch,
                        retry_epoch=quota_retry or None))
            elif (status == UPLOAD_ATTENTION_REQUIRED
                  and _is_invalid_description_error(error)
                  and not job.get("permanent_request_error_at")):
                # build_video_description now removes YouTube's forbidden
                # angle brackets. Retry these deterministic legacy failures
                # once after the queue-wide quota pause has elapsed.
                _archive_active_upload_error(job)
                job["status"] = "pending"
                job["legacy_invalid_description_attempts"] = int(
                    job.get("attempts", 0) or 0)
                job["attempts"] = 0
                job["description_sanitized_retry_at"] = (
                    datetime.datetime.fromtimestamp(now_epoch).isoformat(
                        timespec="seconds"))
                job["updated_at"] = job["description_sanitized_retry_at"]
                job.pop("upload_attention_required_at", None)
                job.pop("upload_attention_error", None)
                _atomic_json(path, job)
    return quota_retry


def _upload_job_schema_error(job):
    """Return a reason when a queue entry cannot be interpreted safely."""
    if not isinstance(job, dict):
        return "JSON objectではありません。"
    if type(job.get("version")) is not int or job.get("version") != 1:
        return "対応していない、または欠落したversionです。"
    identity_version = job.get("identity_version", 1)
    if type(identity_version) is not int or identity_version not in (1, 2):
        return "対応していないqueue job identity_versionです。"
    status = job.get("status")
    if not isinstance(status, str) or status not in KNOWN_UPLOAD_STATUSES:
        return "statusが不明または欠落しています。"
    for key in ("media_path", "session_dir"):
        value = job.get(key)
        if (not isinstance(value, str) or not value.strip()
                or not os.path.isabs(value)):
            return "{}は絶対パスの文字列である必要があります。".format(key)
    if ("session_identity" in job
            and (not isinstance(job.get("session_identity"), dict)
                 or not job.get("session_identity"))):
        return "session_identityが存在しますが不正または空です。"
    segments = job.get("segments")
    if not isinstance(segments, list):
        return "segmentsは配列である必要があります。"
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            return "segments[{}]はJSON objectではありません。".format(index)
        try:
            part = int(segment.get("part", 0) or 0)
            start = float(segment.get("start_seconds", 0.0) or 0.0)
            duration = float(segment.get("duration_seconds", 0.0) or 0.0)
            uploaded = int(segment.get("uploaded_bytes", 0) or 0)
        except (TypeError, ValueError, OverflowError):
            return "segments[{}]の数値が不正です。".format(index)
        if (part <= 0 or not math.isfinite(start)
                or not math.isfinite(duration) or start < 0.0
                or duration < 0.0 or uploaded < 0):
            return "segments[{}]の数値範囲が不正です。".format(index)
        for key in ("video_id", "upload_url", "local_path"):
            if key in segment and not isinstance(segment.get(key), str):
                return "segments[{}].{}は文字列である必要があります。".format(
                    index, key)
        if ("source_identity" in segment
                and not isinstance(segment.get("source_identity"), dict)):
            return "segments[{}].source_identityが不正です。".format(index)
        if ("upload_session_tracking_version" in segment
                and type(segment.get(
                    "upload_session_tracking_version")) is not int):
            return "segments[{}]のPUT tracking versionが不正です。".format(
                index)
        if ("put_attempted_at" in segment
                and not isinstance(segment.get("put_attempted_at"), str)):
            return "segments[{}].put_attempted_atが不正です。".format(index)
    return ""


def completed_upload_has_remote_proof(job):
    """Return whether every completed segment has a durable YouTube object."""
    if not isinstance(job, dict):
        return False
    segments = job.get("segments")
    return bool(
        isinstance(segments, list) and segments
        and all(isinstance(segment, dict)
                and str(segment.get("video_id", "") or "").strip()
                for segment in segments))


def _upload_job_identity(media_path, session_dir, identity_version=2):
    """Return the deterministic queue id for one recording intent.

    Version 1 used case-preserving absolute paths.  Windows paths are
    case-insensitive, so two callers could create distinct jobs for the same
    recording merely by spelling a drive/directory with different case.
    Version 2 hashes ``normcase`` paths while the validator continues to
    accept already-persisted version-1 jobs.
    """
    media_path = os.path.abspath(str(media_path or ""))
    session_dir = os.path.abspath(str(session_dir or ""))
    if int(identity_version) >= 2:
        media_path = os.path.normcase(media_path)
        session_dir = os.path.normcase(session_dir)
    return hashlib.sha256((media_path + "\0" + session_dir).encode(
        "utf-8")).hexdigest()[:24]


def _upload_job_identity_error(job, expected_id, media_path=None,
                               session_dir=None):
    """Require a queue payload to belong to its deterministic job path."""
    if not isinstance(job, dict):
        return "queue jobがJSON objectではありません。"
    expected_id = str(expected_id or "")
    actual_id = str(job.get("id", "") or "")
    if not expected_id or actual_id != expected_id:
        return "queue job IDがファイル名と一致しません。"
    try:
        actual_media = os.path.abspath(str(job.get("media_path", "") or ""))
        actual_session = os.path.abspath(str(
            job.get("session_dir", "") or ""))
        identity_version = job.get("identity_version", 1)
        if type(identity_version) is not int or identity_version not in (1, 2):
            return "queue job identity_versionが不正です。"
        derived_id = _upload_job_identity(
            actual_media, actual_session, identity_version)
        if derived_id != expected_id:
            return "queue job IDがmedia/session identityと一致しません。"
        if (media_path is not None
                and os.path.normcase(actual_media) != os.path.normcase(
                    os.path.abspath(str(media_path)))):
            return "queue jobのmedia_pathが要求された録画と一致しません。"
        if (session_dir is not None
                and os.path.normcase(actual_session) != os.path.normcase(
                    os.path.abspath(str(session_dir)))):
            return "queue jobのsession_dirが要求された録画と一致しません。"
    except (OSError, TypeError, ValueError):
        return "queue jobのmedia/session identityを確認できません。"
    return ""


def _equivalent_upload_job_base(queue_dir, media_path, session_dir):
    """Find one existing v1/v2 job for the same Windows path identity.

    Return ``(base_json_path, conflict)``.  Both a final entry and its hidden
    local-commit entry count as one base.  Multiple distinct bases are
    ambiguous remote intents and therefore fail closed instead of choosing a
    job that might already contain an upload URL or video id.
    """
    expected_media = os.path.normcase(os.path.abspath(media_path))
    expected_session = os.path.normcase(os.path.abspath(session_dir))
    try:
        names = os.listdir(queue_dir)
    except OSError:
        return "", False
    bases = set()
    for name in names:
        lower = name.lower()
        if lower.endswith((".json" + LOCAL_COMMIT_SUFFIX).lower()):
            base_name = name[:-len(LOCAL_COMMIT_SUFFIX)]
        elif lower.endswith(".json"):
            base_name = name
        else:
            continue
        candidate = os.path.join(queue_dir, name)
        if _is_link_or_reparse_point(candidate):
            continue
        value = _read_json(candidate, None)
        if not isinstance(value, dict):
            continue
        try:
            actual_media = os.path.normcase(os.path.abspath(str(
                value.get("media_path", "") or "")))
            actual_session = os.path.normcase(os.path.abspath(str(
                value.get("session_dir", "") or "")))
        except (OSError, TypeError, ValueError):
            continue
        if (actual_media == expected_media
                and actual_session == expected_session):
            bases.add(os.path.abspath(os.path.join(queue_dir, base_name)))
    if len(bases) > 1:
        return "", True
    return (next(iter(bases)) if bases else ""), False


def _quarantine_invalid_upload_job(path, message):
    """Preserve an unreadable queue payload and replace it with a safe stub."""
    path = os.path.abspath(path)
    quarantine_path = "{}.invalid.{}.bad".format(path, uuid.uuid4().hex)
    moved = False
    try:
        os.replace(path, quarantine_path)
        moved = True
        now = datetime.datetime.now().isoformat(timespec="seconds")
        _atomic_json(path, {
            "version": 1,
            "status": INVALID_JOB,
            "error": str(message or "YouTube upload jobが不正です。"),
            "invalid_job_at": now,
            "updated_at": now,
            "quarantined_payload_path": quarantine_path,
        })
    except Exception:
        if moved and not os.path.exists(path):
            try:
                os.replace(quarantine_path, path)
            except OSError:
                pass
        raise
    return INVALID_JOB


@contextlib.contextmanager
def _upload_job_state_lock(job_path):
    """Serialize the short read/transition/write phase for one queue job."""
    lock_path = os.path.abspath(str(job_path or "")) + ".state.lock"
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    stream = open(lock_path, "a+b")
    locked = False
    try:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            while True:
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    locked = True
                    break
                except OSError:
                    time.sleep(0.01)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            locked = True
        yield
    finally:
        if locked:
            try:
                if os.name == "nt":
                    import msvcrt
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        stream.close()


def youtube_data_root(settings_path):
    return os.path.dirname(os.path.abspath(settings_path))


def channel_store_path(settings_path):
    return os.path.join(youtube_data_root(settings_path), CHANNEL_STORE_NAME)


def upload_queue_dir(settings_path):
    return os.path.join(youtube_data_root(settings_path), QUEUE_DIRECTORY_NAME)


def _protect_secret(value):
    value = str(value or "")
    if not value:
        return {"scheme": "empty", "value": ""}
    raw = value.encode("utf-8")
    if os.name == "nt":
        try:
            import win32crypt
            protected = win32crypt.CryptProtectData(
                raw, "PokeCon YouTube", None, None, None, 0)
            return {
                "scheme": "dpapi",
                "value": base64.b64encode(protected).decode("ascii"),
            }
        except Exception as error:
            raise RuntimeError(
                "YouTube認証情報をWindows DPAPIで暗号化できません。") from error
    # Non-Windows development/test fallback. Restrict the containing file;
    # Windows production uses per-user DPAPI above.
    return {
        "scheme": "base64",
        "value": base64.b64encode(raw).decode("ascii"),
    }


def _unprotect_secret(payload):
    if not isinstance(payload, dict):
        return ""
    scheme = str(payload.get("scheme", "") or "")
    value = str(payload.get("value", "") or "")
    if not value:
        return ""
    raw = base64.b64decode(value.encode("ascii"))
    if scheme == "dpapi":
        import win32crypt
        raw = win32crypt.CryptUnprotectData(raw, None, None, None, 0)[1]
    return raw.decode("utf-8")


def load_channel_store(path):
    value = _read_json(path, {})
    if not isinstance(value, dict):
        value = {}
    profiles = value.get("profiles", {})
    if not isinstance(profiles, dict):
        profiles = {}
    return {
        "version": 1,
        "default_profile": str(value.get("default_profile", "") or ""),
        "profiles": profiles,
    }


def _save_channel_store_unlocked(path, store):
    """Persist one normalized store while the caller owns its state lock."""
    payload = {
        "version": 1,
        "default_profile": str(store.get("default_profile", "") or ""),
        "profiles": dict(store.get("profiles", {}) or {}),
    }
    _atomic_json(path, payload)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return payload


def save_channel_store(path, store):
    """Replace the complete store without racing another PokeCon writer."""
    with _upload_job_state_lock(path):
        return _save_channel_store_unlocked(path, store)


def channel_profile_names(path):
    return sorted(load_channel_store(path)["profiles"], key=str.casefold)


def set_default_channel_profile(path, name):
    name = str(name or "").strip()
    with _upload_job_state_lock(path):
        store = load_channel_store(path)
        if name and name not in store["profiles"]:
            raise ValueError("YouTubeチャンネル設定が見つかりません: " + name)
        store["default_profile"] = name
        return _save_channel_store_unlocked(path, store)


def remove_channel_profile(path, name):
    name = str(name or "").strip()
    with _upload_job_state_lock(path):
        store = load_channel_store(path)
        store["profiles"].pop(name, None)
        if store["default_profile"] == name:
            store["default_profile"] = next(
                iter(sorted(store["profiles"])), "")
        return _save_channel_store_unlocked(path, store)


def _oauth_client_from_file(path):
    value = _read_json(path, None)
    if not isinstance(value, dict):
        raise ValueError("OAuth client JSONを読み込めません。")
    client = value.get("installed") or value.get("web")
    if not isinstance(client, dict):
        raise ValueError("OAuth client JSONに installed/web 設定がありません。")
    client_id = str(client.get("client_id", "") or "")
    client_secret = str(client.get("client_secret", "") or "")
    auth_uri = str(client.get("auth_uri", "") or "https://accounts.google.com/o/oauth2/v2/auth")
    token_uri = str(client.get("token_uri", "") or "https://oauth2.googleapis.com/token")
    if not client_id or not client_secret:
        raise ValueError("OAuth client_id / client_secret がありません。")
    return client_id, client_secret, auth_uri, token_uri


def _urlencoded_post(url, fields, timeout=60):
    request = urllib.request.Request(
        url, data=urllib.parse.urlencode(fields).encode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        try:
            oauth_payload = json.loads(detail)
        except (TypeError, ValueError):
            oauth_payload = {}
        oauth_error = str(oauth_payload.get("error", "") or "") \
            if isinstance(oauth_payload, dict) else ""
        if oauth_error == "invalid_grant":
            description = str(oauth_payload.get(
                "error_description", "") or "")
            raise YouTubeAuthenticationRequired(
                description or "保存済みのYouTube認証が失効しました。再認証してください。",
                oauth_error=oauth_error) from error
        raise RuntimeError("YouTube OAuth HTTP {}: {}".format(error.code, detail[-1000:]))


def _api_json(url, token, method="GET", payload=None, headers=None, timeout=60):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
    }
    if payload is not None:
        request_headers["Content-Type"] = "application/json; charset=UTF-8"
    request_headers.update(headers or {})
    request = urllib.request.Request(
        url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}, response.headers
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError("YouTube API HTTP {}: {}".format(error.code, detail[-2000:]))


def authorize_installed_app(client_json_path, profile_name, store_path,
                            open_browser=webbrowser.open, timeout=300):
    """Run Google's localhost installed-app OAuth flow and save with DPAPI."""
    profile_name = str(profile_name or "").strip()
    if not profile_name:
        raise ValueError("チャンネル設定名を入力してください。")
    client_id, client_secret, auth_uri, token_uri = _oauth_client_from_file(
        client_json_path)
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    received = {}
    ready = threading.Event()

    class Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            received.update({key: values[0] for key, values in query.items() if values})
            message = "PokeConのYouTube認証を受け取りました。このタブを閉じてください。"
            body = message.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            ready.set()

        def log_message(self, _format, *_args):
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Callback)
    redirect_uri = "http://127.0.0.1:{}/".format(server.server_port)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(YOUTUBE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        open_browser(auth_uri + "?" + urllib.parse.urlencode(params))
        if not ready.wait(float(timeout)):
            raise TimeoutError("YouTube認証が5分以内に完了しませんでした。")
    finally:
        server.shutdown()
        server.server_close()
    if received.get("state") != state:
        raise RuntimeError("YouTube認証のstateが一致しません。")
    if received.get("error"):
        raise RuntimeError("YouTube認証が拒否されました: " + received["error"])
    token = _urlencoded_post(token_uri, {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": received.get("code", ""),
        "code_verifier": verifier,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    })
    refresh_token = str(token.get("refresh_token", "") or "")
    if not refresh_token:
        raise RuntimeError("refresh_tokenを取得できませんでした。再認証してください。")
    access_token = str(token.get("access_token", "") or "")
    channel_id = ""
    channel_title = ""
    if access_token:
        response, _headers = _api_json(
            "https://www.googleapis.com/youtube/v3/channels?part=id,snippet&mine=true",
            access_token)
        items = response.get("items", []) if isinstance(response, dict) else []
        if items:
            channel_id = str(items[0].get("id", "") or "")
            channel_title = str(dict(items[0].get("snippet", {}) or {}).get("title", "") or "")
    if not channel_id:
        # Never replace a known profile with credentials whose destination
        # channel cannot be proven.  A blank mine=true response is not a safe
        # upload target.
        raise RuntimeError(
            "認証したYouTubeチャンネルIDを確認できませんでした。"
            "チャンネルを作成済みのアカウントで再認証してください。")
    # The browser/token/API work above must not hold a process-wide file lock.
    # Serialize only the final read-modify-write so another PokeCon cannot lose
    # a simultaneous default/remove/authorization update.
    with _upload_job_state_lock(store_path):
        store = load_channel_store(store_path)
        store["profiles"][profile_name] = {
            "channel_id": channel_id,
            "channel_title": channel_title,
            "client_id": _protect_secret(client_id),
            "client_secret": _protect_secret(client_secret),
            "refresh_token": _protect_secret(refresh_token),
            "token_uri": token_uri,
            "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        if not store["default_profile"]:
            store["default_profile"] = profile_name
        _save_channel_store_unlocked(store_path, store)
    return {
        "profile": profile_name,
        "channel_id": channel_id,
        "channel_title": channel_title,
    }


def _resolve_profile(store_path, requested=""):
    store = load_channel_store(store_path)
    name = str(requested or "").strip() or store["default_profile"]
    profile = store["profiles"].get(name)
    if not name or not isinstance(profile, dict):
        raise RuntimeError("YouTubeチャンネルが未設定です。PokeConのRecordingから認証してください。")
    return name, profile


def _access_token(profile):
    response = _urlencoded_post(
        str(profile.get("token_uri", "") or "https://oauth2.googleapis.com/token"), {
            "client_id": _unprotect_secret(profile.get("client_id")),
            "client_secret": _unprotect_secret(profile.get("client_secret")),
            "refresh_token": _unprotect_secret(profile.get("refresh_token")),
            "grant_type": "refresh_token",
        })
    token = str(response.get("access_token", "") or "")
    if not token:
        raise RuntimeError("YouTube access_tokenを更新できませんでした。")
    return token


def _truncate_utf8(value, maximum=5000):
    raw = str(value or "").encode("utf-8")
    if len(raw) <= maximum:
        return str(value or "")
    suffix = "\n…(PokeConのローカル索引に続きがあります)"
    allowance = max(0, maximum - len(suffix.encode("utf-8")))
    return raw[:allowance].decode("utf-8", errors="ignore") + suffix


def _safe_video_description(value):
    """Remove characters rejected by videos.insert, then enforce 5,000 B."""
    text = str(value or "").replace("<", "＜").replace(">", "＞")
    text = "".join(
        character if (
            character in "\n\r\t"
            or (ord(character) >= 0x20
                and not 0x7f <= ord(character) <= 0x9f))
        else " "
        for character in text)
    return _truncate_utf8(text, 5000)


def format_timestamp(seconds):
    value = max(0, int(float(seconds or 0.0)))
    hours, value = divmod(value, 3600)
    minutes, seconds = divmod(value, 60)
    return "{}:{:02d}:{:02d}".format(hours, minutes, seconds) \
        if hours else "{}:{:02d}".format(minutes, seconds)


def _load_step_markers(session_dir):
    rows = []
    path = os.path.join(session_dir, "steps.jsonl")
    try:
        stream = open(path, "r", encoding="utf-8")
    except OSError:
        return rows
    previous = ""
    with stream:
        for line in stream:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            step = str(event.get("step_path", "") or "")
            if not step or step == previous:
                continue
            previous = step
            for key in ("video_time", "chunk_time", "command_time"):
                try:
                    if event.get(key) not in (None, ""):
                        rows.append((float(event[key]), step))
                        break
                except (TypeError, ValueError):
                    continue
    return rows


def build_video_description(job, segment_start=0.0, segment_duration=0.0):
    session_dir = str(job.get("session_dir", "") or "")
    end = float(segment_start) + max(0.0, float(segment_duration or 0.0))
    lines = [
        "PokeCon録画アーカイブ",
        "InputSet: {}".format(job.get("input_set") or "(未設定)"),
        "録画種別: {}".format(job.get("recording_kind") or "recording"),
    ]
    if job.get("command"):
        lines.append("Command: " + str(job["command"]))
    if job.get("commands_video_mode"):
        lines.append("映像内容: " + commands_video_mode_label(
            job.get("commands_video_mode")))
    lines.extend(("公開設定: 限定公開（リンクを知っている人のみ）", "", "タイムスタンプ"))
    markers = []
    # YouTube is the compact viewing index: emit state-machine Step
    # transitions only.  Function occurrences remain available in the local
    # common_function_index.json / DevStudio index, but including them here
    # expands every Step into its implementation details.
    for when, step in _load_step_markers(session_dir):
        if when < segment_start or (segment_duration and when >= end):
            continue
        markers.append((when - segment_start, "Step: " + step))
    markers.sort(key=lambda item: item[0])
    used = set()
    for when, label in markers:
        key = (int(when), label)
        if key in used:
            continue
        used.add(key)
        lines.append("{} {}".format(format_timestamp(when), label))
        if len(lines) >= 80:
            lines.append("（以降はDevStudio／ローカル索引を参照）")
            break
    if not markers:
        lines.append("0:00 録画開始")
    lines.extend(("", "YouTubeのタイムスタンプはStep遷移のみです。呼び出し元、関数、検知結果、ソーススナップショットは録画フォルダのローカル索引に保存されています。"))
    return _safe_video_description("\n".join(lines))


def _safe_title(job, part=1, total=1):
    pieces = ["PokeCon", str(job.get("input_set", "") or "")]
    if job.get("command"):
        pieces.append(str(job["command"]))
    pieces.append(str(job.get("created_at", "") or "")[:19].replace("T", " "))
    title = _safe_video_description(
        " - ".join(piece for piece in pieces if piece))
    # Titles cannot contain line/control characters.  Collapse whitespace
    # after applying the same forbidden-character rules as descriptions.
    title = " ".join(title.split())
    suffix = " ({}/{})".format(part, total) if total > 1 else ""
    # Reserve space before truncating so multi-part uploads never lose their
    # part identity at YouTube's 100-character title boundary.
    return title[:max(0, 100 - len(suffix))].rstrip() + suffix


def enqueue_upload_job(queue_dir, media_path, session_dir, input_set="",
                       channel_profile="", recording_kind="normal",
                       command="", delete_local=True, commands_video_mode="",
                       segment_seconds=DEFAULT_SEGMENT_SECONDS,
                       channel_profile_resolved="", channel_id_resolved="",
                       hold_for_local_commit=False):
    queue_dir = os.path.abspath(queue_dir)
    media_path = os.path.abspath(media_path)
    session_dir = os.path.abspath(session_dir or os.path.dirname(media_path))
    os.makedirs(queue_dir, exist_ok=True)
    # One finalized recording path represents one logical upload.  Keep this
    # stable when metadata/keyframes later change the directory mtime.  Reuse
    # a valid legacy v1 path when present; otherwise v2 normalizes path case so
    # concurrent PokeCon instances cannot enqueue the same Windows file twice.
    canonical_identity = _upload_job_identity(
        media_path, session_dir, UPLOAD_JOB_IDENTITY_VERSION)
    existing_base, identity_conflict = _equivalent_upload_job_base(
        queue_dir, media_path, session_dir)
    if identity_conflict:
        return ""
    path = existing_base or os.path.join(
        queue_dir, canonical_identity + ".json")
    identity = os.path.basename(path)[:-len(".json")]
    payload_identity_version = (
        UPLOAD_JOB_IDENTITY_VERSION
        if identity == canonical_identity else 1)
    staging_path = path + LOCAL_COMMIT_SUFFIX
    with _upload_job_state_lock(path):
        if os.path.lexists(path):
            if _is_link_or_reparse_point(path):
                _quarantine_invalid_upload_job(
                    path, "既存のqueue jobがlink/reparse pointです。")
                return ""
            existing = _read_json(path, None)
            if (isinstance(existing, dict)
                    and existing.get("status") in (INVALID_JOB, "cancelled")):
                return ""
            schema_error = _upload_job_schema_error(existing)
            if schema_error:
                # Never overwrite a corrupt/unknown entry.  It may contain a
                # resumable URL or video ID that cannot safely be recreated.
                _quarantine_invalid_upload_job(
                    path, "既存のYouTube upload jobを隔離しました: "
                    + schema_error)
                return ""
            identity_error = _upload_job_identity_error(
                existing, identity, media_path, session_dir)
            if identity_error:
                # A schema-valid job under the wrong deterministic filename
                # may contain remote state. Preserve it for manual recovery,
                # but never adopt or overwrite it for this recording.
                _quarantine_invalid_upload_job(
                    path, "既存のYouTube upload jobを隔離しました: "
                    + identity_error)
                return ""
            return path
        if os.path.lexists(staging_path):
            if not hold_for_local_commit:
                # A Commands rolling merge has deliberately kept this job
                # invisible to every (including older, already-running)
                # uploader.  A generic enqueue must never bypass that local
                # journal barrier by publishing a second final queue entry.
                return ""
            if _is_link_or_reparse_point(staging_path):
                _quarantine_invalid_upload_job(
                    staging_path,
                    "既存のlocal-commit queue jobがlink/reparse pointです。")
            else:
                staged = _read_json(staging_path, None)
                # Quarantine leaves an INVALID_JOB stub at this same hidden
                # name.  It was never worker-visible and has no remote state,
                # so an interrupted repair can safely replace that stub
                # directly without creating another ``.invalid.*.bad`` file.
                if not (isinstance(staged, dict)
                        and staged.get("status") == INVALID_JOB):
                    schema_error = _upload_job_schema_error(staged)
                    same_identity = False
                    if isinstance(staged, dict):
                        try:
                            same_identity = bool(
                                str(staged.get("id", "") or "") == identity
                                and os.path.normcase(os.path.abspath(str(
                                    staged.get("media_path", "") or "")))
                                == os.path.normcase(media_path)
                                and os.path.normcase(os.path.abspath(str(
                                    staged.get("session_dir", "") or "")))
                                == os.path.normcase(session_dir))
                        except (OSError, TypeError, ValueError):
                            same_identity = False
                    if (schema_error or not same_identity
                            or str(staged.get("status", "") or "") != "pending"):
                        _quarantine_invalid_upload_job(
                            staging_path,
                            "既存のlocal-commit YouTube upload jobが不正です: "
                            + (schema_error or "録画identityが一致しません。"))
                    else:
                        return staging_path
        payload = {
            "version": 1,
            "identity_version": payload_identity_version,
            "id": identity,
            "status": "pending",
            "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "media_path": media_path,
            "session_dir": session_dir,
            "input_set": str(input_set or ""),
            "channel_profile": str(channel_profile or ""),
            "recording_kind": str(recording_kind or "normal"),
            "command": str(command or ""),
            "commands_video_mode": normalize_commands_video_mode(
                commands_video_mode) if commands_video_mode else "",
            "privacy_status": "unlisted",
            "delete_local_after_processing": bool(delete_local),
            "segment_seconds": min(11 * 3600, max(
                10 * 60, int(segment_seconds or DEFAULT_SEGMENT_SECONDS))),
            "segments": [],
            "attempts": 0,
        }
        session_identity = _session_directory_identity_snapshot(session_dir)
        if session_identity is not None:
            # Cleanup can happen hours after enqueue.  Pin the directory object
            # now so replacing the timestamp folder with a junction/symlink
            # cannot turn later cleanup into deletion outside this recording.
            payload["session_identity"] = session_identity
            recording_targets = _snapshot_recording_cleanup_targets(payload)
            if recording_targets:
                # Active recordings refresh this immediately before the first
                # remote side effect, after the MP4 has become stable.
                payload["recording_cleanup_targets"] = recording_targets
        if str(channel_profile_resolved or "").strip():
            payload["channel_profile_resolved"] = str(
                channel_profile_resolved).strip()
        if str(channel_id_resolved or "").strip():
            payload["channel_id_resolved"] = str(
                channel_id_resolved).strip()
        write_path = staging_path if hold_for_local_commit else path
        _atomic_json(write_path, payload)
    return write_path


def release_upload_job_local_commit(staging_path):
    """Atomically publish a locally journaled upload job to old/new workers.

    ``enqueue_upload_job(..., hold_for_local_commit=True)`` writes a durable
    payload whose name does not end in ``.json``.  Existing detached upload
    workers therefore cannot observe it while Commands commits the merged and
    source metadata.  This function shares the final job's state lock and
    promotes that exact payload only after the local transaction is complete.

    The absolute final ``.json`` path is returned.  Releasing the same staging
    path again is idempotent; an invalid, missing, or conflicting payload
    returns an empty string without replacing a final queue job.
    """
    raw_path = str(staging_path or "").strip()
    if not raw_path:
        return ""
    staging_path = os.path.abspath(raw_path)
    if not staging_path.lower().endswith(
            (".json" + LOCAL_COMMIT_SUFFIX).lower()):
        return ""
    path = staging_path[:-len(LOCAL_COMMIT_SUFFIX)]
    if not path.lower().endswith(".json"):
        return ""

    with _upload_job_state_lock(path):
        identity_probe = _read_json(
            path if os.path.lexists(path) else staging_path, None)
        if isinstance(identity_probe, dict):
            _equivalent, identity_conflict = _equivalent_upload_job_base(
                os.path.dirname(path),
                identity_probe.get("media_path", ""),
                identity_probe.get("session_dir", ""))
            if identity_conflict:
                # Preserve every intent.  An older PokeCon may have created a
                # case-variant v1 job while this held v2 job was being locally
                # journaled; publishing/removing either entry is ambiguous.
                return ""
        if os.path.lexists(path):
            if _is_link_or_reparse_point(path):
                _quarantine_invalid_upload_job(
                    path, "既存のqueue jobがlink/reparse pointです。")
                return ""
            existing = _read_json(path, None)
            if (isinstance(existing, dict)
                    and existing.get("status") in (INVALID_JOB, "cancelled")):
                return ""
            schema_error = _upload_job_schema_error(existing)
            if schema_error:
                _quarantine_invalid_upload_job(
                    path, "既存のYouTube upload jobを隔離しました: "
                    + schema_error)
                return ""
            expected_id = os.path.basename(path)[:-len(".json")]
            identity_error = _upload_job_identity_error(
                existing, expected_id)
            if identity_error:
                _quarantine_invalid_upload_job(
                    path, "既存のYouTube upload jobを隔離しました: "
                    + identity_error)
                return ""
            # A previous release (or another PokeCon process) already won.
            # Remove only a demonstrably duplicate staging payload. A staged
            # conflict makes this release ambiguous even though the final job
            # is internally consistent, so preserve both and return failure.
            if os.path.lexists(staging_path):
                if _is_link_or_reparse_point(staging_path):
                    _quarantine_invalid_upload_job(
                        staging_path,
                        "local-commit queue jobがlink/reparse pointです。")
                    return ""
                staged = _read_json(staging_path, None)
                if (isinstance(staged, dict)
                        and staged.get("status") == INVALID_JOB):
                    return ""
                staged_error = _upload_job_schema_error(staged)
                if not staged_error:
                    staged_error = _upload_job_identity_error(
                        staged, expected_id,
                        existing.get("media_path", ""),
                        existing.get("session_dir", ""))
                if (not staged_error
                        and str(staged.get("status", "") or "") != "pending"):
                    staged_error = "local-commit queue jobがpendingではありません。"
                if staged_error:
                    _quarantine_invalid_upload_job(
                        staging_path,
                        "local-commit YouTube upload jobが不正です: "
                        + staged_error)
                    return ""
                try:
                    os.remove(staging_path)
                except OSError:
                    pass
            return path

        if not os.path.lexists(staging_path):
            return ""
        if _is_link_or_reparse_point(staging_path):
            _quarantine_invalid_upload_job(
                staging_path,
                "local-commit queue jobがlink/reparse pointです。")
            return ""
        staged = _read_json(staging_path, None)
        if (isinstance(staged, dict)
                and staged.get("status") == INVALID_JOB):
            return ""
        schema_error = _upload_job_schema_error(staged)
        expected_id = os.path.basename(path)[:-len(".json")]
        identity_error = "" if schema_error else _upload_job_identity_error(
            staged, expected_id)
        if (schema_error or not isinstance(staged, dict)
                or str(staged.get("status", "") or "") != "pending"
                or identity_error):
            _quarantine_invalid_upload_job(
                staging_path,
                "local-commit YouTube upload jobが不正です: "
                + (schema_error or identity_error
                   or "録画identityが一致しません。"))
            return ""
        os.replace(staging_path, path)
        return path


def cancel_upload_job(job_path, reason):
    """Atomically cancel only a not-yet-started local upload intent.

    The per-job state lock is shared with ``process_upload_job``.  A worker
    therefore either observes ``cancelled`` before claiming the job, or claims
    it first and makes this function return ``False``.  Persisted remote upload
    state is never modified.
    """
    raw_path = str(job_path or "").strip()
    if not raw_path:
        return False
    path = os.path.abspath(raw_path)
    with _upload_job_state_lock(path):
        if _is_link_or_reparse_point(path):
            return False
        job = _read_json(path, None)
        if not isinstance(job, dict):
            return False
        schema_error = _upload_job_schema_error(job)
        name = os.path.basename(path)
        expected_id = name[:-len(".json")] \
            if name.lower().endswith(".json") else ""
        if (schema_error
                or _upload_job_identity_error(job, expected_id)):
            # Cancellation must never rewrite a payload copied beneath a
            # different queue filename; it may describe another recording or
            # contain remote state owned by that other job.
            return False
        status = str(job.get("status", "") or "")
        has_remote_state = _job_has_remote_upload_state(job)
        if status == "cancelled":
            return not has_remote_state
        if status not in ("pending", "waiting_media"):
            return False
        if has_remote_state:
            return False
        now = datetime.datetime.now().isoformat(timespec="seconds")
        job["status"] = "cancelled"
        job["cancel_reason"] = str(reason or "").strip() or "cancelled"
        job["cancelled_at"] = now
        job["updated_at"] = now
        _atomic_json(path, job)
        return True


def _job_profile_name(job, store_path=""):
    for key in ("authentication_profile", "channel_profile_resolved",
                "channel_profile"):
        name = str(job.get(key, "") or "").strip()
        if name:
            return name
    if store_path:
        return str(load_channel_store(store_path).get(
            "default_profile", "") or "").strip()
    return ""


def _is_invalid_grant_error(value):
    return "invalid_grant" in str(value or "").lower()


def _job_has_remote_upload_state(job):
    for segment in job.get("segments", []):
        if not isinstance(segment, dict):
            continue
        try:
            uploaded_bytes = int(segment.get("uploaded_bytes", 0) or 0)
        except (TypeError, ValueError):
            # Malformed progress is uncertain remote state, so cancellation
            # must fail closed instead of erasing the intent.
            return True
        if (str(segment.get("video_id", "") or "").strip()
                or str(segment.get("upload_url", "") or "").strip()
                or uploaded_bytes > 0
                or str(segment.get("status", "") or "") == "uploaded"):
            return True
    remote = _read_json(os.path.join(
        str(job.get("session_dir", "") or ""), REMOTE_FILE_NAME), {})
    return any(
        str(video.get("video_id", "") or "").strip()
        for video in dict(remote or {}).get("videos", [])
        if isinstance(video, dict))


def _expired_session_may_have_completed_put(segment):
    """Fail closed when an expired URI may already represent a video."""
    try:
        uploaded_bytes = int(segment.get("uploaded_bytes", 0) or 0)
        tracking_version = int(segment.get(
            "upload_session_tracking_version", 0) or 0)
    except (TypeError, ValueError):
        return True
    # A URL written by an older PokeCon version has no durable proof that no
    # PUT occurred.  It is ambiguous even when uploaded_bytes remained zero:
    # the process may have died after YouTube accepted the final PUT but before
    # the response/video ID could be checkpointed.
    return bool(
        tracking_version != RESUMABLE_PUT_TRACKING_VERSION
        or str(segment.get("put_attempted_at", "") or "").strip()
        or uploaded_bytes > 0
        or str(segment.get("status", "") or "") == "uploaded")


def _job_remote_channel_id(job):
    remote = _read_json(os.path.join(
        str(job.get("session_dir", "") or ""), REMOTE_FILE_NAME), {})
    return str(dict(remote or {}).get("channel_id", "") or "").strip()


def _pin_job_channel_identity(job, profile_name, profile):
    """Pin a job to one YouTube channel before any remote side effect."""
    profile_name = str(profile_name or "").strip()
    current_channel_id = str(dict(profile or {}).get(
        "channel_id", "") or "").strip()
    pinned_channel_id = str(job.get(
        "channel_id_resolved", "") or "").strip()
    if not pinned_channel_id:
        pinned_channel_id = _job_remote_channel_id(job)
    if not pinned_channel_id and _job_has_remote_upload_state(job):
        raise YouTubeAuthenticationRequired(
            "既存アップロードのYouTubeチャンネルを特定できないため、"
            "自動再開を停止しました。新しい録画として再登録せず、"
            "youtube_remote.jsonまたはジョブを確認してください。",
            profile_name=profile_name, oauth_error="channel_identity_unknown")
    if not current_channel_id:
        raise YouTubeAuthenticationRequired(
            "認証済み設定からYouTubeチャンネルIDを確認できません。"
            "Recordingから同じチャンネルを再認証してください。",
            profile_name=profile_name, oauth_error="channel_identity_unknown")
    if pinned_channel_id and pinned_channel_id != current_channel_id:
        raise YouTubeAuthenticationRequired(
            "再認証されたYouTubeチャンネルが、このアップロードを開始した"
            "チャンネルと一致しません。誤ったチャンネルへの再送を防ぐため"
            "自動再開を停止しました。",
            profile_name=profile_name, oauth_error="channel_identity_mismatch")
    changed = False
    if str(job.get("channel_profile_resolved", "") or "") != profile_name:
        job["channel_profile_resolved"] = profile_name
        changed = True
    if str(job.get("channel_id_resolved", "") or "") != current_channel_id:
        job["channel_id_resolved"] = current_channel_id
        changed = True
    return changed


def _apply_job_authentication_required(job, error, profile_name=""):
    profile_name = str(profile_name or getattr(
        error, "profile_name", "") or _job_profile_name(job) or "")
    now = datetime.datetime.now().isoformat(timespec="seconds")
    job["status"] = "authentication_required"
    job["authentication_profile"] = profile_name
    if profile_name and not str(job.get(
            "channel_profile_resolved", "") or "").strip():
        job["channel_profile_resolved"] = profile_name
    job["authentication_required_at"] = now
    job["updated_at"] = now
    job["error"] = str(error)
    job["authentication_error"] = str(getattr(
        error, "oauth_error", "invalid_grant") or "invalid_grant")
    job["attempts"] = int(job.get("attempts", 0) or 0) + 1
    return job


def _mark_job_authentication_required(path, job, error, profile_name=""):
    """Mark fresh on-disk state without overwriting a concurrent transition."""
    path = os.path.abspath(path)
    with _upload_job_state_lock(path):
        current = _read_json(path, None)
        name = os.path.basename(path)
        expected_id = name[:-len(".json")] \
            if name.lower().endswith(".json") else ""
        if (not isinstance(current, dict)
                or _upload_job_schema_error(current)
                or _upload_job_identity_error(current, expected_id)):
            return False
        status = str(current.get("status", "") or "")
        if status in (
                "completed", "cancelled", "cleanup_pending",
                REMOTE_VERIFICATION_REQUIRED, REMOTE_PROCESSING_FAILED,
                CLEANUP_ATTENTION_REQUIRED, UPLOAD_ATTENTION_REQUIRED,
                SOURCE_VERIFICATION_REQUIRED, INVALID_JOB):
            return False
        _apply_job_authentication_required(
            current, error, profile_name=profile_name)
        _atomic_json(path, current)
        if isinstance(job, dict):
            job.clear()
            job.update(current)
        return True


def resume_upload_jobs_for_profile(queue_dir, store_path, profile_name):
    """Resume locally valid jobs blocked by an expired OAuth profile.

    Reauthorization must call this with the profile name that was replaced.
    Upload progress already stored in each job is deliberately preserved.
    """
    queue_dir = os.path.abspath(queue_dir)
    profile_name = str(profile_name or "").strip()
    if not profile_name:
        raise ValueError("再開するYouTubeチャンネル設定名がありません。")
    store = load_channel_store(store_path)
    if profile_name not in store.get("profiles", {}):
        raise ValueError("YouTubeチャンネル設定が見つかりません: " + profile_name)
    profile = store["profiles"][profile_name]
    try:
        paths = sorted(
            os.path.join(queue_dir, name) for name in os.listdir(queue_dir)
            if name.endswith(".json"))
    except OSError:
        return []
    resumed = []
    now = datetime.datetime.now().isoformat(timespec="seconds")
    for path in paths:
        with _upload_job_state_lock(path):
            if _is_link_or_reparse_point(path):
                continue
            job = _read_json(path, None)
            name = os.path.basename(path)
            expected_id = name[:-len(".json")] \
                if name.lower().endswith(".json") else ""
            if (not isinstance(job, dict)
                    or _upload_job_schema_error(job)
                    or _upload_job_identity_error(job, expected_id)):
                continue
            status = str(job.get("status", "") or "")
            if status != "authentication_required" and not (
                    status == "failed"
                    and _is_invalid_grant_error(job.get("error", ""))):
                continue
            job_profile = _job_profile_name(job) or str(
                store.get("default_profile", "") or "").strip()
            if job_profile != profile_name:
                continue
            try:
                _pin_job_channel_identity(job, profile_name, profile)
            except YouTubeAuthenticationRequired as error:
                _apply_job_authentication_required(
                    job, error, profile_name=profile_name)
                _atomic_json(path, job)
                continue
            # Reauthorization unblocks the credential state, independently of
            # whether an external/shared recording root is mounted right now.
            # process_upload_job will durably wait for missing local media while
            # still polling any already-uploaded video IDs.
            job["status"] = "pending"
            job["updated_at"] = now
            job.pop("error", None)
            job.pop("authentication_error", None)
            job.pop("authentication_required_at", None)
            job.pop("authentication_profile", None)
            _atomic_json(path, job)
            resumed.append(path)
    return resumed


def youtube_watch_url(video_id, seconds=0.0):
    video_id = str(video_id or "").strip()
    if not video_id:
        return ""
    return "https://www.youtube.com/watch?" + urllib.parse.urlencode({
        "v": video_id,
        "t": "{}s".format(max(0, int(float(seconds or 0.0)))),
    })


def remote_video_for_time(remote, seconds):
    when = max(0.0, float(seconds or 0.0))
    videos = remote.get("videos", []) if isinstance(remote, dict) else []
    for position, video in enumerate(videos):
        start = float(video.get("start_seconds", 0.0) or 0.0)
        duration = float(video.get("duration_seconds", 0.0) or 0.0)
        if when >= start and (duration <= 0.0 or when < start + duration or position == len(videos) - 1):
            return video, max(0.0, when - start)
    return (videos[-1], max(0.0, when - float(videos[-1].get("start_seconds", 0.0) or 0.0))) \
        if videos else (None, when)


def load_remote_video(session_dir):
    value = _read_json(os.path.join(session_dir, REMOTE_FILE_NAME), {})
    return value if isinstance(value, dict) else {}


def remote_url_for_time(session_dir, seconds):
    video, relative = remote_video_for_time(load_remote_video(session_dir), seconds)
    return youtube_watch_url(video.get("video_id", ""), relative) if video else ""


def launch_upload_worker(queue_dir, store_path, wait_pid=0):
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "YouTubeUploadWorker.py")
    python = sys.executable
    if os.name == "nt":
        candidate = os.path.join(os.path.dirname(python), "pythonw.exe")
        if os.path.isfile(candidate):
            python = candidate
    command = [python, script, "--queue-dir", os.path.abspath(queue_dir),
               "--store", os.path.abspath(store_path)]
    if wait_pid:
        command.extend(("--wait-pid", str(int(wait_pid))))
    options = {"cwd": os.path.dirname(script), "close_fds": True}
    if os.name == "nt":
        options["creationflags"] = (
            getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000))
    return subprocess.Popen(command, **options)


def _ffmpeg_tools():
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg:
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg = None
    if ffmpeg and not ffprobe:
        candidate = os.path.join(os.path.dirname(ffmpeg), "ffprobe.exe" if os.name == "nt" else "ffprobe")
        if os.path.isfile(candidate):
            ffprobe = candidate
    return ffmpeg, ffprobe


def _probe_duration(path):
    _ffmpeg, ffprobe = _ffmpeg_tools()
    if ffprobe:
        completed = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if completed.returncode == 0:
            try:
                return max(0.0, float(completed.stdout.strip()))
            except ValueError:
                pass
    try:
        import cv2
        capture = cv2.VideoCapture(path)
        try:
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
            frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
            return frames / fps if fps > 0 else 0.0
        finally:
            capture.release()
    except Exception:
        return 0.0


def _materialize_segment(job, segment, total):
    source = job["media_path"]
    if total <= 1:
        return source
    ffmpeg, _ffprobe = _ffmpeg_tools()
    if not ffmpeg:
        raise RuntimeError("長時間録画の分割にFFmpegが必要です。")
    directory = os.path.join(job["session_dir"], ".youtube_segments")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "part_{:03d}.mp4".format(int(segment["part"])))
    if os.path.isfile(path) and os.path.getsize(path) > 1024:
        return path
    temporary = path + ".tmp.mp4"
    command = [
        ffmpeg, "-y", "-ss", "{:.6f}".format(segment["start_seconds"]),
        "-i", source, "-t", "{:.6f}".format(segment["duration_seconds"]),
        "-map", "0:v:0", "-map", "0:a?", "-c", "copy",
        "-movflags", "+faststart", temporary,
    ]
    options = {"stdout": subprocess.DEVNULL, "stderr": subprocess.PIPE, "text": True}
    if os.name == "nt":
        options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    completed = subprocess.run(command, **options)
    if completed.returncode != 0 or not os.path.isfile(temporary):
        raise RuntimeError("YouTube用分割に失敗しました: " + str(completed.stderr or "")[-1000:])
    os.replace(temporary, path)
    return path


def _initiate_resumable_upload(token, path, title, description, privacy):
    size = os.path.getsize(path)
    mime = mimetypes.guess_type(path)[0] or "video/mp4"
    _response, headers = _api_json(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        token, method="POST", payload={
            "snippet": {"title": title, "description": description,
                        "categoryId": "20"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
        }, headers={
            "X-Upload-Content-Length": str(size),
            "X-Upload-Content-Type": mime,
        })
    location = headers.get("Location")
    if not location:
        raise RuntimeError("YouTube resumable upload URLを取得できませんでした。")
    return location


def _resumable_upload_offset(upload_url, token, size):
    request = urllib.request.Request(
        upload_url, data=b"", method="PUT", headers={
            "Authorization": "Bearer " + token,
            "Content-Length": "0",
            "Content-Range": "bytes */{}".format(size),
        })
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            if response.status in (200, 201):
                try:
                    value = json.loads(raw.decode("utf-8")) if raw else {}
                except (TypeError, ValueError) as error:
                    raise RuntimeError(
                        "YouTube upload完了応答のvideo IDを確認できません。") \
                        from error
                video_id = str(value.get("id", "") or "") \
                    if isinstance(value, dict) else ""
                if not video_id:
                    raise RuntimeError(
                        "YouTube upload完了応答にvideo IDがありません。"
                        "同じresumable sessionを保持して再確認します。")
                return size, video_id
    except urllib.error.HTTPError as error:
        if error.code == 308:
            acknowledged = str(error.headers.get("Range", "") or "")
            if "-" in acknowledged:
                try:
                    return int(acknowledged.rsplit("-", 1)[-1]) + 1, ""
                except ValueError:
                    pass
            return 0, ""
        if error.code in (404, 410):
            raise UploadSessionExpired(
                "YouTube resumable upload session expired")
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            "YouTube upload status HTTP {}: {}".format(
                error.code, detail[-2000:]))
    return 0, ""


def _upload_resumable(path, token, upload_url, progress=None,
                      chunk_size=8 * 1024 * 1024,
                      expected_identity=None, before_put=None):
    if expected_identity is not None:
        _require_source_identity(path, expected_identity)
    size = os.path.getsize(path)
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    if expected_identity is not None:
        _require_source_identity(path, expected_identity)
    offset, completed_video_id = _resumable_upload_offset(
        upload_url, token, size)
    if completed_video_id:
        return completed_video_id
    if callable(progress) and offset:
        progress(offset, size)
    no_progress_responses = 0
    with open(path, "rb") as stream:
        while offset < size:
            if expected_identity is not None:
                _require_source_identity(path, expected_identity)
            stream.seek(offset)
            data = stream.read(min(chunk_size, size - offset))
            end = offset + len(data) - 1
            if expected_identity is not None:
                # Check again after reading so an in-place write during the
                # read cannot mix byte generations in one remote video.
                _require_source_identity(path, expected_identity)
            if callable(before_put):
                # The durable marker must precede the network request.  If the
                # response/video ID is then lost, an expired URI is ambiguous
                # and must never be replaced with an automatic re-upload.
                before_put(offset, size)
            if expected_identity is not None:
                _require_source_identity(path, expected_identity)
            request = urllib.request.Request(
                upload_url, data=data, method="PUT", headers={
                    "Authorization": "Bearer " + token,
                    "Content-Type": mime,
                    "Content-Length": str(len(data)),
                    "Content-Range": "bytes {}-{}/{}".format(offset, end, size),
                })
            try:
                with urllib.request.urlopen(request, timeout=180) as response:
                    raw = response.read()
                    if response.status in (200, 201):
                        try:
                            value = json.loads(raw.decode("utf-8")) if raw else {}
                        except (TypeError, ValueError) as error:
                            raise RuntimeError(
                                "YouTube upload完了応答のvideo IDを確認できません。") \
                                from error
                        video_id = str(value.get("id", "") or "") \
                            if isinstance(value, dict) else ""
                        if not video_id:
                            raise RuntimeError(
                                "YouTube upload完了応答にvideo IDがありません。"
                                "同じresumable sessionを保持して再確認します。")
                        return video_id
                    raise RuntimeError(
                        "YouTube uploadの予期しない成功応答です: HTTP {}".format(
                            response.status))
            except urllib.error.HTTPError as error:
                if error.code == 308:
                    acknowledged = str(error.headers.get("Range", "") or "")
                    next_offset = None
                    if "-" in acknowledged:
                        try:
                            candidate = int(
                                acknowledged.rsplit("-", 1)[-1]) + 1
                            if 0 <= candidate <= size:
                                next_offset = candidate
                        except ValueError:
                            pass
                    if next_offset is None:
                        # A 308 without a valid Range does not acknowledge the
                        # chunk.  Query the authoritative session offset and
                        # retry from there; never advance to ``end + 1``.
                        if expected_identity is not None:
                            _require_source_identity(
                                path, expected_identity)
                        next_offset, completed_video_id = (
                            _resumable_upload_offset(upload_url, token, size))
                        if completed_video_id:
                            return completed_video_id
                    if next_offset == offset:
                        no_progress_responses += 1
                        if no_progress_responses >= 5:
                            raise RuntimeError(
                                "YouTube resumable uploadの受信位置を"
                                "確認できません。同じsessionから再試行します。")
                    else:
                        no_progress_responses = 0
                    offset = next_offset
                    if callable(progress) and offset:
                        progress(offset, size)
                    continue
                if error.code in (404, 410):
                    raise UploadSessionExpired(
                        "YouTube resumable upload session expired")
                detail = error.read().decode("utf-8", errors="replace")
                raise RuntimeError("YouTube upload HTTP {}: {}".format(error.code, detail[-2000:]))
            offset = end + 1
            if callable(progress):
                progress(offset, size)
    raise RuntimeError("YouTube upload完了応答にvideo IDがありません。")


def _processing_status(token, video_id):
    response, _headers = _api_json(
        "https://www.googleapis.com/youtube/v3/videos?" + urllib.parse.urlencode({
            "part": "status,processingDetails", "id": video_id}), token)
    items = response.get("items", []) if isinstance(response, dict) else []
    if not items:
        return "missing"
    item = items[0]
    upload_status = str(dict(item.get("status", {}) or {}).get("uploadStatus", "") or "")
    processing = str(dict(item.get("processingDetails", {}) or {}).get("processingStatus", "") or "")
    if (upload_status in ("rejected", "failed", "deleted")
            or processing == "failed"):
        return "failed"
    if upload_status == "processed" or processing == "succeeded":
        return "processed"
    if processing == "terminated":
        # Per the YouTube API this means processing information is no longer
        # available, not necessarily that processing failed.  Keep the remote
        # ID and require manual verification rather than retrying an upload.
        return "terminated"
    return "processing"


def _write_remote(job, profile_name, profile):
    videos = []
    for segment in job.get("segments", []):
        if not segment.get("video_id"):
            continue
        videos.append({
            "part": segment["part"],
            "video_id": segment["video_id"],
            "url": youtube_watch_url(segment["video_id"], 0),
            "start_seconds": segment["start_seconds"],
            "duration_seconds": segment["duration_seconds"],
            "processing_status": segment.get("processing_status", ""),
        })
    remote = {
        "version": 1,
        "provider": "youtube",
        "privacy_status": "unlisted",
        "channel_profile": profile_name,
        "channel_id": str(profile.get("channel_id", "") or ""),
        "channel_title": str(profile.get("channel_title", "") or ""),
        "input_set": job.get("input_set", ""),
        "recording_kind": job.get("recording_kind", ""),
        "commands_video_mode": job.get("commands_video_mode", ""),
        "uploaded_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "videos": videos,
    }
    now = datetime.datetime.now().isoformat(timespec="seconds")
    if not _cleanup_session_identity_matches(job):
        # A timestamp directory can be deleted/recreated or replaced with a
        # junction while an upload is in flight.  Never write remote metadata
        # into that different object.
        job["remote_index_skip_reason"] = "session_identity_unverified"
        job["remote_index_skipped_at"] = now
        return remote
    try:
        _atomic_json(os.path.join(
            job["session_dir"], REMOTE_FILE_NAME), remote)
        index_path = os.path.join(
            job["session_dir"], "common_function_index.json")
        index = _read_json(index_path, None)
        if isinstance(index, dict):
            for occurrence in index.get("occurrences", []):
                if not isinstance(occurrence, dict):
                    continue
                video, relative = remote_video_for_time(
                    remote, occurrence.get("start_seconds", 0.0))
                if video and video.get("video_id"):
                    occurrence["youtube"] = {
                        "video_id": video["video_id"],
                        "seconds": relative,
                        "url": youtube_watch_url(
                            video["video_id"], relative),
                    }
            _atomic_json(index_path, index)
        metadata_path = os.path.join(
            job["session_dir"], "command_monitor.json")
        metadata = _read_json(metadata_path, None)
        if isinstance(metadata, dict):
            metadata["youtube"] = remote
            _atomic_json(metadata_path, metadata)
    except Exception as error:
        # The queue job is the authoritative no-duplicate checkpoint.  Index
        # files are helpful mirrors, so their failure must not make a terminal
        # remote state actionable again.
        job["remote_index_error"] = str(error)
        job["remote_index_error_at"] = now
    return remote


def _uploaded_recording_cleanup_paths(job):
    raw_session = str(job.get("session_dir", "") or "").strip()
    if not raw_session:
        return "", [], ""
    session = os.path.abspath(raw_session)
    allowed_names = {
        "recording.mp4", "recording.avi", "recording.wav",
        "recording_presentation_aligned.wav",
    }
    candidates = [job.get("media_path", "")]
    candidates.extend(os.path.join(session, name) for name in allowed_names)
    safe_files = []
    for raw in candidates:
        path = os.path.abspath(str(raw or ""))
        try:
            inside = os.path.normcase(os.path.commonpath(
                [session, path])) == os.path.normcase(session)
        except ValueError:
            inside = False
        if (inside and os.path.basename(path) in allowed_names
                and path not in safe_files):
            safe_files.append(path)
    segment_dir = os.path.join(session, ".youtube_segments")
    return session, safe_files, segment_dir


def _is_link_or_reparse_point(path):
    """Reject POSIX links and Windows junction/reparse-point traversal."""
    try:
        details = os.lstat(path)
    except OSError:
        return False
    attributes = int(getattr(details, "st_file_attributes", 0) or 0)
    reparse_flag = int(getattr(
        stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400) or 0x400)
    return bool(stat.S_ISLNK(details.st_mode) or attributes & reparse_flag)


def _session_directory_identity_snapshot(path):
    """Return the stable identity of one real recording-session directory."""
    raw_path = str(path or "").strip()
    if not raw_path:
        return None
    path = os.path.abspath(raw_path)
    if _is_link_or_reparse_point(path):
        return None
    try:
        details = os.stat(path, follow_symlinks=False)
    except OSError:
        return None
    if not stat.S_ISDIR(details.st_mode):
        return None
    return {
        "path": path,
        "realpath": os.path.normcase(os.path.realpath(path)),
        "device": int(getattr(details, "st_dev", 0) or 0),
        "inode": int(getattr(details, "st_ino", 0) or 0),
    }


def _cleanup_session_identity_matches(job):
    """Verify that cleanup still targets the directory captured at enqueue."""
    expected = job.get("session_identity", {}) \
        if isinstance(job, dict) else {}
    if not isinstance(expected, dict) or not expected:
        return False
    session = os.path.abspath(str(job.get("session_dir", "") or ""))
    current = _session_directory_identity_snapshot(session)
    if current is None:
        return False
    try:
        expected_path = os.path.normcase(os.path.abspath(str(
            expected.get("path", "") or "")))
        expected_realpath = os.path.normcase(os.path.realpath(str(
            expected.get("realpath", "") or "")))
        return bool(
            expected_path == os.path.normcase(session)
            and expected_realpath == current["realpath"]
            and int(expected.get("device", 0) or 0) == current["device"]
            and int(expected.get("inode", 0) or 0) == current["inode"])
    except (OSError, TypeError, ValueError):
        return False


def _realpath_is_within(root, path):
    root = os.path.normcase(os.path.realpath(os.path.abspath(root)))
    path = os.path.normcase(os.path.realpath(os.path.abspath(path)))
    try:
        return os.path.commonpath([root, path]) == root
    except ValueError:
        return False


def _segment_cleanup_path_is_safe(session, path):
    """Verify every path component below a session is a real local object."""
    session = os.path.abspath(session)
    path = os.path.abspath(path)
    if _is_link_or_reparse_point(session):
        return False
    if not _realpath_is_within(session, path):
        return False
    try:
        relative = os.path.relpath(path, session)
    except ValueError:
        return False
    if relative in ("", ".") or relative == os.pardir \
            or relative.startswith(os.pardir + os.sep):
        return False
    current = session
    for part in relative.split(os.sep):
        current = os.path.join(current, part)
        if _is_link_or_reparse_point(current):
            return False
    return True


def _cleanup_target_snapshot(path, kind):
    if _is_link_or_reparse_point(path):
        return None
    try:
        details = os.stat(path, follow_symlinks=False)
    except OSError:
        return None
    if kind == "file" and not stat.S_ISREG(details.st_mode):
        return None
    if kind == "directory" and not stat.S_ISDIR(details.st_mode):
        return None
    return {
        "path": os.path.abspath(path),
        "kind": kind,
        "device": int(getattr(details, "st_dev", 0) or 0),
        "inode": int(getattr(details, "st_ino", 0) or 0),
        "size": int(getattr(details, "st_size", 0) or 0),
        "mtime_ns": int(getattr(
            details, "st_mtime_ns",
            int(float(getattr(details, "st_mtime", 0.0) or 0.0) * 1e9))),
        "ctime_ns": int(getattr(
            details, "st_ctime_ns",
            int(float(getattr(details, "st_ctime", 0.0) or 0.0) * 1e9))),
    }


def _source_identity_snapshot(job, path):
    """Pin one regular upload source inside the original session object."""
    session = os.path.abspath(str(job.get("session_dir", "") or ""))
    path = os.path.abspath(str(path or ""))
    if (not _cleanup_session_identity_matches(job)
            or not _segment_cleanup_path_is_safe(session, path)):
        return None
    identity = _cleanup_target_snapshot(path, "file")
    if identity is None:
        return None
    identity["realpath"] = os.path.normcase(os.path.realpath(path))
    return identity


def _source_identity_matches(path, expected):
    """Verify exact bytes are still represented by a pinned file identity."""
    if not isinstance(expected, dict) or not expected:
        return False
    path = os.path.abspath(str(path or ""))
    try:
        expected_path = os.path.normcase(os.path.abspath(str(
            expected.get("path", "") or "")))
    except (OSError, TypeError, ValueError):
        return False
    if expected_path != os.path.normcase(path):
        return False
    current = _cleanup_target_snapshot(path, "file")
    if current is None:
        return False
    expected_realpath = str(expected.get("realpath", "") or "").strip()
    if (expected_realpath
            and os.path.normcase(os.path.realpath(path))
            != os.path.normcase(expected_realpath)):
        return False
    return _cleanup_identity_matches(current, expected, "file")


def _require_source_identity(path, expected):
    if not _source_identity_matches(path, expected):
        raise UploadSourceChanged(
            "YouTube upload元ファイルが開始時の内容から変更されました: "
            + os.path.abspath(str(path or "")))


def _recording_media_source_identity(job):
    """Return the pre-remote snapshot for the job's primary recording."""
    media_path = os.path.normcase(os.path.abspath(str(
        job.get("media_path", "") or "")))
    targets = job.get("recording_cleanup_targets", [])
    if not isinstance(targets, list):
        return None
    for target in targets:
        if not isinstance(target, dict) or target.get("kind") != "file":
            continue
        try:
            target_path = os.path.normcase(os.path.abspath(str(
                target.get("path", "") or "")))
        except (OSError, TypeError, ValueError):
            continue
        if target_path == media_path:
            return dict(target)
    return None


def _snapshot_recording_cleanup_targets(job):
    """Pin recording files before any remote upload can reference them."""
    session, files, _segment_dir = _uploaded_recording_cleanup_paths(job)
    if not _cleanup_session_identity_matches(job):
        return []
    targets = []
    for path in files:
        target = _cleanup_target_snapshot(path, "file")
        if (target is not None
                and _segment_cleanup_path_is_safe(session, target["path"])):
            targets.append(target)
    return targets


def _snapshot_uploaded_recording_cleanup_targets(job):
    """Freeze exact local objects before the first destructive operation."""
    session, _files, segment_dir = _uploaded_recording_cleanup_paths(job)
    if not _cleanup_session_identity_matches(job):
        return []
    # Direct recording files must have been pinned before the first remote
    # upload.  Reconstructing them now from their names could delete a newer
    # recording that replaced the uploaded file before cleanup began.
    pinned = job.get("recording_cleanup_targets", [])
    targets = []
    skipped_replacements = []
    if isinstance(pinned, list):
        for target in pinned:
            if (not isinstance(target, dict)
                    or target.get("kind") != "file"
                    or not _cleanup_target_is_safe(job, target)):
                continue
            if _cleanup_target_matches(job, target):
                targets.append(dict(target))
            elif os.path.lexists(str(target.get("path", "") or "")):
                skipped_replacements.append(os.path.abspath(str(
                    target.get("path", "") or "")))
    if (os.path.isdir(segment_dir)
            and _segment_cleanup_path_is_safe(session, segment_dir)):
        expected_parts = {}
        for segment in job.get("segments", []):
            source_identity = segment.get("source_identity") \
                if isinstance(segment, dict) else None
            if not isinstance(source_identity, dict):
                continue
            source_path = os.path.abspath(str(
                source_identity.get("path", "") or ""))
            try:
                inside_segment_dir = os.path.normcase(os.path.commonpath(
                    [segment_dir, source_path])) == os.path.normcase(
                        segment_dir)
            except ValueError:
                inside_segment_dir = False
            if (inside_segment_dir
                    and source_path != os.path.abspath(segment_dir)):
                expected_parts[os.path.normcase(source_path)] = dict(
                    source_identity)
        try:
            walked = list(os.walk(segment_dir, topdown=False, followlinks=False))
        except OSError:
            walked = []
        protected_paths = []
        untracked_files = []
        directory_candidates = []
        for root, directories, names in walked:
            for name in names:
                file_path = os.path.abspath(os.path.join(root, name))
                expected = expected_parts.get(os.path.normcase(file_path))
                if (expected is not None
                        and _cleanup_target_is_safe(job, expected)
                        and _source_identity_matches(file_path, expected)):
                    targets.append(dict(expected))
                else:
                    protected_paths.append(file_path)
                    if expected is not None:
                        skipped_replacements.append(file_path)
                    else:
                        untracked_files.append(file_path)
            for name in directories:
                directory_path = os.path.abspath(os.path.join(root, name))
                if _is_link_or_reparse_point(directory_path):
                    protected_paths.append(directory_path)
                else:
                    directory_candidates.append(directory_path)
            directory_candidates.append(os.path.abspath(root))
        for directory_path in sorted(
                set(directory_candidates), key=lambda value: value.count(os.sep),
                reverse=True):
            try:
                contains_protected = any(
                    os.path.normcase(os.path.commonpath(
                        [directory_path, protected]))
                    == os.path.normcase(directory_path)
                    for protected in protected_paths)
            except ValueError:
                contains_protected = True
            if contains_protected:
                continue
            target = _cleanup_target_snapshot(directory_path, "directory")
            if (target is not None
                    and _cleanup_target_is_safe(job, target)):
                targets.append(target)
            else:
                protected_paths.append(directory_path)
        if untracked_files:
            previous_untracked = job.get(
                "cleanup_skipped_untracked_segment_targets", [])
            previous_untracked = list(previous_untracked) \
                if isinstance(previous_untracked, list) else []
            job["cleanup_skipped_untracked_segment_targets"] = list(
                dict.fromkeys(previous_untracked + untracked_files))
            job["cleanup_skipped_untracked_segment_targets_at"] = (
                datetime.datetime.now().isoformat(timespec="seconds"))
    if skipped_replacements:
        previous_skipped = job.get("cleanup_skipped_replaced_targets", [])
        previous_skipped = list(previous_skipped) \
            if isinstance(previous_skipped, list) else []
        job["cleanup_skipped_replaced_targets"] = list(dict.fromkeys(
            previous_skipped + skipped_replacements))
        job["cleanup_skipped_replaced_targets_at"] = (
            datetime.datetime.now().isoformat(timespec="seconds"))
    return targets


def _cleanup_target_is_safe(job, target):
    session, _files, segment_dir = _uploaded_recording_cleanup_paths(job)
    if (not session or not isinstance(target, dict)
            or not _cleanup_session_identity_matches(job)):
        return False
    path = os.path.abspath(str(target.get("path", "") or ""))
    kind = str(target.get("kind", "") or "")
    if not _segment_cleanup_path_is_safe(session, path):
        return False
    try:
        if os.path.normcase(os.path.commonpath(
                [session, path])) != os.path.normcase(session):
            return False
    except ValueError:
        return False
    if kind == "directory":
        if not _segment_cleanup_path_is_safe(session, path):
            return False
        try:
            return os.path.normcase(os.path.commonpath(
                [segment_dir, path])) == os.path.normcase(segment_dir)
        except ValueError:
            return False
    if kind != "file":
        return False
    if (os.path.dirname(path) == session
            and os.path.basename(path) in {
                "recording.mp4", "recording.avi", "recording.wav",
                "recording_presentation_aligned.wav",
            }):
        return True
    try:
        return bool(
            os.path.normcase(os.path.commonpath(
                [segment_dir, path])) == os.path.normcase(segment_dir)
            and _segment_cleanup_path_is_safe(session, path))
    except ValueError:
        return False


def _cleanup_target_matches(job, target):
    if not _cleanup_target_is_safe(job, target):
        return False
    current = _cleanup_target_snapshot(
        target.get("path", ""), target.get("kind", ""))
    if current is None:
        return False
    return _cleanup_identity_matches(
        current, target, str(target.get("kind", "") or ""))


def _cleanup_identity_matches(current, expected, kind):
    """Compare a pinned object after it has been atomically renamed."""
    if not isinstance(current, dict) or not isinstance(expected, dict):
        return False
    keys = ("device", "inode") if kind == "directory" else (
        "device", "inode", "size", "mtime_ns")
    if kind == "file" and "ctime_ns" in expected:
        keys += ("ctime_ns",)
    try:
        return all(int(current.get(key, 0) or 0)
                   == int(expected.get(key, 0) or 0) for key in keys)
    except (TypeError, ValueError):
        return False


def _cleanup_tombstone_path(path):
    """Return a practically unique, same-directory deletion staging path."""
    directory = os.path.dirname(os.path.abspath(path))
    basename = os.path.basename(path)
    for _attempt in range(8):
        candidate = os.path.join(
            directory, ".{}.youtube-delete-{}.tombstone".format(
                basename, uuid.uuid4().hex))
        if not os.path.lexists(candidate):
            return candidate
    raise FileExistsError("YouTube cleanup tombstoneを作成できません: " + path)


def _record_cleanup_skipped_replacement(job, path):
    path = os.path.abspath(str(path or ""))
    skipped = job.get("cleanup_skipped_replaced_targets", [])
    skipped = list(skipped) if isinstance(skipped, list) else []
    job["cleanup_skipped_replaced_targets"] = list(dict.fromkeys(
        skipped + [path]))
    job["cleanup_skipped_replaced_targets_at"] = (
        datetime.datetime.now().isoformat(timespec="seconds"))


def _preserve_cleanup_quarantine(tombstone, original_path, kind="file"):
    """Best-effort restore without overwriting a concurrently-created path."""
    tombstone = os.path.abspath(tombstone)
    original_path = os.path.abspath(original_path)
    if (kind == "file" and os.path.lexists(tombstone)
            and not os.path.lexists(original_path)):
        try:
            # link() fails atomically when another object already owns the
            # original name.  Unlike rename(), it never replaces that object.
            os.link(tombstone, original_path, follow_symlinks=False)
        except (NotImplementedError, OSError):
            pass
        else:
            try:
                os.unlink(tombstone)
            except OSError:
                pass
    return [candidate for candidate in (original_path, tombstone)
            if os.path.lexists(candidate)]


def _record_cleanup_quarantine(job, original_path, preserved_paths, reason):
    original_path = os.path.abspath(str(original_path or ""))
    preserved_paths = [os.path.abspath(str(path)) for path in preserved_paths
                       if str(path or "")]
    entries = job.get("cleanup_quarantined_replacements", [])
    entries = list(entries) if isinstance(entries, list) else []
    signature = (original_path, tuple(preserved_paths), str(reason or ""))
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        existing = (
            str(entry.get("original_path", "") or ""),
            tuple(entry.get("preserved_paths", [])
                  if isinstance(entry.get("preserved_paths"), list) else []),
            str(entry.get("reason", "") or ""),
        )
        if existing == signature:
            return
    entries.append({
        "original_path": original_path,
        "preserved_paths": preserved_paths,
        "reason": str(reason or "identity_changed_after_atomic_move"),
        "detected_at": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    job["cleanup_quarantined_replacements"] = entries


def _append_cleanup_delete_tombstone(job, snapshot, original_path):
    if not isinstance(snapshot, dict):
        return
    entry = dict(snapshot)
    entry["cleanup_origin_path"] = os.path.abspath(str(original_path or ""))
    entries = job.get("cleanup_delete_tombstones", [])
    entries = list(entries) if isinstance(entries, list) else []
    path_key = os.path.normcase(os.path.abspath(str(entry.get("path", ""))))
    entries = [existing for existing in entries
               if not isinstance(existing, dict)
               or os.path.normcase(os.path.abspath(str(
                   existing.get("path", "") or ""))) != path_key]
    entries.append(entry)
    job["cleanup_delete_tombstones"] = entries


def _cleanup_delete_tombstone_is_safe(job, target):
    if not isinstance(target, dict):
        return False
    path = os.path.abspath(str(target.get("path", "") or ""))
    origin = os.path.abspath(str(
        target.get("cleanup_origin_path", "") or ""))
    if (not path or not origin
            or os.path.normcase(os.path.dirname(path))
            != os.path.normcase(os.path.dirname(origin))):
        return False
    prefix = ".{}.youtube-delete-".format(os.path.basename(origin))
    if (not os.path.basename(path).startswith(prefix)
            or not os.path.basename(path).endswith(".tombstone")):
        return False
    origin_target = dict(target)
    origin_target["path"] = origin
    origin_target.pop("cleanup_origin_path", None)
    return (_cleanup_target_is_safe(job, origin_target)
            and _segment_cleanup_path_is_safe(
                os.path.abspath(str(job.get("session_dir", "") or "")),
                path))


def _append_cleanup_tombstone_intent(job, source_path, tombstone_path,
                                     origin_path, target, kind):
    intent = {
        "id": uuid.uuid4().hex,
        "source_path": os.path.abspath(source_path),
        "tombstone_path": os.path.abspath(tombstone_path),
        "origin_path": os.path.abspath(origin_path),
        "kind": str(kind or "file"),
        "identity": dict(target),
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    intents = job.get("cleanup_tombstone_intents", [])
    intents = list(intents) if isinstance(intents, list) else []
    intents.append(intent)
    job["cleanup_tombstone_intents"] = intents
    return intent


def _remove_cleanup_tombstone_intent(job, intent_id):
    intents = job.get("cleanup_tombstone_intents", [])
    intents = list(intents) if isinstance(intents, list) else []
    job["cleanup_tombstone_intents"] = [
        intent for intent in intents
        if not isinstance(intent, dict)
        or str(intent.get("id", "") or "") != str(intent_id or "")]


def _recover_cleanup_tombstone_intents(job_path, job):
    """Adopt a staged object after a crash between rename and journal update."""
    intents = job.get("cleanup_tombstone_intents", [])
    if not isinstance(intents, list) or not intents:
        return
    job["cleanup_tombstone_intents"] = []
    for intent in intents:
        if not isinstance(intent, dict):
            continue
        source_path = os.path.abspath(str(
            intent.get("source_path", "") or ""))
        tombstone = os.path.abspath(str(
            intent.get("tombstone_path", "") or ""))
        origin_path = os.path.abspath(str(
            intent.get("origin_path", "") or source_path))
        kind = str(intent.get("kind", "file") or "file")
        expected = intent.get("identity")
        if not isinstance(expected, dict) or kind not in ("file", "directory"):
            if os.path.lexists(tombstone):
                _record_cleanup_quarantine(
                    job, origin_path, [tombstone],
                    "invalid_durable_tombstone_intent")
            continue
        tracked = dict(expected)
        tracked["path"] = tombstone
        tracked["kind"] = kind
        tracked["cleanup_origin_path"] = origin_path
        if not _cleanup_delete_tombstone_is_safe(job, tracked):
            if os.path.lexists(tombstone):
                _record_cleanup_quarantine(
                    job, origin_path, [tombstone],
                    "unsafe_durable_tombstone_intent")
            continue
        if not os.path.lexists(tombstone):
            # Rename never happened, or deletion completed before the final
            # checkpoint.  A first-stage source is covered by the ordinary
            # journal target.  A tracked tombstone retry is not, so re-adopt
            # that source before dropping its planned next-stage intent.
            source_target = dict(expected)
            source_target["path"] = source_path
            source_target["kind"] = kind
            source_target["cleanup_origin_path"] = origin_path
            source_snapshot = _cleanup_target_snapshot(source_path, kind)
            if (_cleanup_delete_tombstone_is_safe(job, source_target)
                    and _cleanup_identity_matches(
                        source_snapshot, expected, kind)):
                _append_cleanup_delete_tombstone(
                    job, source_snapshot, origin_path)
            continue
        moved = _cleanup_target_snapshot(tombstone, kind)
        if _cleanup_identity_matches(moved, expected, kind):
            _append_cleanup_delete_tombstone(job, moved, origin_path)
            continue
        preserved = _preserve_cleanup_quarantine(
            tombstone, source_path, kind)
        _record_cleanup_skipped_replacement(job, origin_path)
        _record_cleanup_quarantine(
            job, origin_path, preserved,
            "identity_changed_after_crash_recovery")
    _atomic_json(job_path, job)


def _atomic_delete_pinned_file(job_path, job, target, *, source_identity=False,
                               tracked_tombstone=False,
                               restore_on_failure=True):
    """Durably isolate, re-verify, then delete one pinned filesystem object.

    A path can be replaced after a successful identity check.  Renaming the
    current directory entry to a unique same-directory tombstone closes that
    check/delete window.  The planned tombstone is checkpointed before rename
    so a process crash cannot orphan an untracked large recording.
    """
    if not isinstance(target, dict):
        return "unsafe", None
    path = os.path.abspath(str(target.get("path", "") or ""))
    kind = str(target.get("kind", "file") or "file")
    if kind not in ("file", "directory"):
        return "unsafe", None
    if tracked_tombstone:
        safe = _cleanup_delete_tombstone_is_safe(job, target)
        matched = safe and _cleanup_identity_matches(
            _cleanup_target_snapshot(path, kind), target, kind)
        origin_path = os.path.abspath(str(
            target.get("cleanup_origin_path", "") or path))
    else:
        safe = _cleanup_target_is_safe(job, target)
        matched = safe and (
            _source_identity_matches(path, target)
            if source_identity and kind == "file"
            else _cleanup_target_matches(job, target))
        origin_path = path
    if not safe:
        return "unsafe", None
    if not matched:
        return "changed", None
    tombstone = _cleanup_tombstone_path(origin_path)
    intent = _append_cleanup_tombstone_intent(
        job, path, tombstone, origin_path, target, kind)
    _atomic_json(job_path, job)
    try:
        os.rename(path, tombstone)
    except FileNotFoundError:
        _remove_cleanup_tombstone_intent(job, intent["id"])
        _atomic_json(job_path, job)
        return "missing", None
    except OSError:
        # Keep the pre-rename intent durable.  In a tracked-tombstone retry
        # the caller has temporarily removed the old journal entry; clearing
        # this intent before the caller re-appends it would create a crash
        # window with a live but completely unreferenced large file.
        return "retry", None
    moved = _cleanup_target_snapshot(tombstone, kind)
    if not _cleanup_identity_matches(moved, target, kind):
        preserved = _preserve_cleanup_quarantine(tombstone, path, kind)
        _record_cleanup_skipped_replacement(job, origin_path)
        _record_cleanup_quarantine(
            job, origin_path, preserved,
            "identity_changed_after_atomic_move")
        _remove_cleanup_tombstone_intent(job, intent["id"])
        _atomic_json(job_path, job)
        return "quarantined", None
    try:
        if kind == "directory":
            os.rmdir(tombstone)
        else:
            os.remove(tombstone)
        _remove_cleanup_tombstone_intent(job, intent["id"])
        _atomic_json(job_path, job)
        return "deleted", None
    except OSError:
        preserved = [tombstone]
        if restore_on_failure and kind == "file":
            preserved = _preserve_cleanup_quarantine(
                tombstone, path, kind)
        if os.path.lexists(tombstone):
            retry_snapshot = _cleanup_target_snapshot(tombstone, kind)
            if retry_snapshot is not None:
                retry_snapshot["cleanup_origin_path"] = origin_path
                _append_cleanup_delete_tombstone(
                    job, retry_snapshot, origin_path)
                _remove_cleanup_tombstone_intent(job, intent["id"])
                _atomic_json(job_path, job)
                return "retry", retry_snapshot
        # The original hard-link was restored, so the ordinary cleanup target
        # remains durable and can be retried without a hidden local remnant.
        _remove_cleanup_tombstone_intent(job, intent["id"])
        _atomic_json(job_path, job)
        if any(os.path.lexists(candidate) for candidate in preserved):
            return "retry", None
        return "missing", None


def _uploaded_recording_remnants(job):
    targets = job.get("cleanup_targets", [])
    if not isinstance(targets, list):
        return ["cleanup_targets"]
    remaining = []
    for target in targets:
        path = os.path.abspath(str(dict(target or {}).get(
            "path", "") or ""))
        if not path or not os.path.lexists(path):
            continue
        if not _cleanup_target_is_safe(job, target):
            remaining.append("unsafe:" + path)
        elif not _cleanup_target_matches(job, target):
            remaining.append("identity_changed:" + path)
        else:
            remaining.append(path)
    for target in job.get("cleanup_delete_tombstones", []):
        if not isinstance(target, dict):
            continue
        path = os.path.abspath(str(target.get("path", "") or ""))
        if path and os.path.lexists(path):
            remaining.append("cleanup_tombstone:" + path)
    for entry in job.get("cleanup_quarantined_replacements", []):
        if not isinstance(entry, dict):
            continue
        preserved = entry.get("preserved_paths", [])
        if not isinstance(preserved, list):
            continue
        for path in preserved:
            path = os.path.abspath(str(path or ""))
            if path and os.path.lexists(path):
                remaining.append("quarantined_replacement:" + path)
    return remaining


def _temporary_cleanup_remnants(job):
    """Return live staged-part remnants even when full cleanup is disabled."""
    remaining = []
    for target in job.get("cleanup_delete_tombstones", []):
        if not isinstance(target, dict):
            continue
        path = os.path.abspath(str(target.get("path", "") or ""))
        if path and os.path.lexists(path):
            remaining.append("cleanup_tombstone:" + path)
    for entry in job.get("cleanup_quarantined_replacements", []):
        if not isinstance(entry, dict):
            continue
        preserved = entry.get("preserved_paths", [])
        if not isinstance(preserved, list):
            continue
        for path in preserved:
            path = os.path.abspath(str(path or ""))
            if path and os.path.lexists(path):
                remaining.append("quarantined_replacement:" + path)
    media_path = os.path.abspath(str(job.get("media_path", "") or ""))
    for segment in job.get("segments", []):
        if (not isinstance(segment, dict)
                or not str(segment.get("video_id", "") or "").strip()):
            continue
        part_path = os.path.abspath(str(
            segment.get("local_path", "") or ""))
        expected = segment.get("source_identity")
        if (not part_path or part_path == media_path
                or not isinstance(expected, dict)
                or not _cleanup_target_is_safe(job, expected)):
            continue
        if (os.path.lexists(part_path)
                and _source_identity_matches(part_path, expected)):
            remaining.append("uploaded_part:" + part_path)
    return list(dict.fromkeys(remaining))


def _retry_cleanup_delete_tombstones(job_path, job):
    """Retry verified upload-object tombstones without touching replacements."""
    targets = job.get("cleanup_delete_tombstones", [])
    targets = list(targets) if isinstance(targets, list) else []
    job["cleanup_delete_tombstones"] = []
    for target in targets:
        if not isinstance(target, dict):
            continue
        path = os.path.abspath(str(target.get("path", "") or ""))
        if not path or not os.path.lexists(path):
            continue
        status, retry_target = _atomic_delete_pinned_file(
            job_path, job, target, tracked_tombstone=True,
            restore_on_failure=False)
        if retry_target is not None:
            _append_cleanup_delete_tombstone(
                job, retry_target,
                target.get("cleanup_origin_path", path))
        elif status == "retry" and os.path.lexists(path):
            # rename() itself can fail (notably Windows sharing violations).
            # Keep the already-journaled tombstone actionable rather than
            # clearing its only durable reference.
            _append_cleanup_delete_tombstone(
                job, target, target.get("cleanup_origin_path", path))
        elif status in ("unsafe", "changed") and os.path.lexists(path):
            origin = os.path.abspath(str(
                target.get("cleanup_origin_path", "") or path))
            _record_cleanup_skipped_replacement(job, origin)
            _record_cleanup_quarantine(
                job, origin, [path],
                "tracked_tombstone_identity_changed")
    if targets:
        _atomic_json(job_path, job)


def _checkpoint_temporary_cleanup_wait(path, job, pending_status):
    """Consume one bounded cleanup attempt without losing remote state."""
    remaining = _temporary_cleanup_remnants(job)
    if not remaining:
        return ""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    job["cleanup_attempts"] = int(job.get("cleanup_attempts", 0) or 0) + 1
    job["cleanup_remaining"] = remaining
    job["updated_at"] = now
    quarantined = [item for item in remaining
                   if item.startswith("quarantined_replacement:")]
    if quarantined:
        job["status"] = CLEANUP_ATTENTION_REQUIRED
        job["cleanup_attention_required_at"] = now
        message = (
            "YouTube用一時partの削除直前にファイルが差し替えられました。"
            "差替え後のファイルは保全したため手動確認が必要です。")
    elif int(job.get("cleanup_attempts", 0) or 0) >= MAX_CLEANUP_ATTEMPTS:
        job["status"] = CLEANUP_ATTENTION_REQUIRED
        job["cleanup_attention_required_at"] = now
        message = (
            "YouTube用一時partを{}回削除できませんでした。"
            "ファイル使用中または権限を確認してください。".format(
                MAX_CLEANUP_ATTEMPTS))
    else:
        job["status"] = str(pending_status or "cleanup_pending")
        message = "YouTube用一時partの削除完了待ちです。"
    job["cleanup_error"] = message
    job["error"] = message
    _atomic_json(path, job)
    return str(job["status"])


def _finish_temporary_part_cleanup(path, job):
    """Bound retries for split-part tombstones without deleting source media."""
    media_path = os.path.abspath(str(job.get("media_path", "") or ""))
    for segment in job.get("segments", []):
        if (isinstance(segment, dict)
                and str(segment.get("video_id", "") or "").strip()):
            _cleanup_uploaded_segment_part(path, job, segment, media_path)
    status = _checkpoint_temporary_cleanup_wait(
        path, job, "cleanup_pending")
    if status:
        return status
    return _mark_upload_completed(path, job)


def _cleanup_uploaded_segment_part(job_path, job, segment, media_path):
    """Retry safe deletion of one remotely-created split part."""
    if not isinstance(segment, dict):
        return
    segment_path = os.path.abspath(str(
        segment.get("local_path", "") or ""))
    media_path = os.path.abspath(str(media_path or ""))
    source_identity = segment.get("source_identity")
    if (not segment_path or segment_path == media_path
            or not isinstance(source_identity, dict)
            or not source_identity or not os.path.lexists(segment_path)):
        return
    status, retry_target = _atomic_delete_pinned_file(
        job_path, job, source_identity, source_identity=True,
        restore_on_failure=False)
    if retry_target is not None:
        _append_cleanup_delete_tombstone(
            job, retry_target, segment_path)
    elif status in ("unsafe", "changed") and os.path.lexists(segment_path):
        _record_cleanup_skipped_replacement(job, segment_path)


def _cleanup_uploaded_recording(job_path, job):
    """Delete only objects captured in the durable cleanup journal."""
    targets = job.get("cleanup_targets", [])
    if not isinstance(targets, list):
        return ["cleanup_targets"]
    _retry_cleanup_delete_tombstones(job_path, job)
    if ((job.get("cleanup_delete_tombstones")
         or job.get("cleanup_quarantined_replacements"))
            and _uploaded_recording_remnants(job)):
        return _uploaded_recording_remnants(job)
    files = [target for target in targets
             if isinstance(target, dict) and target.get("kind") == "file"]
    directories = sorted(
        (target for target in targets
         if isinstance(target, dict) and target.get("kind") == "directory"),
        key=lambda target: str(target.get("path", "")).count(os.sep),
        reverse=True)
    for target in files:
        path = os.path.abspath(str(target.get("path", "") or ""))
        status, retry_target = _atomic_delete_pinned_file(
            job_path, job, target)
        if retry_target is not None:
            _append_cleanup_delete_tombstone(job, retry_target, path)
        elif status in ("unsafe", "changed") and os.path.lexists(path):
            _record_cleanup_skipped_replacement(job, path)
    if (job.get("cleanup_delete_tombstones")
            or job.get("cleanup_quarantined_replacements")):
        return _uploaded_recording_remnants(job)
    for target in directories:
        path = os.path.abspath(str(target.get("path", "") or ""))
        status, retry_target = _atomic_delete_pinned_file(
            job_path, job, target, restore_on_failure=False)
        if retry_target is not None:
            _append_cleanup_delete_tombstone(job, retry_target, path)
        elif status in ("unsafe", "changed") and os.path.lexists(path):
            _record_cleanup_skipped_replacement(job, path)
    return _uploaded_recording_remnants(job)


def _skip_permanently_changed_cleanup_targets(job):
    """Stop retrying identities that now name a different local object."""
    targets = job.get("cleanup_targets", [])
    if not isinstance(targets, list):
        return
    retained = []
    skipped = []
    for target in targets:
        if not isinstance(target, dict):
            continue
        path = os.path.abspath(str(target.get("path", "") or ""))
        if not path or not os.path.lexists(path):
            continue
        if not _cleanup_target_is_safe(job, target):
            skipped.append(path)
            continue
        try:
            os.stat(path, follow_symlinks=False)
        except OSError:
            retained.append(target)
            continue
        current = _cleanup_target_snapshot(path, target.get("kind", ""))
        if current is None:
            # The path is accessible but its object type no longer matches the
            # journal (for example, a directory replaced the recording file).
            skipped.append(path)
            continue
        if not _cleanup_target_matches(job, target):
            skipped.append(path)
            continue
        retained.append(target)
    if skipped:
        previous = job.get("cleanup_skipped_replaced_targets", [])
        previous = list(previous) if isinstance(previous, list) else []
        job["cleanup_skipped_replaced_targets"] = list(dict.fromkeys(
            previous + skipped))
        job["cleanup_skipped_replaced_targets_at"] = (
            datetime.datetime.now().isoformat(timespec="seconds"))
    job["cleanup_targets"] = retained


def _mark_upload_completed(path, job):
    job.pop("cleanup_remaining", None)
    job.pop("cleanup_error", None)
    job.pop("error", None)
    job["status"] = "completed"
    job["completed_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    job["updated_at"] = job["completed_at"]
    _atomic_json(path, job)
    return "completed"


def _request_missing_media_finalization(job):
    """Hand an arbitrary session's recoverable MP4 job to the load guard."""
    session = os.path.abspath(str(job.get("session_dir", "") or ""))
    if not session or not os.path.isdir(session):
        return False
    manifest = os.path.join(session, "mp4_finalize_job.json")
    if not os.path.isfile(manifest):
        return False
    try:
        from ProcessShutdown import launch_recording_finalize_worker
        from Recording import discover_finalize_manifests
        recoverable = discover_finalize_manifests(os.path.dirname(session))
        if os.path.abspath(manifest) not in recoverable:
            return False
        launch_recording_finalize_worker([manifest])
        return True
    except (ImportError, OSError, ValueError):
        return False


def _finish_uploaded_recording_cleanup(path, job):
    """Persist cleanup intent before deletion and complete it idempotently."""
    current_status = str(job.get("status", "") or "")
    if not _cleanup_session_identity_matches(job):
        # Missing identity means a pre-hardening job; a mismatch means the
        # timestamp folder was removed/replaced after enqueue.  Neither is
        # sufficient authority to delete current filesystem objects.  Finish
        # the remote job while preserving an explicit audit marker and every
        # local file at the unverified path.
        now = datetime.datetime.now().isoformat(timespec="seconds")
        job["cleanup_skipped_session_identity_at"] = now
        job["cleanup_skip_reason"] = "session_identity_unverified"
        return _mark_upload_completed(path, job)
    if "cleanup_targets" not in job:
        if current_status == "cleanup_pending":
            # Old versions reconstructed targets from file names.  Doing that
            # after a restart could delete a newly restored recording, so a
            # legacy unjournaled cleanup is completed without deleting files.
            job["cleanup_skipped_unjournaled_at"] = (
                datetime.datetime.now().isoformat(timespec="seconds"))
            return _mark_upload_completed(path, job)
        job["cleanup_targets"] = _snapshot_uploaded_recording_cleanup_targets(job)
        job["cleanup_journaled_at"] = (
            datetime.datetime.now().isoformat(timespec="seconds"))
    _recover_cleanup_tombstone_intents(path, job)
    _skip_permanently_changed_cleanup_targets(job)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    job["status"] = "cleanup_pending"
    job["updated_at"] = now
    job.setdefault("processing_completed_at", now)
    _atomic_json(path, job)
    remaining = _cleanup_uploaded_recording(path, job)
    job["cleanup_attempts"] = int(job.get("cleanup_attempts", 0) or 0) + 1
    job["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    if remaining:
        job["cleanup_remaining"] = remaining
        quarantined = [item for item in remaining
                       if item.startswith("quarantined_replacement:")]
        if quarantined:
            job["status"] = CLEANUP_ATTENTION_REQUIRED
            job["cleanup_attention_required_at"] = job["updated_at"]
            message = (
                "削除直前にローカルファイルが差し替えられました。"
                "差替え後のファイルは保全したため手動確認が必要です。")
            job["cleanup_error"] = message
            job["error"] = message
            _atomic_json(path, job)
            return CLEANUP_ATTENTION_REQUIRED
        if int(job.get("cleanup_attempts", 0) or 0) >= \
                MAX_CLEANUP_ATTEMPTS:
            job["status"] = CLEANUP_ATTENTION_REQUIRED
            job["cleanup_attention_required_at"] = job["updated_at"]
            message = (
                "ローカル動画・音声を{}回削除できませんでした。"
                "ファイル使用中または権限を確認してください。".format(
                    MAX_CLEANUP_ATTEMPTS))
            job["cleanup_error"] = message
            job["error"] = message
            _atomic_json(path, job)
            return CLEANUP_ATTENTION_REQUIRED
        message = "ローカル動画・音声の削除完了待ちです。"
        job["cleanup_error"] = message
        job["error"] = message
        _atomic_json(path, job)
        return "cleanup_pending"
    return _mark_upload_completed(path, job)


def _mark_remote_upload_blocked(path, job, status, message,
                                profile_name, profile):
    """Persist a non-retriable remote state without losing local or IDs."""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    job["status"] = status
    job["error"] = str(message or "")
    job[status + "_at"] = now
    job["updated_at"] = now
    # Commit the non-actionable state before best-effort index mirroring.  A
    # permissions error in youtube_remote.json must never regress this job to
    # an upload/retry state and risk a duplicate remote video.
    _atomic_json(path, job)
    try:
        _write_remote(job, profile_name, profile)
    except Exception as error:
        # _write_remote is itself best-effort, but retain this boundary so a
        # future/custom index writer can never undo the terminal checkpoint.
        job["remote_index_error"] = str(error)
        job["remote_index_error_at"] = (
            datetime.datetime.now().isoformat(timespec="seconds"))
    _atomic_json(path, job)
    return status


def _mark_source_upload_blocked(path, job, message):
    """Stop automatic PUTs while retaining every remote and local reference."""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    job["status"] = SOURCE_VERIFICATION_REQUIRED
    job["error"] = str(message or "")
    job["source_verification_required_at"] = now
    job["updated_at"] = now
    _atomic_json(path, job)
    return SOURCE_VERIFICATION_REQUIRED


def process_upload_job(path, store_path):
    path = os.path.abspath(path)
    with _upload_job_state_lock(path):
        if _is_link_or_reparse_point(path):
            return _quarantine_invalid_upload_job(
                path, "YouTube upload jobがlink/reparse pointです。")
        job = _read_json(path, None)
        if not isinstance(job, dict):
            return _quarantine_invalid_upload_job(
                path, "YouTube upload jobのJSONを読み込めません。")
        schema_error = _upload_job_schema_error(job)
        if schema_error:
            return _quarantine_invalid_upload_job(
                path, "YouTube upload jobを隔離しました: " + schema_error)
        name = os.path.basename(path)
        expected_id = name[:-len(".json")] \
            if name.lower().endswith(".json") else ""
        identity_error = _upload_job_identity_error(job, expected_id)
        if identity_error:
            # The filename is part of the durable intent.  A schema-valid JSON
            # copied or atomically swapped under another name must not upload
            # (or later delete) the recording referenced by its payload.
            return _quarantine_invalid_upload_job(
                path, "YouTube upload jobを隔離しました: " + identity_error)
        current_status = str(job.get("status", "pending") or "pending")
        if (current_status == "completed"
                and not completed_upload_has_remote_proof(job)):
            # A terminal label alone is not durable evidence that YouTube owns
            # the video. Refuse all tombstone recovery/local cleanup until the
            # missing remote IDs are inspected or repaired manually.
            now = datetime.datetime.now().isoformat(timespec="seconds")
            job["status"] = UPLOAD_ATTENTION_REQUIRED
            job["error"] = (
                "completed jobに永続化済みYouTube video_idがありません。"
                "ローカル録画を保持して手動確認します。")
            job["upload_attention_required_at"] = now
            job["updated_at"] = now
            _atomic_json(path, job)
            return UPLOAD_ATTENTION_REQUIRED
        _equivalent, identity_conflict = _equivalent_upload_job_base(
            os.path.dirname(path), job.get("media_path", ""),
            job.get("session_dir", ""))
        if identity_conflict:
            # Old and new PokeCon processes can overlap during an upgrade.
            # Even though each v1/v2 payload is internally valid, two queue
            # filenames for the same case-insensitive Windows paths represent
            # an ambiguous duplicate remote intent.  Stop before profile/API
            # access or local cleanup and preserve all jobs for inspection.
            if current_status in ("completed", "cancelled", INVALID_JOB):
                return current_status
            now = datetime.datetime.now().isoformat(timespec="seconds")
            job["status"] = UPLOAD_ATTENTION_REQUIRED
            job["error"] = (
                "同じ録画を参照する複数のYouTube queue jobを検出しました。"
                "重複アップロードを防ぐため手動確認が必要です。")
            job["upload_attention_required_at"] = now
            job["updated_at"] = now
            _atomic_json(path, job)
            return UPLOAD_ATTENTION_REQUIRED
        # A crash after atomic rename but before unlink/final checkpoint must
        # not strand a hidden, untracked recording.  Recover and retry the
        # durable tombstone before honoring even a terminal job status.
        _recover_cleanup_tombstone_intents(path, job)
        _retry_cleanup_delete_tombstones(path, job)
        current_status = str(job.get("status", "pending") or "pending")
        if current_status == QUOTA_WAITING:
            if not upload_job_is_actionable(job):
                return QUOTA_WAITING
            # The daily window elapsed. Preserve the previous error/audit
            # fields, but let this job make exactly one new remote attempt.
            _archive_active_upload_error(job)
            current_status = "pending"
            job["status"] = current_status
            job["attempts"] = 0
            job["quota_resumed_at"] = datetime.datetime.now().isoformat(
                timespec="seconds")
            job.pop("quota_retry_after", None)
            job.pop("quota_retry_after_epoch", None)
            _atomic_json(path, job)
        if current_status == "completed":
            return "completed"
        if current_status == "cancelled":
            return "cancelled"
        if current_status in (
                REMOTE_VERIFICATION_REQUIRED, REMOTE_PROCESSING_FAILED,
                CLEANUP_ATTENTION_REQUIRED, UPLOAD_ATTENTION_REQUIRED,
                SOURCE_VERIFICATION_REQUIRED, INVALID_JOB):
            return current_status
        if current_status == "cleanup_pending":
            if not job.get("delete_local_after_processing"):
                return _finish_temporary_part_cleanup(path, job)
            return _finish_uploaded_recording_cleanup(path, job)
        media_path = os.path.abspath(str(job.get("media_path", "") or ""))
        try:
            media_available = (os.path.isfile(media_path)
                               and os.path.getsize(media_path) > 1024)
        except OSError:
            media_available = False
        has_persisted_video = any(
            str(segment.get("video_id", "") or "").strip()
            for segment in job.get("segments", [])
            if isinstance(segment, dict))
        has_remote_state = _job_has_remote_upload_state(job)
        needs_local_upload = (not job.get("segments") or any(
            not str(segment.get("video_id", "") or "").strip()
            for segment in job.get("segments", [])
            if isinstance(segment, dict)))
        if not media_available and not has_persisted_video:
            # The queue is global to the settings directory, whereas an
            # InputSet may later select a different recording root.  Recover
            # the durable manifest next to this job's media instead of relying
            # on the currently selected root to rediscover it.
            _request_missing_media_finalization(job)
            _archive_active_upload_error(job)
            now = datetime.datetime.now().isoformat(timespec="seconds")
            job["status"] = "waiting_media"
            job.setdefault("media_missing_since", now)
            job["updated_at"] = now
            # ``error`` describes the previous attempt (for example HTTP
            # 400/429), not this local-media wait. Keeping it would make the
            # queue dialog misidentify both the active cause and its time.
            _atomic_json(path, job)
            return "waiting_media"
        if media_available:
            job.pop("media_missing_since", None)
        if media_available and not has_remote_state:
            # Never turn a replacement timestamp directory into the original
            # upload intent, even before the first remote request.  Only a
            # legacy job with no identity may pin its current real directory.
            if "session_identity" in job:
                if not _cleanup_session_identity_matches(job):
                    return _mark_source_upload_blocked(
                        path, job,
                        "録画session directoryがqueue登録後に差し替えられました。"
                        "別録画の送信・削除を防ぐため手動確認が必要です: "
                        + str(job.get("session_dir", "") or ""))
            else:
                session_identity = _session_directory_identity_snapshot(
                    job.get("session_dir", ""))
                if session_identity is None:
                    return _mark_source_upload_blocked(
                        path, job,
                        "録画session directoryの安全な同一性を確認できません: "
                        + str(job.get("session_dir", "") or ""))
                job["session_identity"] = session_identity
            expected_media = _recording_media_source_identity(job)
            if expected_media is not None:
                # A finalized MP4 (for example a Commands chunk) was already
                # pinned at enqueue; never legitimize a later replacement by
                # refreshing its identity.
                if not _source_identity_matches(media_path, expected_media):
                    return _mark_source_upload_blocked(
                        path, job,
                        "queue登録済み録画ファイルがupload開始前に"
                        "差し替えられました。手動確認が必要です: "
                        + media_path)
            else:
                # Session-start jobs are queued before recording.mp4 exists.
                # Pin the finalized MP4 exactly once before remote activity.
                job["recording_cleanup_targets"] = (
                    _snapshot_recording_cleanup_targets(job))
                expected_media = _recording_media_source_identity(job)
                if (expected_media is None
                        or not _source_identity_matches(
                            media_path, expected_media)):
                    return _mark_source_upload_blocked(
                        path, job,
                        "finalized recording.mp4の同一性を記録できません: "
                        + media_path)
        elif media_available and has_remote_state and needs_local_upload:
            expected_media = _recording_media_source_identity(job)
            if (expected_media is None
                    or not _source_identity_matches(
                        media_path, expected_media)):
                return _mark_source_upload_blocked(
                    path, job,
                    "部分アップロード開始後に録画元ファイルの同一性を"
                    "確認できません。重複・混在を防ぐため手動確認が必要です: "
                    + media_path)
        if current_status in ("pending", "waiting_media"):
            _archive_active_upload_error(job)
            job["status"] = "uploading"
            job["updated_at"] = datetime.datetime.now().isoformat(
                timespec="seconds")
            _atomic_json(path, job)
    profile_name, profile = _resolve_profile(
        store_path, job.get("channel_profile_resolved", "")
        or job.get("channel_profile", ""))
    try:
        if _pin_job_channel_identity(job, profile_name, profile):
            job["updated_at"] = (
                datetime.datetime.now().isoformat(timespec="seconds"))
            _atomic_json(path, job)
        token = _access_token(profile)
    except YouTubeAuthenticationRequired as error:
        wrapped = YouTubeAuthenticationRequired(
            str(error), profile_name=profile_name,
            oauth_error=error.oauth_error)
        _mark_job_authentication_required(
            path, job, wrapped, profile_name=profile_name)
        raise wrapped from error
    duration = float(job.get("duration_seconds", 0.0) or 0.0)
    existing_segments = [segment for segment in job.get("segments", [])
                         if isinstance(segment, dict)]
    if existing_segments:
        total = max(1, len(existing_segments))
        if duration <= 0.0:
            duration = max((
                float(segment.get("start_seconds", 0.0) or 0.0)
                + float(segment.get("duration_seconds", 0.0) or 0.0)
                for segment in existing_segments), default=0.0)
    else:
        if duration <= 0.0:
            duration = _probe_duration(media_path)
            if duration <= 0.0:
                raise RuntimeError("録画時間を確認できません: " + media_path)
            job["duration_seconds"] = duration
        segment_seconds = float(job.get(
            "segment_seconds", DEFAULT_SEGMENT_SECONDS)
            or DEFAULT_SEGMENT_SECONDS)
        total = max(1, int(math.ceil(duration / segment_seconds)))
        job["segments"] = [{
            "part": part + 1,
            "start_seconds": round(part * segment_seconds, 6),
            "duration_seconds": round(min(segment_seconds, duration - part * segment_seconds), 6),
            "status": "pending",
        } for part in range(total)]
    _archive_active_upload_error(job)
    job["status"] = "uploading"
    job["channel_profile_resolved"] = profile_name
    _atomic_json(path, job)
    pending_processing = False
    for segment in job["segments"]:
        if segment.get("video_id"):
            status = _processing_status(token, segment["video_id"])
            segment["processing_status"] = status
            if status == "failed":
                return _mark_remote_upload_blocked(
                    path, job, REMOTE_PROCESSING_FAILED,
                    "YouTube側で動画処理に失敗しました: "
                    + segment["video_id"], profile_name, profile)
            if status == "terminated":
                return _mark_remote_upload_blocked(
                    path, job, REMOTE_VERIFICATION_REQUIRED,
                    "YouTube側の処理情報を取得できなくなりました。"
                    "既存動画を手動確認してください: "
                    + segment["video_id"], profile_name, profile)
            if status == "missing":
                missing_checks = int(segment.get("missing_checks", 0) or 0) + 1
                segment["missing_checks"] = missing_checks
                segment["last_missing_at"] = (
                    datetime.datetime.now().isoformat(timespec="seconds"))
                # A persisted video ID proves that a remote upload completed.
                # YouTube search/list visibility can lag or transiently return
                # no item; clearing the ID here would create a duplicate video.
                _atomic_json(path, job)
                if missing_checks >= 20:
                    return _mark_remote_upload_blocked(
                        path, job, REMOTE_VERIFICATION_REQUIRED,
                        "YouTube動画IDを20回確認できませんでした。"
                        "重複アップロードを防ぐため既存IDを保持して"
                        "手動確認を待ちます: " + segment["video_id"],
                        profile_name, profile)
                pending_processing = True
            elif status != "processed":
                pending_processing = True
            _cleanup_uploaded_segment_part(
                path, job, segment, media_path)
            continue
        if not media_available:
            # Existing remote videos were still polled above.  Any remaining
            # segment cannot be uploaded until its local source is restored.
            _archive_active_upload_error(job)
            now = datetime.datetime.now().isoformat(timespec="seconds")
            job["status"] = "waiting_media"
            job.setdefault("media_missing_since", now)
            job["updated_at"] = now
            _write_remote(job, profile_name, profile)
            _atomic_json(path, job)
            return "waiting_media"
        expected_media = _recording_media_source_identity(job)
        if (expected_media is None
                or not _source_identity_matches(media_path, expected_media)):
            return _mark_source_upload_blocked(
                path, job,
                "YouTube upload中に録画元ファイルが変更されました。"
                "未送信partへの混在を防ぐため手動確認が必要です: "
                + media_path)
        segment_path = os.path.abspath(
            _materialize_segment(job, segment, total))
        if not _source_identity_matches(media_path, expected_media):
            return _mark_source_upload_blocked(
                path, job,
                "YouTube用partの作成中に録画元ファイルが変更されました。"
                "内容混在を防ぐため手動確認が必要です: " + media_path)
        segment["local_path"] = segment_path
        segment_remote_state = bool(
            str(segment.get("upload_url", "") or "").strip()
            or int(segment.get("uploaded_bytes", 0) or 0) > 0
            or str(segment.get("status", "") or "") == "uploaded")
        source_identity = segment.get("source_identity")
        if not segment_remote_state:
            # No remote bytes exist, so it is safe to refresh a local part
            # that may have been rematerialized after a previous local error.
            source_identity = _source_identity_snapshot(job, segment_path)
            if source_identity is None:
                return _mark_source_upload_blocked(
                    path, job,
                    "YouTube upload元partの安全な同一性を記録できません: "
                    + segment_path)
            segment["source_identity"] = source_identity
            _atomic_json(path, job)
        elif not isinstance(source_identity, dict) or not source_identity:
            # A one-part legacy job can safely adopt the media identity that
            # was pinned before its first remote effect.  Split parts had no
            # equivalent durable pre-upload snapshot, so fail closed.
            if (os.path.normcase(segment_path) == os.path.normcase(media_path)
                    and _source_identity_matches(
                        segment_path, expected_media)):
                source_identity = dict(expected_media)
                source_identity["realpath"] = os.path.normcase(
                    os.path.realpath(segment_path))
                segment["source_identity"] = source_identity
                _atomic_json(path, job)
            else:
                return _mark_source_upload_blocked(
                    path, job,
                    "部分アップロード済みpartの開始時同一性がありません。"
                    "重複・混在を防ぐため手動確認が必要です: "
                    + segment_path)
        if not _source_identity_matches(segment_path, source_identity):
            return _mark_source_upload_blocked(
                path, job,
                "部分アップロード中の元partが差し替えられました。"
                "同じresumable sessionへの送信を停止しました: "
                + segment_path)

        def progress(offset, size):
            segment["uploaded_bytes"] = int(offset)
            segment["total_bytes"] = int(size)
            job["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
            _atomic_json(path, job)

        def before_put(offset, size):
            if str(segment.get("put_attempted_at", "") or "").strip():
                return
            now = datetime.datetime.now().isoformat(timespec="seconds")
            segment["put_attempted_at"] = now
            segment["put_attempted_offset"] = int(offset)
            segment["total_bytes"] = int(size)
            job["updated_at"] = now
            _atomic_json(path, job)

        def initiate_tracked_session():
            # The daily pause protects only videos.insert. Existing upload
            # sessions, remote processing checks, and local cleanup remain
            # safe and must continue so disk space can still be reclaimed.
            if _active_quota_pause(os.path.dirname(path)):
                return ""
            try:
                upload_url = _initiate_resumable_upload(
                    token, segment_path,
                    _safe_title(job, int(segment["part"]), total),
                    build_video_description(
                        job, segment["start_seconds"],
                        segment["duration_seconds"]),
                    str(job.get(
                        "privacy_status", "unlisted") or "unlisted"))
            except Exception as error:
                if _is_youtube_quota_error(error):
                    raise YouTubeVideoInsertQuotaExceeded(str(error)) \
                        from error
                raise
            segment["upload_url"] = upload_url
            segment["upload_session_tracking_version"] = (
                RESUMABLE_PUT_TRACKING_VERSION)
            segment["upload_session_created_at"] = (
                datetime.datetime.now().isoformat(timespec="seconds"))
            segment.pop("put_attempted_at", None)
            segment.pop("put_attempted_offset", None)
            segment.pop("uploaded_bytes", None)
            segment.pop("total_bytes", None)
            _atomic_json(path, job)
            return upload_url

        try:
            if not segment.get("upload_url"):
                _require_source_identity(segment_path, source_identity)
                if not initiate_tracked_session():
                    _atomic_json(path, job)
                    return UPLOAD_INSERT_PAUSED
            segment["video_id"] = _upload_resumable(
                segment_path, token, segment["upload_url"],
                progress=progress, expected_identity=source_identity,
                before_put=before_put)
        except UploadSessionExpired:
            if _expired_session_may_have_completed_put(segment):
                return _mark_remote_upload_blocked(
                    path, job, REMOTE_VERIFICATION_REQUIRED,
                    "YouTube resumable sessionが期限切れですが、既にPUTが"
                    "成功して動画が作成された可能性があります。重複uploadを"
                    "防ぐため旧sessionを保持して手動確認を待ちます: "
                    + str(segment.get("upload_url", "") or ""),
                    profile_name, profile)
            try:
                _require_source_identity(segment_path, source_identity)
                expired_url = str(segment.get("upload_url", "") or "")
                expired_urls = segment.get("expired_upload_urls", [])
                expired_urls = list(expired_urls) \
                    if isinstance(expired_urls, list) else []
                if expired_url:
                    segment["expired_upload_urls"] = list(dict.fromkeys(
                        expired_urls + [expired_url]))
                if not initiate_tracked_session():
                    _atomic_json(path, job)
                    return UPLOAD_INSERT_PAUSED
                segment["video_id"] = _upload_resumable(
                    segment_path, token, segment["upload_url"],
                    progress=progress, expected_identity=source_identity,
                    before_put=before_put)
            except UploadSessionExpired:
                return _mark_remote_upload_blocked(
                    path, job, REMOTE_VERIFICATION_REQUIRED,
                    "再作成したYouTube resumable sessionも期限切れになり"
                    "ました。重複uploadを防ぐため手動確認が必要です: "
                    + str(segment.get("upload_url", "") or ""),
                    profile_name, profile)
            except UploadSourceChanged as error:
                return _mark_source_upload_blocked(path, job, str(error))
        except UploadSourceChanged as error:
            return _mark_source_upload_blocked(path, job, str(error))
        segment["status"] = "uploaded"
        job["updated_at"] = datetime.datetime.now().isoformat(
            timespec="seconds")
        # The upload has already created a remote YouTube video at this point.
        # Checkpoint its ID before any processing-status request so a transient
        # API failure/restart resumes by polling that video instead of creating
        # a duplicate upload.
        _atomic_json(path, job)
        segment["processing_status"] = _processing_status(token, segment["video_id"])
        if segment["processing_status"] == "failed":
            return _mark_remote_upload_blocked(
                path, job, REMOTE_PROCESSING_FAILED,
                "YouTube側で動画処理に失敗しました: "
                + segment["video_id"], profile_name, profile)
        if segment["processing_status"] == "terminated":
            return _mark_remote_upload_blocked(
                path, job, REMOTE_VERIFICATION_REQUIRED,
                "YouTube側の処理情報を取得できなくなりました。"
                "既存動画を手動確認してください: "
                + segment["video_id"], profile_name, profile)
        if segment["processing_status"] == "missing":
            segment["missing_checks"] = 1
        pending_processing = pending_processing or segment["processing_status"] != "processed"
        _cleanup_uploaded_segment_part(path, job, segment, media_path)
        _write_remote(job, profile_name, profile)
        _atomic_json(path, job)
    if pending_processing:
        job["status"] = "awaiting_processing"
        job["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        cleanup_status = _checkpoint_temporary_cleanup_wait(
            path, job, "awaiting_processing")
        _write_remote(job, profile_name, profile)
        _atomic_json(path, job)
        return cleanup_status or "awaiting_processing"
    _write_remote(job, profile_name, profile)
    if job.get("delete_local_after_processing"):
        return _finish_uploaded_recording_cleanup(path, job)
    if _temporary_cleanup_remnants(job):
        return _finish_temporary_part_cleanup(path, job)
    job.pop("error", None)
    job["status"] = "completed"
    job["completed_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    job["updated_at"] = job["completed_at"]
    _atomic_json(path, job)
    return "completed"


@contextlib.contextmanager
def _queue_lock(queue_dir):
    os.makedirs(queue_dir, exist_ok=True)
    path = os.path.join(queue_dir, "worker.lock")
    stream = open(path, "a+b")
    locked = False
    try:
        if os.name == "nt":
            import msvcrt
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                locked = True
            except OSError:
                locked = False
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except OSError:
                locked = False
        yield locked
    finally:
        if locked:
            try:
                if os.name == "nt":
                    import msvcrt
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        stream.close()


def run_upload_queue(queue_dir, store_path, max_wait_seconds=12 * 3600):
    queue_dir = os.path.abspath(queue_dir)
    with _queue_lock(queue_dir) as locked:
        if not locked:
            return {"locked": True, "completed": 0, "failed": 0}
        started = time.monotonic()
        completed = 0
        failed = 0
        attempts_this_run = {}
        insert_paused_paths = set()
        while True:
            paths = sorted(
                os.path.join(queue_dir, name) for name in os.listdir(queue_dir)
                if name.endswith(".json"))
            _recover_retryable_legacy_errors(queue_dir, paths)
            quota_pause = _active_quota_pause(queue_dir)
            if not quota_pause:
                insert_paused_paths.clear()
            actionable = []
            waiting_media = False
            waiting_processing = False
            waiting_cleanup = False
            retry_pending = False
            retry_delay = 5.0
            quota_blocked = False
            for path in paths:
                job = _read_json(path, {})
                status = str(job.get("status", "pending") or "pending")
                if not upload_job_is_actionable(job):
                    continue
                if path in insert_paused_paths:
                    continue
                if (quota_pause
                        and not _job_can_progress_during_quota_pause(job)):
                    continue
                if (status == "failed"
                        and int(attempts_this_run.get(path, 0)) >= 5):
                    continue
                actionable.append(path)
            if not actionable:
                break
            made_progress = False
            for path in actionable:
                try:
                    result = process_upload_job(path, store_path)
                    if result == "completed":
                        completed += 1
                        made_progress = True
                    elif result == "waiting_media":
                        waiting_media = True
                    elif result == "awaiting_processing":
                        waiting_processing = True
                    elif result == "cleanup_pending":
                        waiting_cleanup = True
                    elif result == UPLOAD_INSERT_PAUSED:
                        insert_paused_paths.add(path)
                except YouTubeAuthenticationRequired:
                    # process_upload_job has already persisted the permanent
                    # authentication block. It must not enter timed retries.
                    failed += 1
                except Exception as error:
                    failed += 1
                    attempts_this_run[path] = int(
                        attempts_this_run.get(path, 0)) + 1
                    # process_upload_job releases its per-job lock when the
                    # exception escapes. Reacquire it before classifying the
                    # failure so cancellation/re-enqueue cannot be overwritten.
                    with _upload_job_state_lock(path):
                        job = _read_json(path, {})
                        if not upload_job_is_actionable(job):
                            # A helper may have committed a terminal/manual
                            # state before a later mirror/checkpoint failed.
                            continue
                        if str(job.get("status", "") or "") == "cleanup_pending":
                            # Cleanup intent and exact file identities were
                            # committed. Never regress to an upload state.
                            job["cleanup_error"] = str(error)
                            job["error"] = str(error)
                            job["updated_at"] = (
                                datetime.datetime.now().isoformat(
                                    timespec="seconds"))
                            job["cleanup_attempts"] = int(
                                job.get("cleanup_attempts", 0) or 0) + 1
                            try:
                                _atomic_json(path, job)
                            except Exception:
                                pass
                            waiting_cleanup = True
                            continue
                        if isinstance(error, YouTubeVideoInsertQuotaExceeded):
                            quota_now = time.time()
                            retry_epoch = _quota_retry_after_epoch(
                                error, now_epoch=quota_now)
                            # Publish the project-wide stop before the job
                            # transition; either checkpoint alone is safe after
                            # a crash, but this ordering also prevents watchdog
                            # process churn while the quota job is dormant.
                            _write_quota_pause(
                                queue_dir, retry_epoch, error)
                            _mark_job_quota_waiting(
                                path, job, error, now_epoch=quota_now)
                            quota_blocked = True
                            # Quota is project-wide. Do not spend one failed
                            # videos.insert request on every later queued clip.
                            break
                        job["error"] = str(error)
                        job["attempts"] = int(
                            job.get("attempts", 0) or 0) + 1
                        job["updated_at"] = (
                            datetime.datetime.now().isoformat(
                                timespec="seconds"))
                        if _is_permanent_youtube_request_error(error):
                            # Retrying identical videos.insert metadata cannot
                            # repair a deterministic HTTP 400 and consumed the
                            # project's daily creation quota in reproduction.
                            job["status"] = UPLOAD_ATTENTION_REQUIRED
                            job["upload_attention_required_at"] = (
                                job["updated_at"])
                            job["upload_attention_error"] = str(error)
                            job["permanent_request_error_at"] = (
                                job["updated_at"])
                        elif int(job["attempts"]) >= MAX_UPLOAD_ATTEMPTS:
                            # attempts is durable across workers. Stop a
                            # deterministic FFmpeg/config/API failure forever.
                            job["status"] = UPLOAD_ATTENTION_REQUIRED
                            job["upload_attention_required_at"] = (
                                job["updated_at"])
                            job["upload_attention_error"] = str(error)
                        else:
                            job["status"] = "failed"
                        _atomic_json(path, job)
                        if (job["status"] == "failed"
                                and attempts_this_run[path] < 5):
                            retry_pending = True
                            retry_delay = max(
                                retry_delay,
                                min(120.0, 5.0 * (
                                    2 ** (attempts_this_run[path] - 1))))
            if quota_blocked:
                # Rebuild the actionable list under the newly persisted pause.
                # Fresh inserts will then be filtered, while processing and
                # cleanup jobs later in the queue can finish in this worker.
                continue
            if made_progress:
                continue
            if ((waiting_media or waiting_processing or waiting_cleanup)
                    and time.monotonic() - started < float(max_wait_seconds)):
                time.sleep(10.0 if (waiting_media or waiting_cleanup) else 30.0)
                continue
            if (retry_pending
                    and time.monotonic() - started < float(max_wait_seconds)):
                time.sleep(retry_delay)
                continue
            break
        return {"locked": False, "completed": completed, "failed": failed}
