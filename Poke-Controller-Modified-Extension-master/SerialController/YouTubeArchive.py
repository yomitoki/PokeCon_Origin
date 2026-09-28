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
import secrets
import shutil
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


class UploadSessionExpired(RuntimeError):
    pass


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


def save_channel_store(path, store):
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


def channel_profile_names(path):
    return sorted(load_channel_store(path)["profiles"], key=str.casefold)


def set_default_channel_profile(path, name):
    store = load_channel_store(path)
    name = str(name or "").strip()
    if name and name not in store["profiles"]:
        raise ValueError("YouTubeチャンネル設定が見つかりません: " + name)
    store["default_profile"] = name
    return save_channel_store(path, store)


def remove_channel_profile(path, name):
    store = load_channel_store(path)
    name = str(name or "").strip()
    store["profiles"].pop(name, None)
    if store["default_profile"] == name:
        store["default_profile"] = next(iter(sorted(store["profiles"])), "")
    return save_channel_store(path, store)


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
    save_channel_store(store_path, store)
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


def format_timestamp(seconds):
    value = max(0, int(float(seconds or 0.0)))
    hours, value = divmod(value, 3600)
    minutes, seconds = divmod(value, 60)
    return "{}:{:02d}:{:02d}".format(hours, minutes, seconds) \
        if hours else "{}:{:02d}".format(minutes, seconds)


def _load_common_occurrences(session_dir):
    value = _read_json(os.path.join(session_dir, "common_function_index.json"), {})
    rows = value.get("occurrences", []) if isinstance(value, dict) else []
    return [row for row in rows if isinstance(row, dict)]


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
    for occurrence in _load_common_occurrences(session_dir):
        when = float(occurrence.get("start_seconds", 0.0) or 0.0)
        if when < segment_start or (segment_duration and when >= end):
            continue
        caller = occurrence.get("step_owner") or occurrence.get("direct_caller") or "caller不明"
        label = "{} → {}".format(caller, occurrence.get("target_function", ""))
        markers.append((when - segment_start, label))
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
    lines.extend(("", "詳細なStep、呼び出し元、検知結果、ソーススナップショットは録画フォルダのローカル索引に保存されています。"))
    return _truncate_utf8("\n".join(lines), 5000)


def _safe_title(job, part=1, total=1):
    pieces = ["PokeCon", str(job.get("input_set", "") or "")]
    if job.get("command"):
        pieces.append(str(job["command"]))
    pieces.append(str(job.get("created_at", "") or "")[:19].replace("T", " "))
    title = " - ".join(piece for piece in pieces if piece)
    if total > 1:
        title += " ({}/{})".format(part, total)
    return title[:100]


def enqueue_upload_job(queue_dir, media_path, session_dir, input_set="",
                       channel_profile="", recording_kind="normal",
                       command="", delete_local=True, commands_video_mode="",
                       segment_seconds=DEFAULT_SEGMENT_SECONDS):
    queue_dir = os.path.abspath(queue_dir)
    media_path = os.path.abspath(media_path)
    session_dir = os.path.abspath(session_dir or os.path.dirname(media_path))
    os.makedirs(queue_dir, exist_ok=True)
    # One finalized recording path represents one logical upload.  Keep this
    # stable when metadata/keyframes later change the directory mtime.
    identity = hashlib.sha256((media_path + "\0" + session_dir).encode(
        "utf-8")).hexdigest()[:24]
    path = os.path.join(queue_dir, identity + ".json")
    existing = _read_json(path, {})
    if isinstance(existing, dict) and existing.get("status") in (
            "pending", "waiting_media", "uploading", "awaiting_processing", "completed"):
        return path
    payload = {
        "version": 1,
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
        "segment_seconds": min(11 * 3600, max(10 * 60, int(segment_seconds or DEFAULT_SEGMENT_SECONDS))),
        "segments": [],
        "attempts": 0,
    }
    _atomic_json(path, payload)
    return path


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
                value = json.loads(raw.decode("utf-8")) if raw else {}
                return size, str(value.get("id", "") or "")
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


def _upload_resumable(path, token, upload_url, progress=None, chunk_size=8 * 1024 * 1024):
    size = os.path.getsize(path)
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    offset, completed_video_id = _resumable_upload_offset(
        upload_url, token, size)
    if completed_video_id:
        return completed_video_id
    if callable(progress) and offset:
        progress(offset, size)
    with open(path, "rb") as stream:
        while offset < size:
            stream.seek(offset)
            data = stream.read(min(chunk_size, size - offset))
            end = offset + len(data) - 1
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
                        value = json.loads(raw.decode("utf-8")) if raw else {}
                        return str(value.get("id", "") or "")
            except urllib.error.HTTPError as error:
                if error.code == 308:
                    acknowledged = str(error.headers.get("Range", "") or "")
                    if "-" in acknowledged:
                        try:
                            offset = int(acknowledged.rsplit("-", 1)[-1]) + 1
                        except ValueError:
                            offset = end + 1
                    else:
                        offset = end + 1
                    if callable(progress):
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
    if upload_status in ("rejected", "failed", "deleted") or processing == "failed":
        return "failed"
    if upload_status == "processed" or processing == "succeeded":
        return "processed"
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
    _atomic_json(os.path.join(job["session_dir"], REMOTE_FILE_NAME), remote)
    index_path = os.path.join(job["session_dir"], "common_function_index.json")
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
                    "url": youtube_watch_url(video["video_id"], relative),
                }
        _atomic_json(index_path, index)
    metadata_path = os.path.join(job["session_dir"], "command_monitor.json")
    metadata = _read_json(metadata_path, None)
    if isinstance(metadata, dict):
        metadata["youtube"] = remote
        _atomic_json(metadata_path, metadata)
    return remote


def _cleanup_uploaded_recording(job):
    session = os.path.abspath(job["session_dir"])
    allowed_names = {
        "recording.mp4", "recording.avi", "recording.wav",
        "recording_presentation_aligned.wav",
    }
    candidates = [job.get("media_path", "")]
    candidates.extend(os.path.join(session, name) for name in allowed_names)
    for raw in candidates:
        path = os.path.abspath(str(raw or ""))
        try:
            if (os.path.commonpath([session, path]) == session
                    and os.path.basename(path) in allowed_names
                    and os.path.isfile(path)):
                os.remove(path)
        except (OSError, ValueError):
            pass
    segment_dir = os.path.join(session, ".youtube_segments")
    try:
        if os.path.commonpath([session, os.path.abspath(segment_dir)]) == session:
            shutil.rmtree(segment_dir, ignore_errors=True)
    except ValueError:
        pass


def process_upload_job(path, store_path):
    job = _read_json(path, None)
    if not isinstance(job, dict):
        raise ValueError("YouTube upload jobを読み込めません: " + path)
    media_path = os.path.abspath(str(job.get("media_path", "") or ""))
    if not os.path.isfile(media_path) or os.path.getsize(media_path) <= 1024:
        if not os.path.isdir(str(job.get("session_dir", "") or "")):
            job["status"] = "cancelled"
            job["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
            _atomic_json(path, job)
            return "cancelled"
        job["status"] = "waiting_media"
        job["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        _atomic_json(path, job)
        return "waiting_media"
    profile_name, profile = _resolve_profile(store_path, job.get("channel_profile", ""))
    token = _access_token(profile)
    duration = float(job.get("duration_seconds", 0.0) or 0.0)
    if duration <= 0.0:
        duration = _probe_duration(media_path)
        if duration <= 0.0:
            raise RuntimeError("録画時間を確認できません: " + media_path)
        job["duration_seconds"] = duration
    segment_seconds = float(job.get("segment_seconds", DEFAULT_SEGMENT_SECONDS) or DEFAULT_SEGMENT_SECONDS)
    total = max(1, int(math.ceil(duration / segment_seconds)))
    if not job.get("segments"):
        job["segments"] = [{
            "part": part + 1,
            "start_seconds": round(part * segment_seconds, 6),
            "duration_seconds": round(min(segment_seconds, duration - part * segment_seconds), 6),
            "status": "pending",
        } for part in range(total)]
    job["status"] = "uploading"
    job["channel_profile_resolved"] = profile_name
    _atomic_json(path, job)
    pending_processing = False
    for segment in job["segments"]:
        if segment.get("video_id"):
            status = _processing_status(token, segment["video_id"])
            segment["processing_status"] = status
            if status == "failed":
                raise RuntimeError(
                    "YouTube側で動画処理に失敗しました: " + segment["video_id"])
            if status == "missing":
                missing_checks = int(segment.get("missing_checks", 0) or 0) + 1
                segment["missing_checks"] = missing_checks
                if missing_checks < 20:
                    pending_processing = True
                    continue
                segment["failed_video_id"] = segment.pop("video_id")
                segment.pop("upload_url", None)
                segment["status"] = "pending"
                _atomic_json(path, job)
            elif status != "processed":
                pending_processing = True
                continue
            else:
                continue
        segment_path = _materialize_segment(job, segment, total)
        segment["local_path"] = segment_path
        if not segment.get("upload_url"):
            segment["upload_url"] = _initiate_resumable_upload(
                token, segment_path,
                _safe_title(job, int(segment["part"]), total),
                build_video_description(
                    job, segment["start_seconds"], segment["duration_seconds"]),
                str(job.get("privacy_status", "unlisted") or "unlisted"))
            _atomic_json(path, job)

        def progress(offset, size):
            segment["uploaded_bytes"] = int(offset)
            segment["total_bytes"] = int(size)
            job["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
            _atomic_json(path, job)

        try:
            segment["video_id"] = _upload_resumable(
                segment_path, token, segment["upload_url"], progress=progress)
        except UploadSessionExpired:
            segment.pop("upload_url", None)
            segment["upload_url"] = _initiate_resumable_upload(
                token, segment_path,
                _safe_title(job, int(segment["part"]), total),
                build_video_description(
                    job, segment["start_seconds"], segment["duration_seconds"]),
                str(job.get("privacy_status", "unlisted") or "unlisted"))
            _atomic_json(path, job)
            segment["video_id"] = _upload_resumable(
                segment_path, token, segment["upload_url"], progress=progress)
        segment["status"] = "uploaded"
        segment["processing_status"] = _processing_status(token, segment["video_id"])
        if segment["processing_status"] == "missing":
            segment["missing_checks"] = 1
        pending_processing = pending_processing or segment["processing_status"] != "processed"
        if segment_path != media_path:
            try:
                os.remove(segment_path)
            except OSError:
                pass
        _write_remote(job, profile_name, profile)
        _atomic_json(path, job)
    if pending_processing:
        job["status"] = "awaiting_processing"
        job["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        _write_remote(job, profile_name, profile)
        _atomic_json(path, job)
        return "awaiting_processing"
    job["status"] = "completed"
    job["completed_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    job["updated_at"] = job["completed_at"]
    _write_remote(job, profile_name, profile)
    _atomic_json(path, job)
    if job.get("delete_local_after_processing"):
        _cleanup_uploaded_recording(job)
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
            stream.seek(0)
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
        while True:
            paths = sorted(
                os.path.join(queue_dir, name) for name in os.listdir(queue_dir)
                if name.endswith(".json"))
            actionable = []
            waiting_media = False
            waiting_processing = False
            retry_pending = False
            retry_delay = 5.0
            for path in paths:
                job = _read_json(path, {})
                status = str(job.get("status", "pending") or "pending")
                if status in ("completed", "cancelled"):
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
                except Exception as error:
                    failed += 1
                    attempts_this_run[path] = int(
                        attempts_this_run.get(path, 0)) + 1
                    job = _read_json(path, {})
                    job["status"] = "failed"
                    job["error"] = str(error)
                    job["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
                    job["attempts"] = int(job.get("attempts", 0) or 0) + 1
                    _atomic_json(path, job)
                    if attempts_this_run[path] < 5:
                        retry_pending = True
                        retry_delay = max(
                            retry_delay,
                            min(120.0, 5.0 * (2 ** (attempts_this_run[path] - 1))))
            if made_progress:
                continue
            if ((waiting_media or waiting_processing)
                    and time.monotonic() - started < float(max_wait_seconds)):
                time.sleep(10.0 if waiting_media else 30.0)
                continue
            if (retry_pending
                    and time.monotonic() - started < float(max_wait_seconds)):
                time.sleep(retry_delay)
                continue
            break
        return {"locked": False, "completed": completed, "failed": failed}
