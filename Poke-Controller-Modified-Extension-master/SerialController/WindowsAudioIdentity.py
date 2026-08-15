"""Stable Windows capture-audio identities independent of PortAudio indexes."""
from __future__ import annotations

import os
import re

try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows compatibility
    winreg = None


_MM_CAPTURE = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture")
_SWD_AUDIO = r"SYSTEM\CurrentControlSet\Enum\SWD\MMDEVAPI"
_DEVICE_INSTANCE = "{b3f8fa53-0004-438e-9003-51a46e139bfc},2"
_DEVICE_NAME = "{b3f8fa53-0004-438e-9003-51a46e139bfc},6"
_INTERFACE_NAME = "{a45c254e-df1c-4efd-8020-67d146a850e0},2"
_INTERFACE_PATH = "{233164c8-1b2c-4c7d-bc68-b671687a2567},1"


def without_portaudio_index(value):
    return re.sub(r"^\s*\d+\s*:\s*", "", str(value or "")).strip()


def normalized_audio_name(value):
    value = without_portaudio_index(value)
    # Windows display ordinals are enumeration labels, not physical identity.
    value = re.sub(r"\(\s*\d+\s*-\s*", "(", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


def audio_name_matches(left, right):
    """Match a full Windows friendly name to a possibly truncated MME name."""
    left = without_portaudio_index(left).casefold()
    right = without_portaudio_index(right).casefold()
    if not left or not right:
        return False
    if left == right:
        return True
    shorter, longer = sorted((left, right), key=len)
    if len(shorter) >= 20 and longer.startswith(shorter):
        return True
    # The Windows ordinal may have changed since the InputSet was saved.
    left = normalized_audio_name(left)
    right = normalized_audio_name(right)
    if left == right:
        return True
    shorter, longer = sorted((left, right), key=len)
    return len(shorter) >= 20 and longer.startswith(shorter)


def physical_usb_key(value):
    """Extract the composite USB location shared by video/audio interfaces."""
    match = re.search(
        r"(?:\\|#)([0-9a-f]+&[0-9a-f]+&[0-9]+)&[0-9a-f]{4}(?:\\|#|$)",
        str(value or ""), re.IGNORECASE)
    return match.group(1).casefold() if match else ""


def usb_connection_token(value):
    """Return the stable part of a composite USB location.

    DirectShow can change the leading enumerator nibble of an otherwise
    unchanged device path (for example ``a&2838c96c&0`` to
    ``b&2838c96c&0``).  The middle token continues to identify that USB
    connection and is therefore useful after Camera ID/order changes.
    """
    key = physical_usb_key(value)
    parts = key.split("&")
    return parts[1] if len(parts) >= 3 else ""


def _query_value(key, name, default=""):
    try:
        return winreg.QueryValueEx(key, name)[0]
    except (FileNotFoundError, OSError):
        return default


def capture_endpoints():
    """Return Windows capture endpoints, including temporarily disconnected."""
    if os.name != "nt" or winreg is None:
        return []
    rows = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _MM_CAPTURE) as root:
            key_count = winreg.QueryInfoKey(root)[0]
            for index in range(key_count):
                endpoint_id = winreg.EnumKey(root, index)
                try:
                    with winreg.OpenKey(root, endpoint_id) as endpoint:
                        state = int(_query_value(endpoint, "DeviceState", 0) or 0)
                        with winreg.OpenKey(endpoint, "Properties") as props:
                            instance_id = str(_query_value(
                                props, _DEVICE_INSTANCE, "") or "")
                            device_name = str(_query_value(
                                props, _DEVICE_NAME, "") or "")
                            interface_name = str(_query_value(
                                props, _INTERFACE_NAME, "") or "")
                            interface_path = str(_query_value(
                                props, _INTERFACE_PATH, "") or "")
                    enum_name = "{0.0.1.00000000}." + endpoint_id
                    friendly_name = ""
                    try:
                        with winreg.OpenKey(
                                winreg.HKEY_LOCAL_MACHINE,
                                _SWD_AUDIO + "\\" + enum_name) as enum_key:
                            friendly_name = str(_query_value(
                                enum_key, "FriendlyName", "") or "")
                    except OSError:
                        pass
                    if not friendly_name:
                        friendly_name = "{} ({})".format(
                            interface_name, device_name).strip(" ()")
                    rows.append({
                        "endpoint_id": endpoint_id.casefold(),
                        "friendly_name": friendly_name,
                        "device_instance_id": instance_id,
                        "device_interface_path": interface_path,
                        "physical_usb_key": physical_usb_key(
                            interface_path or instance_id),
                        "active": state == 1,
                        "state": state,
                    })
                except OSError:
                    continue
    except OSError:
        return []
    return rows


def _endpoints_matching_label(label, endpoints):
    raw = [item for item in endpoints
           if without_portaudio_index(label).casefold()
           == str(item.get("friendly_name", "")).strip().casefold()
           or _raw_audio_name_prefix_matches(
               label, item.get("friendly_name", ""))]
    if raw:
        return raw
    return [item for item in endpoints if audio_name_matches(
        label, item.get("friendly_name", ""))]


def identity_for_audio_label(label, endpoints=None, active_only=True):
    if not label or str(label).startswith("選択ゲーム音声 [PID:"):
        return {}
    endpoints = capture_endpoints() if endpoints is None else list(endpoints)
    candidates = [item for item in endpoints if item.get("active", False)] \
        if active_only else endpoints
    matches = _endpoints_matching_label(label, candidates)
    if len(matches) != 1:
        return {}
    item = matches[0]
    return {
        "endpoint_id": item.get("endpoint_id", ""),
        "device_instance_id": item.get("device_instance_id", ""),
        "device_interface_path": item.get("device_interface_path", ""),
        "physical_usb_key": item.get("physical_usb_key", ""),
        "friendly_name": item.get("friendly_name", ""),
    }


def enrich_saved_audio_identity(saved, camera_device_path="", endpoints=None):
    """Add a stable Windows endpoint identity to a legacy Audio snapshot.

    Returns ``True`` only when ``saved`` was changed.  A unique old friendly
    name is preferred.  The Camera USB location is used only to disambiguate
    legacy capture-card audio; a remembered stable endpoint is never replaced
    with a merely similar device.
    """
    if not isinstance(saved, dict) or not saved.get("enabled", True):
        return False
    saved_name = str(saved.get("device_name", "") or "")
    if not saved_name or saved_name.startswith("選択ゲーム音声 [PID:"):
        return False
    endpoints = capture_endpoints() if endpoints is None else list(endpoints)
    stable_fields = ("endpoint_id", "device_instance_id",
                     "device_interface_path")
    has_stable_identity = any(saved.get(field) for field in stable_fields)
    matches = []
    if has_stable_identity:
        for item in endpoints:
            if any(str(saved.get(field, "") or "").casefold()
                   and str(saved.get(field, "") or "").casefold()
                   == str(item.get(field, "") or "").casefold()
                   for field in stable_fields):
                matches.append(item)
    else:
        matches = _endpoints_matching_label(saved_name, endpoints)

    camera_usb = physical_usb_key(camera_device_path)
    if len(matches) != 1 and not has_stable_identity and camera_usb:
        matches = [item for item in endpoints
                   if str(item.get("physical_usb_key", "") or "").casefold()
                   == camera_usb]
    if len(matches) != 1:
        return False

    item = matches[0]
    identity = {
        "endpoint_id": item.get("endpoint_id", ""),
        "device_instance_id": item.get("device_instance_id", ""),
        "device_interface_path": item.get("device_interface_path", ""),
        "physical_usb_key": item.get("physical_usb_key", ""),
        "friendly_name": item.get("friendly_name", ""),
    }
    changed = False
    for key, value in identity.items():
        if value and saved.get(key) != value:
            saved[key] = value
            changed = True
    return changed


def upgrade_input_set_audio_identities(data, endpoints=None):
    """Upgrade every legacy InputSet Audio entry in an already-loaded file."""
    if not isinstance(data, dict):
        return False
    items = data.get("input_sets", {})
    if not isinstance(items, dict):
        return False
    pending = []
    for item in items.values():
        if not isinstance(item, dict):
            continue
        audio = item.get("audio")
        camera = item.get("camera", {})
        if not isinstance(audio, dict) or any(audio.get(field) for field in (
                "endpoint_id", "device_instance_id", "device_interface_path")):
            continue
        name = str(audio.get("device_name", "") or "")
        # System defaults and application-loopback entries do not represent a
        # particular USB capture endpoint.
        if not audio.get("enabled", True) or "usb" not in name.casefold():
            continue
        pending.append((audio, camera if isinstance(camera, dict) else {}))
    if not pending:
        return False
    endpoints = capture_endpoints() if endpoints is None else list(endpoints)
    changed = False
    for audio, camera in pending:
        changed = enrich_saved_audio_identity(
            audio, camera_device_path=camera.get("device_path", ""),
            endpoints=endpoints) or changed
    return changed


def _label_for_endpoint(endpoint, labels):
    friendly = endpoint.get("friendly_name", "")
    exact = [label for label in labels
             if without_portaudio_index(label).casefold()
             == str(friendly).strip().casefold()]
    if exact:
        return exact[0]
    raw_prefix = [label for label in labels
                  if _raw_audio_name_prefix_matches(label, friendly)]
    if raw_prefix:
        return raw_prefix[0]
    matches = [label for label in labels if audio_name_matches(label, friendly)]
    return matches[0] if matches else None


def _raw_audio_name_prefix_matches(left, right):
    left = without_portaudio_index(left).casefold()
    right = without_portaudio_index(right).casefold()
    shorter, longer = sorted((left, right), key=len)
    return len(shorter) >= 20 and longer.startswith(shorter)


def resolve_saved_audio(saved, available_labels, camera_device_path="",
                        endpoints=None):
    """Resolve an InputSet audio endpoint without trusting display numbers."""
    saved = saved if isinstance(saved, dict) else {}
    labels = list(available_labels or [])
    saved_name = str(saved.get("device_name", "") or "")
    if saved_name.startswith("選択ゲーム音声 [PID:"):
        return next((label for label in labels if label == saved_name), None)
    endpoints = capture_endpoints() if endpoints is None else list(endpoints)
    active = [item for item in endpoints if item.get("active", False)]

    endpoint_id = str(saved.get("endpoint_id", "") or "").casefold()
    instance_id = str(saved.get("device_instance_id", "") or "").casefold()
    interface_path = str(saved.get("device_interface_path", "") or "").casefold()
    saved_usb = str(saved.get("physical_usb_key", "") or "").casefold() \
        or physical_usb_key(camera_device_path)
    has_stable_identity = bool(endpoint_id or instance_id or interface_path)

    identity_matches = []
    for item in active:
        if endpoint_id and str(item.get("endpoint_id", "")).casefold() == endpoint_id:
            identity_matches.append(item)
        elif instance_id and str(item.get("device_instance_id", "")).casefold() == instance_id:
            identity_matches.append(item)
        elif interface_path and str(item.get("device_interface_path", "")).casefold() == interface_path:
            identity_matches.append(item)
    if not identity_matches and saved_usb:
        identity_matches = [item for item in active
                            if str(item.get("physical_usb_key", "")).casefold()
                            == saved_usb]
    if len(identity_matches) == 1:
        return _label_for_endpoint(identity_matches[0], labels)
    if has_stable_identity:
        # The remembered physical endpoint is absent. Never silently attach a
        # different identical capture card merely because its display name is
        # similar.
        return None

    # Legacy InputSets can be upgraded by their old full friendly name. This
    # includes inactive endpoints so a disconnected device is not replaced by
    # the first currently connected device with the same normalized name.
    legacy_endpoints = _endpoints_matching_label(saved_name, endpoints)
    if len(legacy_endpoints) == 1:
        return _label_for_endpoint(legacy_endpoints[0], labels) \
            if legacy_endpoints[0].get("active", False) else None
    if len(legacy_endpoints) > 1 and saved_usb:
        matched = [item for item in legacy_endpoints
                   if str(item.get("physical_usb_key", "")).casefold()
                   == saved_usb]
        if len(matched) == 1 and matched[0].get("active", False):
            return _label_for_endpoint(matched[0], labels)

    normalized = str(saved.get("normalized_name", "") or "") \
        or normalized_audio_name(saved_name)
    name_matches = [label for label in labels
                    if normalized and normalized_audio_name(label) == normalized]
    return name_matches[0] if len(name_matches) == 1 else None
