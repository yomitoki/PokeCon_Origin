"""ZA action prompts: word references first, explicit debug-only glyph recovery.

No session directory is created at Commands start. Debug evidence is appended
only after a fresh, field-confirmed glyph match at a failed call site.
"""
import hashlib
import json
import os
import sys

try:
    from .ActionPromptDebug import rank_action_prompt_candidates, save_action_prompt_debug
    from .ImageDetection import read_command_frame
except ImportError:
    if __package__:
        raise
    from ActionPromptDebug import rank_action_prompt_candidates, save_action_prompt_debug
    from ImageDetection import read_command_frame


ACTION_TARGETS = frozenset("POKEMON_ZA_" + name for name in (
    "IN_MARKER", "OUT_MARKER", "CHAT_MARKER", "HASHIGO_ICON",
    "INVESTIGATE_MARKER", "DOOR_A", "OTHER_A_MARKER", "RESEARCH_A")) | frozenset(("ZA_RESEARCH_A", "ZA_STORY_COMMON_ZA_RESEARCH_A"))
_WRAPPERS = frozenset((
    "check_action_prompt", "_source", "capture_action_prompt_source", "image_check", "ZA_story_movement_a_check",
    "ZA_story_wait_movement_a", "ZA_story_resume_movement_a",
    "ZA_story_checked_movement_action"))
_CATALOG_CACHE = {}


def _root(command):
    override = getattr(command, "_action_prompt_template_root", None)
    if override:
        return os.path.abspath(os.fspath(override))
    current = os.path.dirname(os.path.abspath(__file__))
    while os.path.dirname(current) != current:
        if os.path.basename(current) == "SerialController":
            return current
        current = os.path.dirname(current)
    raise RuntimeError("ActionPromptCheck: SerialController directory not found")


def _source(command, pictures):
    frame = sys._getframe(1)
    try:
        while frame and (frame.f_code.co_name in _WRAPPERS
                         or os.path.abspath(frame.f_code.co_filename) == os.path.abspath(__file__)):
            frame = frame.f_back
        code = frame.f_code if frame else None
        pending = getattr(command, "_za_movement_a_pending", None)
        pending = pending if isinstance(pending, dict) else {}
        saved = pending.get("_action_prompt_source")
        if isinstance(saved, dict) and tuple(saved.get("pictures", ())) == tuple(pictures):
            return dict(saved)
        context_getter = getattr(command, "ZA_story_movement_a_context", None)
        context = context_getter() if callable(context_getter) else (
            getattr(command, "_za_story_pre_step_gate_last_dispatch_state", None),
            getattr(command, "Common_current_state", None))
        return {
            "source_path": os.path.abspath(code.co_filename) if code else "",
            "line": frame.f_lineno if frame else 0,
            "runtime_line": frame.f_lineno if frame else 0,
            "function": code.co_name if code else "unknown",
            "runtime_code_sha256": hashlib.sha256(code.co_code).hexdigest() if code else "",
            "callsite_key": pending.get("key", ""),
            "pictures": list(pictures),
            "step": getattr(command, "_za_story_pre_step_gate_last_dispatch_state", None),
            "context": list(context),
        }
    finally:
        del frame


def capture_action_prompt_source(command, pictures, callsite_key, action):
    """Capture before creating a continuation, so nested endpoints stay distinct."""
    # A second endpoint may be created from the first endpoint's continuation.
    pending = getattr(command, "_za_movement_a_pending", None)
    command._za_movement_a_pending = None
    try:
        source = _source(command, pictures)
    finally:
        command._za_movement_a_pending = pending
    source["callsite_key"] = str(callsite_key)
    code = getattr(action, "__code__", None)
    source["action_first_line"] = code.co_firstlineno if code else None
    return source


def _catalog(root):
    path = os.path.join(root, "Template", "ZA_Story_PIC", "ActionPrompts", "catalog.json")
    stat = os.stat(path)
    signature = (path, stat.st_mtime_ns, stat.st_size)
    if signature not in _CATALOG_CACHE:
        with open(path, encoding="utf-8-sig") as stream:
            payload = json.load(stream)
        rows = payload.get("candidates", payload.get("templates", []))
        if not isinstance(rows, list) or not rows:
            raise ValueError("ActionPrompts/catalog.json has no word references")
        result = []
        for row in rows:
            row = dict(row)
            if not row.get("template_path") or not row.get("picture"):
                raise ValueError("Action prompt reference is missing picture/template_path")
            row.setdefault("manual_target", "ZA_ACTION_PROMPT_" + str(row.get("id", "")).upper())
            if "ZA_RESEARCH_A" in row.get("pictures", ()):
                row["pictures"] = list(row["pictures"]) + ["ZA_STORY_COMMON_ZA_RESEARCH_A"]
            result.append(row)
        _CATALOG_CACHE.clear()
        _CATALOG_CACHE[signature] = result
    return _CATALOG_CACHE[signature]


def _matches(command, root, frame, targets):
    """Use the original registry conditions on exactly this fallback frame."""
    registry = getattr(command, "IMAGE_DETECTION_TARGETS", {})
    for target in targets:
        rows = []
        for index, settings in enumerate(registry.get(target, ())):
            row = dict(settings)
            row.update(id=target + ":" + str(index), picture=target)
            rows.append(row)
        if not rows:
            continue
        results = rank_action_prompt_candidates(frame, rows, template_root=root)
        operator = getattr(command, "IMAGE_DETECTION_OPERATORS", {}).get(target, "OR")
        flags = [bool(row.get("matched")) for row in results]
        if (all(flags) if operator == "AND" else any(flags)):
            return True
    return False


def _field(command, root, frame):
    prefix = "POKEMON_ZA_"
    if not _matches(command, root, frame, (prefix + "FIELD_W", prefix + "FIELD_BACK_W")):
        return False
    if not _matches(command, root, frame, tuple(prefix + n for n in (
            "MERIP_ICON_GET5", "BATTLE", "WANINOKO_ICON", "ODAIRU_ICON", "ABSOL_ICON", "DEAD"))):
        return False
    # In particular, title/menu/button legends must never activate this route.
    return not _matches(command, root, frame, tuple(prefix + n for n in (
        "BATTLE_BALL_CHECK", "ESCAPE", "EYE_CHECK_HIGH_POKE", "X_MENU_OPEN",
        "TEXT_WHITE_COMMENT", "TEXT_BLACK_COMMENT", "TEXT_GREEN_COMMENT",
        "HELP_MARKER", "1_SELECT", "2_SELECT", "3_SELECT", "4_SELECT")))


def _supplemental(command):
    # 補完モードのセッション（LocalFunction/ZA/SupplementalSession.py）が付いている間
    return getattr(command, "_command_supplemental_session", None) is not None


def _check_supplemental(command, pictures):
    """補完モード: 日本語の文字は出ないので、登録済みの判定（A の字だけに置き換わる）に任せる。"""
    registry = getattr(command, "IMAGE_DETECTION_TARGETS", {})
    targets = []
    for value in pictures:
        target = "ZA_STORY_COMMON_ZA_RESEARCH_A" if value == "ZA_RESEARCH_A" else value
        if target not in registry:
            # ZA_ACTION_PROMPT_* などの単語だけの参照は、汎用の A で確かめる。
            target = "POKEMON_ZA_OTHER_A_MARKER"
        if target not in targets:
            targets.append(target)
    matched = next((target for target in targets if command._image_check_target(target)), None)
    command.last_action_prompt_detection = {
        "matched": bool(matched), "status": "supplemental_A",
        "pictures": list(pictures), "targets": targets, "target": matched,
    }
    return bool(matched)


def check_action_prompt(command, pictures, count_attempt=False):
    """One fresh frame; count_attempt means one failed logical wait/search.

    Repeated samples inside a three-second wait pass count_attempt=False.
    The caller completes one attempt once that wait has failed.
    """
    requested_pictures = tuple(str(value) for value in pictures)
    pictures = tuple("ZA_RESEARCH_A" if value in ("POKEMON_ZA_RESEARCH_A", "ZA_STORY_COMMON_ZA_RESEARCH_A")
                     else value for value in requested_pictures)
    if not pictures or any(value not in ACTION_TARGETS and not value.startswith("ZA_ACTION_PROMPT_")
                           for value in pictures):
        raise ValueError("Unsupported action prompt: " + repr(pictures))
    alive = getattr(command, "checkIfAlive", lambda: None)
    alive()
    if _supplemental(command):
        return _check_supplemental(command, pictures)
    frame = read_command_frame(command)
    if frame is None:
        command.last_action_prompt_detection = {"matched": False, "status": "no_frame"}
        return False
    root = _root(command)
    candidates = _catalog(root)
    selected = [row for row in candidates if (
        row["picture"] in pictures
        or row["manual_target"] in pictures
        or set(row.get("pictures", ())).intersection(pictures)
        or (set(pictures).intersection(("POKEMON_ZA_OTHER_A_MARKER", "POKEMON_ZA_DOOR_A"))))]
    ranking = rank_action_prompt_candidates(frame, selected, template_root=root, check_alive=alive)
    best = next((row for row in ranking if row.get("matched")), None)
    source = _source(command, requested_pictures)
    identity = json.dumps([source["source_path"], source.get("runtime_code_sha256"),
                           source["context"], source["step"], source["callsite_key"],
                           source["function"], source["line"], source.get("action_first_line"), pictures],
                          ensure_ascii=False, sort_keys=True)
    attempts = getattr(command, "_action_prompt_attempts", {})
    command._action_prompt_attempts = attempts
    command.last_action_prompt_detection = {
        "matched": bool(best), "status": "word", "pictures": list(pictures),
        "ranking": ranking, "source": source,
    }
    if ranking:
        command.last_image_detection = best or ranking[0]
    if best:
        attempts.pop(identity, None)
        return True
    if not bool(getattr(command, "Debug_A_Check", False)) or not count_attempt:
        return False
    attempts[identity] = attempts.get(identity, 0) + 1
    command.last_action_prompt_detection["attempt"] = attempts[identity]
    if attempts[identity] < 3:
        return False
    if not _field(command, root, frame):
        command.last_action_prompt_detection["status"] = "fallback_not_field"
        return False
    # Keep the A letter and white disk, omitting the reference's outer background.
    # This tight screen ROI also excludes the title's PRESS A BUTTON legend.
    glyph = {"id": "debug_a_glyph", "picture": "POKEMON_ZA_OTHER_A_MARKER",
             "template_path": "Template/ZA_Story_PIC/Common/other_a_marker.png",
             "template_crop": [3, 3, 20, 20], "crop": [550, 250, 900, 550],
             "threshold": .90, "use_gray": True}
    fallback = rank_action_prompt_candidates(frame, [glyph], template_root=root, check_alive=alive)[0]
    command.last_action_prompt_detection["fallback"] = fallback
    if not fallback.get("matched"):
        return False
    alive()
    # The same original frame is used for the saved image and every ranking row.
    # No run/session initialization touches this stable, accumulating directory.
    output_root = getattr(command, "_action_prompt_debug_root", os.path.join(root, "Debug_A_Check"))
    result = save_action_prompt_debug(
        frame, candidates, source, output_root, template_root=root,
        comparison_crop=glyph["crop"], fallback_detail=fallback, check_alive=alive)
    alive()
    attempts.pop(identity, None)
    command.last_action_prompt_detection.update(matched=True, status="debug_glyph", evidence=result)
    print("[DEBUG_A_CHECK] {}: A+文字3回不一致 -> A一致; 保存 {}".format(
        source["callsite_key"] or source["function"], result.get("event_dir", output_root)))
    return True
