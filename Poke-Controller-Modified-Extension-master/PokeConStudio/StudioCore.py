#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure, testable helpers used by the PokeConStudio desktop application.

The module deliberately does not import Tk, OpenCV, or PokeCon runtime classes.
Profiles and source/image discovery therefore remain usable on every Python
runtime supported by PokeCon, including the compatibility Python 3.7 setup.
"""
from __future__ import print_function

import ast
import hashlib
import io
import json
import math
import os
import pprint
import re
import sys
import tempfile
import time
import tokenize


SCHEMA_VERSION = 1
SOURCE_SUFFIXES = (".py", ".pyw", ".pyfrag")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
MANAGED_BEGIN = "# POKECON_STUDIO_DETECTION_BEGIN"
MANAGED_END = "# POKECON_STUDIO_DETECTION_END"
DEFAULT_OPERATION_PATTERNS = (
    r"(^|_)(press|hold|release|send|input|stick|button)(_|$)",
    r"^(pressRep|holdEnd|stickEnd|moveStick)$",
    r"^game_input$",
    r"^direct_serial$",
    r"^ZA_.*_ACTION$",
    r"^ZA_MOVE_SEE$",
    r"^[LR](button|stick)_",
)
DEFAULT_PANEL_VISIBILITY = {
    "source_list": True,
    "source_editor": True,
    "image_detection": True,
    "run_support": True,
}


def default_profile(project_root):
    project_root = os.path.abspath(project_root)
    serial_root = os.path.join(project_root, "SerialController")
    return {
        "source_files": [],
        "source_folders": [
            os.path.join(serial_root, "Commands", "PythonCommands")
        ],
        "image_folders": [os.path.join(serial_root, "Template")],
        "include_folders": [serial_root, project_root],
        "capture_source": "0",
        "operation_patterns": list(DEFAULT_OPERATION_PATTERNS),
        "last_source": "",
        "last_operation_session": "",
        "last_command_recording": "",
        "panel_visibility": dict(DEFAULT_PANEL_VISIBILITY),
    }


def default_profile_store_path():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(
        base, "PokeConModifiedExtension", "pokecon_studio_profiles.json")


def _unique_paths(values):
    result = []
    seen = set()
    for value in values or ():
        if not isinstance(value, str) or not value.strip():
            continue
        path = os.path.abspath(os.path.expandvars(os.path.expanduser(value)))
        key = os.path.normcase(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def normalize_profile(value, project_root):
    source = value if isinstance(value, dict) else {}
    fallback = default_profile(project_root)
    result = {}
    for key in ("source_files", "source_folders", "image_folders",
                "include_folders"):
        result[key] = _unique_paths(source.get(key, fallback[key]))
    result["capture_source"] = str(
        source.get("capture_source", fallback["capture_source"]) or "0")
    patterns = source.get("operation_patterns", fallback["operation_patterns"])
    result["operation_patterns"] = [
        str(pattern) for pattern in patterns
        if isinstance(pattern, str) and pattern.strip()
    ] or list(DEFAULT_OPERATION_PATTERNS)
    result["last_source"] = str(source.get("last_source", "") or "")
    result["last_operation_session"] = str(
        source.get("last_operation_session", "") or "")
    result["last_command_recording"] = str(
        source.get("last_command_recording", "") or "")
    panel_visibility = source.get(
        "panel_visibility", fallback["panel_visibility"])
    if not isinstance(panel_visibility, dict):
        panel_visibility = {}
    result["panel_visibility"] = {
        key: bool(panel_visibility.get(key, default))
        for key, default in DEFAULT_PANEL_VISIBILITY.items()
    }
    return result


class _ProfileStoreLock(object):
    """Small cross-process lock for one profile-store JSON file."""

    def __init__(self, path, timeout=5.0):
        self.path = os.path.abspath(path)
        self.timeout = float(timeout)
        self.stream = None
        self.locked = False

    def __enter__(self):
        directory = os.path.dirname(self.path)
        if not os.path.isdir(directory):
            try:
                os.makedirs(directory)
            except OSError:
                if not os.path.isdir(directory):
                    raise
        self.stream = open(self.path, "a+b")
        self.stream.seek(0, os.SEEK_END)
        if self.stream.tell() == 0:
            self.stream.write(b"\0")
            self.stream.flush()
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self.stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(
                        self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.locked = True
                return self
            except (IOError, OSError):
                if time.monotonic() >= deadline:
                    self.stream.close()
                    self.stream = None
                    raise TimeoutError(
                        "PokeConStudio設定をほかのプロセスが更新中です。")
                time.sleep(0.05)

    def __exit__(self, exception_type, exception_value, traceback_value):
        if self.stream is None:
            return
        if self.locked:
            try:
                self.stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
            except (IOError, OSError):
                pass
        self.stream.close()
        self.stream = None
        self.locked = False


class ProfileStore(object):
    """Named, atomically persisted path groups for resuming Studio work."""

    def __init__(self, path, project_root):
        self.path = os.path.abspath(path)
        self.project_root = os.path.abspath(project_root)
        self.data = self._load()

    def _empty(self):
        return {
            "schema_version": SCHEMA_VERSION,
            "last_profile": "PokeCon既定",
            "profiles": {"PokeCon既定": default_profile(self.project_root)},
        }

    def _load(self):
        try:
            with io.open(self.path, "r", encoding="utf-8") as stream:
                value = json.load(stream)
        except (OSError, ValueError, TypeError):
            return self._empty()
        if not isinstance(value, dict) or not isinstance(value.get("profiles"), dict):
            return self._empty()
        profiles = {}
        for name, profile in value["profiles"].items():
            if not isinstance(name, str) or not name.strip():
                continue
            profiles[name.strip()] = normalize_profile(profile, self.project_root)
        if not profiles:
            return self._empty()
        last_profile = str(value.get("last_profile", "") or "")
        if last_profile not in profiles:
            last_profile = sorted(profiles, key=str.casefold)[0]
        return {
            "schema_version": SCHEMA_VERSION,
            "last_profile": last_profile,
            "profiles": profiles,
        }

    def names(self):
        return sorted(self.data["profiles"], key=str.casefold)

    def get(self, name):
        profile = self.data["profiles"].get(str(name))
        if profile is None:
            raise KeyError(name)
        return normalize_profile(profile, self.project_root)

    def set(self, name, profile, select=True):
        name = str(name or "").strip()
        if not name:
            raise ValueError("設定名を入力してください。")
        normalized = normalize_profile(profile, self.project_root)

        def apply(latest):
            latest["profiles"][name] = normalized
            if select:
                latest["last_profile"] = name
            return name

        return self._update(apply)

    def select(self, name):
        def apply(latest):
            if name not in latest["profiles"]:
                raise KeyError(name)
            latest["last_profile"] = name

        self._update(apply)

    def delete(self, name):
        def apply(latest):
            if name not in latest["profiles"]:
                return False
            if len(latest["profiles"]) <= 1:
                raise ValueError("最後の設定は削除できません。")
            del latest["profiles"][name]
            if latest.get("last_profile") == name:
                latest["last_profile"] = sorted(
                    latest["profiles"], key=str.casefold)[0]
            return True

        return self._update(apply)

    def save(self):
        """Merge this snapshot into the newest on-disk data and save it."""
        local = self.data
        local_profiles = {
            str(name).strip(): normalize_profile(profile, self.project_root)
            for name, profile in local.get("profiles", {}).items()
            if isinstance(name, str) and name.strip()
        }
        local_last = str(local.get("last_profile", "") or "")

        def apply(latest):
            latest["profiles"].update(local_profiles)
            if local_last in latest["profiles"]:
                latest["last_profile"] = local_last

        self._update(apply)

    def _update(self, mutation):
        """Reload and apply one mutation while holding this store's lock."""
        with _ProfileStoreLock(self.path + ".lock"):
            latest = self._load()
            result = mutation(latest)
            self._write(latest)
            self.data = latest
            return result

    def _write(self, data):
        directory = os.path.dirname(self.path)
        if not os.path.isdir(directory):
            try:
                os.makedirs(directory)
            except OSError:
                if not os.path.isdir(directory):
                    raise
        handle, temporary = tempfile.mkstemp(
            prefix=".pokecon-studio-", suffix=".tmp", dir=directory)
        try:
            with io.open(handle, "w", encoding="utf-8", closefd=True) as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2,
                          sort_keys=True)
                stream.write("\n")
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                try:
                    os.remove(temporary)
                except OSError:
                    pass


def discover_source_files(profile):
    paths = []
    paths.extend(path for path in profile.get("source_files", [])
                 if os.path.isfile(path) and path.lower().endswith(SOURCE_SUFFIXES))
    for folder in profile.get("source_folders", []):
        if not os.path.isdir(folder):
            continue
        for directory, folder_names, filenames in os.walk(folder):
            folder_names[:] = sorted(
                name for name in folder_names
                if name not in (".git", "__pycache__", ".venv", "node_modules"))
            for filename in sorted(filenames, key=str.casefold):
                if filename.lower().endswith(SOURCE_SUFFIXES):
                    paths.append(os.path.join(directory, filename))
    return _unique_paths(paths)


def discover_image_files(profile):
    paths = []
    for folder in profile.get("image_folders", []):
        if not os.path.isdir(folder):
            continue
        for directory, folder_names, filenames in os.walk(folder):
            folder_names[:] = sorted(
                name for name in folder_names
                if name not in (".git", "__pycache__"))
            for filename in sorted(filenames, key=str.casefold):
                if filename.lower().endswith(IMAGE_SUFFIXES):
                    paths.append(os.path.join(directory, filename))
    return _unique_paths(paths)


def read_source(path):
    # ``utf-8-sig`` also accepts ordinary UTF-8, so trying it first falsely
    # reports every UTF-8 file as BOM-bearing and causes the next save to add a
    # BOM (potentially before a shebang).  Detect the marker explicitly.
    with io.open(path, "rb") as stream:
        has_utf8_bom = stream.read(3) == b"\xef\xbb\xbf"
    last_error = None
    encodings = ("utf-8-sig", "cp932") if has_utf8_bom \
        else ("utf-8", "cp932")
    for encoding in encodings:
        try:
            with io.open(path, "r", encoding=encoding, newline="") as stream:
                return stream.read(), encoding
        except UnicodeError as error:
            last_error = error
    if last_error:
        raise last_error
    raise OSError(path)


def _literal_dict(node):
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return {}
    return value if isinstance(value, dict) else {}


def _container_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


_NO_TOP_LEVEL_BINDING = object()
_NONLOCAL_TOP_LEVEL_BINDING = object()


def _target_binds_name(target, name):
    if isinstance(target, ast.Name):
        return target.id == name
    if isinstance(target, (ast.Tuple, ast.List)):
        return any(_target_binds_name(item, name) for item in target.elts)
    if isinstance(target, ast.Starred):
        return _target_binds_name(target.value, name)
    return False


def _expression_binds_name(expression, name):
    """Conservatively recognize assignment expressions at module scope."""
    named_expression = getattr(ast, "NamedExpr", ())
    if not named_expression:
        return False
    return any(
        isinstance(node, named_expression) and
        _target_binds_name(node.target, name)
        for node in ast.walk(expression)
    )


def _top_level_statement_binding(statement, name):
    """Describe whether one module statement can rebind *name*.

    A direct class definition is the only result that can safely be used as
    a local base.  Imports, assignments, functions, deletes, and conditional
    bindings deliberately become opaque.  This mirrors Python's statement
    order and prevents a class declared *after* its supposed subclass from
    being mistaken for the base that existed when the subclass was created.
    """
    if isinstance(statement, ast.ClassDef):
        return statement if statement.name == name else _NO_TOP_LEVEL_BINDING
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return (_NONLOCAL_TOP_LEVEL_BINDING if statement.name == name
                else _NO_TOP_LEVEL_BINDING)
    if isinstance(statement, ast.Import):
        for alias in statement.names:
            bound = alias.asname or alias.name.split(".", 1)[0]
            if bound == name:
                return _NONLOCAL_TOP_LEVEL_BINDING
        return _NO_TOP_LEVEL_BINDING
    if isinstance(statement, ast.ImportFrom):
        for alias in statement.names:
            if alias.name == "*" or (alias.asname or alias.name) == name:
                return _NONLOCAL_TOP_LEVEL_BINDING
        return _NO_TOP_LEVEL_BINDING
    if isinstance(statement, ast.Assign):
        if any(_target_binds_name(target, name)
               for target in statement.targets):
            return _NONLOCAL_TOP_LEVEL_BINDING
        if _expression_binds_name(statement.value, name):
            return _NONLOCAL_TOP_LEVEL_BINDING
        return _NO_TOP_LEVEL_BINDING
    if isinstance(statement, (ast.AnnAssign, ast.AugAssign)):
        if _target_binds_name(statement.target, name):
            return _NONLOCAL_TOP_LEVEL_BINDING
        value = getattr(statement, "value", None)
        if value is not None and _expression_binds_name(value, name):
            return _NONLOCAL_TOP_LEVEL_BINDING
        return _NO_TOP_LEVEL_BINDING
    if isinstance(statement, ast.Delete):
        return (_NONLOCAL_TOP_LEVEL_BINDING
                if any(_target_binds_name(target, name)
                       for target in statement.targets)
                else _NO_TOP_LEVEL_BINDING)
    if isinstance(statement, (ast.For, ast.AsyncFor)):
        if _target_binds_name(statement.target, name):
            return _NONLOCAL_TOP_LEVEL_BINDING
    if isinstance(statement, (ast.With, ast.AsyncWith)):
        if any(item.optional_vars is not None and
               _target_binds_name(item.optional_vars, name)
               for item in statement.items):
            return _NONLOCAL_TOP_LEVEL_BINDING

    child_groups = []
    for attribute in ("body", "orelse", "finalbody"):
        child_groups.extend(getattr(statement, attribute, ()) or ())
    for handler in getattr(statement, "handlers", ()) or ():
        handler_name = getattr(handler, "name", None)
        if handler_name == name or _target_binds_name(handler_name, name):
            return _NONLOCAL_TOP_LEVEL_BINDING
        child_groups.extend(getattr(handler, "body", ()) or ())
    if any(_top_level_statement_binding(child, name) is not
           _NO_TOP_LEVEL_BINDING for child in child_groups):
        return _NONLOCAL_TOP_LEVEL_BINDING

    if isinstance(statement, ast.Expr) and _expression_binds_name(
            statement.value, name):
        return _NONLOCAL_TOP_LEVEL_BINDING
    return _NO_TOP_LEVEL_BINDING


def _top_level_name_binding(tree, subclass, name):
    """Return a stable identity for *name* immediately before subclass."""
    binding = ("external-initial", str(name))
    for statement in getattr(tree, "body", ()):
        if statement is subclass:
            break
        current = _top_level_statement_binding(statement, name)
        if current is not _NO_TOP_LEVEL_BINDING:
            if isinstance(current, ast.ClassDef):
                binding = current
            else:
                binding = (
                    "external-binding", str(name),
                    int(getattr(statement, "lineno", 0) or 0),
                    int(getattr(statement, "col_offset", 0) or 0),
                    statement.__class__.__name__,
                )
    return binding


def _local_top_level_base(tree, subclass, base):
    """Resolve a bare base name to its binding immediately before subclass."""
    if not isinstance(base, ast.Name):
        return None
    binding = _top_level_name_binding(tree, subclass, base.id)
    return binding if isinstance(binding, ast.ClassDef) else None


def _source_detection_literal_maps(source):
    """Read literal IMAGE_DETECTION_* containers without normalizing them."""
    tree = ast.parse(source)
    targets, operators, descriptions = {}, {}, {}
    assignments = []
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            assignments.append(node)
        elif isinstance(node, ast.Call):
            calls.append(node)
    assignments.sort(key=lambda node: int(getattr(node, "lineno", 1)))
    for node in assignments:
        value_node = getattr(node, "value", None)
        names = []
        if isinstance(node, ast.Assign):
            names = [_container_name(target) for target in node.targets]
        else:
            names = [_container_name(node.target)]
        values = _literal_dict(value_node)
        for name in names:
            if name == "IMAGE_DETECTION_TARGETS":
                targets = values
            elif name == "IMAGE_DETECTION_OPERATORS":
                operators = values
            elif name == "IMAGE_DETECTION_DESCRIPTIONS":
                descriptions = values
    calls.sort(key=lambda node: int(getattr(node, "lineno", 1)))
    for call in calls:
        function = getattr(call, "func", None)
        if not isinstance(function, ast.Attribute) or function.attr != "update" or not call.args:
            continue
        values = _literal_dict(call.args[0])
        owner = function.value
        name = _container_name(owner)
        if name == "IMAGE_DETECTION_TARGETS":
            targets.update(values)
        elif name == "IMAGE_DETECTION_OPERATORS":
            operators.update(values)
        elif name == "IMAGE_DETECTION_DESCRIPTIONS":
            descriptions.update(values)
        elif isinstance(owner, ast.Call) and isinstance(owner.func, ast.Attribute):
            if (owner.func.attr == "setdefault" and owner.args and
                    _container_name(owner.func.value) == "IMAGE_DETECTION_DESCRIPTIONS"):
                try:
                    section = ast.literal_eval(owner.args[0])
                except (ValueError, TypeError, SyntaxError):
                    section = None
                if section == "targets":
                    descriptions.setdefault("targets", {}).update(values)
    return targets, operators, descriptions


def source_detection_settings(source):
    """Read literal IMAGE_DETECTION_* assignments and update blocks."""
    targets, operators, descriptions = _source_detection_literal_maps(source)
    result = {}
    for name, variants in targets.items():
        if not isinstance(variants, list):
            continue
        nested_descriptions = descriptions.get("targets", {})
        if isinstance(nested_descriptions, dict) and \
                str(name) in nested_descriptions:
            description = nested_descriptions.get(str(name), "")
        else:
            # Older Commands, including SSR3_Story, use a flat mapping.  Keep
            # accepting it so opening and re-saving image registrations does
            # not erase hand-maintained descriptions.
            description = descriptions.get(str(name), "")
        result[str(name)] = {
            "operator": str(operators.get(str(name), "OR")).upper(),
            "description": str(description),
            "variants": [dict(item) for item in variants
                         if isinstance(item, dict)],
        }
    return result


def source_detection_references(source):
    """Return logical image names and literal image paths used by source."""
    tree = ast.parse(source)
    names, paths = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            function_name = _container_name(node.func)
            if function_name in (
                    "image_check", "_image_check_target", "detect_image",
                    "isContainTemplate", "isContainedImage"):
                for argument in list(node.args) + [item.value for item in node.keywords]:
                    try:
                        value = ast.literal_eval(argument)
                    except (ValueError, TypeError, SyntaxError):
                        continue
                    if not isinstance(value, str):
                        continue
                    if value.lower().endswith(IMAGE_SUFFIXES):
                        paths.add(value)
                    else:
                        names.add(value)
        value = None
        if isinstance(node, getattr(ast, "Constant", ())):
            value = getattr(node, "value", None)
        elif isinstance(node, getattr(ast, "Str", ())):
            value = getattr(node, "s", None)
        if isinstance(value, str) and value.lower().endswith(IMAGE_SUFFIXES):
            paths.add(value)
    return names, paths


def _resolve_image_path(raw_path, source_path, profile, project_root):
    raw_path = str(raw_path or "").replace("/", os.sep)
    if not raw_path:
        return ""
    candidates = []
    if os.path.isabs(raw_path):
        candidates.append(raw_path)
    else:
        if source_path:
            candidates.append(os.path.join(os.path.dirname(source_path), raw_path))
        candidates.append(os.path.join(project_root, raw_path))
        serial_root = os.path.join(project_root, "SerialController")
        candidates.append(os.path.join(serial_root, raw_path))
        for root in (profile.get("image_folders", []) +
                     profile.get("source_folders", []) +
                     profile.get("include_folders", [])):
            candidates.append(os.path.join(root, raw_path))
            candidates.append(os.path.join(root, os.path.basename(raw_path)))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return os.path.abspath(candidates[0]) if candidates else raw_path


def _image_dimensions(path):
    try:
        from PIL import Image
        with Image.open(path) as image:
            return int(image.size[0]), int(image.size[1])
    except (ImportError, OSError, ValueError):
        return 0, 0


def _image_region(image, value, label):
    """Return a validated image region and its top-left offset."""
    if image is None or getattr(image, "size", 0) == 0:
        raise ValueError("{} image is empty".format(label))
    shape = getattr(image, "shape", ())
    if not isinstance(shape, tuple) or len(shape) not in (2, 3):
        raise ValueError("{} image must be a 2-D or 3-D array".format(label))
    try:
        height, width = int(shape[0]), int(shape[1])
    except (TypeError, ValueError, IndexError):
        raise ValueError("{} image dimensions are invalid".format(label))
    if height <= 0 or width <= 0:
        raise ValueError("{} image is empty".format(label))

    if value is None or (isinstance(value, (list, tuple)) and not value):
        return image, (0, 0)
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("{} must be [x1, y1, x2, y2]".format(label))
    try:
        x1, y1, x2, y2 = [int(item) for item in value]
    except (TypeError, ValueError, OverflowError):
        raise ValueError("{} must contain integer coordinates".format(label))
    if not any((x1, y1, x2, y2)):
        return image, (0, 0)

    x1 = max(0, min(width, x1))
    y1 = max(0, min(height, y1))
    x2 = width if x2 <= 0 else max(0, min(width, x2))
    y2 = height if y2 <= 0 else max(0, min(height, y2))
    if x2 <= x1 or y2 <= y1:
        raise ValueError("{} is outside the image or has no area".format(label))
    return image[y1:y2, x1:x2], (x1, y1)


def _match_plane(image, use_gray, cv2, label):
    """Validate channel layout and optionally convert an image to grayscale."""
    shape = getattr(image, "shape", ())
    if len(shape) == 2:
        return image
    channels = int(shape[2]) if len(shape) == 3 else 0
    if channels == 1:
        return image[:, :, 0]
    if channels not in (3, 4):
        raise ValueError("{} image has an unsupported channel count".format(label))
    if not use_gray:
        return image
    conversion = (cv2.COLOR_BGR2GRAY if channels == 3
                  else cv2.COLOR_BGRA2GRAY)
    return cv2.cvtColor(image, conversion)


def _exclusion_regions(value):
    if value is None or (isinstance(value, (list, tuple)) and not value):
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError("exclude_regions must be a list of rectangles")
    result = []
    for index, region in enumerate(value):
        if not isinstance(region, (list, tuple)) or len(region) != 4:
            raise ValueError(
                "exclude_regions[{}] must be [x1, y1, x2, y2]".format(index))
        try:
            x1, y1, x2, y2 = [int(item) for item in region]
        except (TypeError, ValueError, OverflowError):
            raise ValueError(
                "exclude_regions[{}] must contain integer coordinates".format(index))
        if x2 <= x1 or y2 <= y1:
            raise ValueError("exclude_regions[{}] has no area".format(index))
        result.append((x1, y1, x2, y2))
    return result


def match_detection_row(frame, template, row):
    """Match one Studio catalog row against a frame using OpenCV.

    Settings that only exist in a source variant (for example
    ``template_crop`` and ``exclude_regions``) are read from
    ``variant_settings``.  Editable values stored directly on the catalog row
    take precedence.
    """
    if not isinstance(row, dict):
        raise ValueError("detection row must be a dictionary")
    nested = row.get("variant_settings", {})
    if nested is None:
        nested = {}
    if not isinstance(nested, dict):
        raise ValueError("variant_settings must be a dictionary")
    settings = dict(nested)
    for key in ("crop", "template_crop", "exclude_regions", "use_gray",
                "threshold"):
        if key in row:
            settings[key] = row[key]

    try:
        threshold = float(settings.get("threshold", 0.8))
    except (TypeError, ValueError, OverflowError):
        raise ValueError("threshold must be a number from 0 to 1")
    if not math.isfinite(threshold) or threshold < 0.0 or threshold > 1.0:
        raise ValueError("threshold must be a finite number from 0 to 1")

    try:
        import cv2
    except ImportError:
        raise RuntimeError("OpenCV is required for image matching")

    try:
        search, offset = _image_region(
            frame, settings.get("crop", [0, 0, 0, 0]), "crop")
        target, _template_offset = _image_region(
            template, settings.get("template_crop", [0, 0, 0, 0]),
            "template_crop")
        use_gray = bool(settings.get("use_gray", True))
        search_match = _match_plane(search, use_gray, cv2, "frame")
        target_match = _match_plane(target, use_gray, cv2, "template")
        if (search_match.ndim != target_match.ndim or
                (search_match.ndim == 3 and
                 search_match.shape[2] != target_match.shape[2])):
            raise ValueError("frame and template channel layouts do not match")
        template_height, template_width = target_match.shape[:2]
        if (search_match.shape[0] < template_height or
                search_match.shape[1] < template_width):
            raise ValueError("crop is smaller than the cropped template")

        response = cv2.matchTemplate(
            search_match, target_match, cv2.TM_CCOEFF_NORMED)
        exclusions = _exclusion_regions(settings.get("exclude_regions", []))
        if exclusions:
            response = response.copy()
            response_height, response_width = response.shape[:2]
            for x1, y1, x2, y2 in exclusions:
                # Each response position is a template's top-left corner.
                # Suppress any placement whose rectangle overlaps an excluded
                # screen region, including placements crossing its border.
                left = max(0, x1 - offset[0] - template_width + 1)
                right = min(response_width, x2 - offset[0])
                top = max(0, y1 - offset[1] - template_height + 1)
                bottom = min(response_height, y2 - offset[1])
                if left < right and top < bottom:
                    response[top:bottom, left:right] = -2.0
        _minimum, score, _minimum_location, location = cv2.minMaxLoc(response)
    except ValueError:
        raise
    except (AttributeError, TypeError, IndexError, OverflowError) as error:
        raise ValueError("invalid image matching input: {}".format(error))
    except cv2.error as error:
        raise ValueError("OpenCV could not match the images: {}".format(error))

    if not math.isfinite(score):
        raise ValueError("image similarity could not be calculated")
    position = (int(location[0]) + int(offset[0]),
                int(location[1]) + int(offset[1]))
    return {
        "score": float(score),
        "matched": float(score) >= threshold,
        "position": position,
        "template_size": (int(template_width), int(template_height)),
    }


def _detection_id(name, path, variant_index, signature=""):
    value = "{}\0{}\0{}\0{}".format(
        name, os.path.normcase(path), variant_index, signature)
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def build_detection_catalog(profile, source_paths, project_root,
                            cancel_event=None, source_overrides=None):
    """Build one row per template, marking rows referenced by source."""
    if cancel_event is not None and cancel_event.is_set():
        return []
    rows = []
    by_path = {}
    by_id = {}
    logical_references, path_references = set(), set()
    settings_by_source = []
    overrides = {}
    for path, source in (source_overrides or {}).items():
        if not path or not isinstance(source, str):
            continue
        overrides[os.path.normcase(os.path.abspath(path))] = source
    for source_path in source_paths:
        if cancel_event is not None and cancel_event.is_set():
            return []
        try:
            key = os.path.normcase(os.path.abspath(source_path))
            if key in overrides:
                source = overrides[key]
            else:
                source, _encoding = read_source(source_path)
            settings = source_detection_settings(source)
            names, paths = source_detection_references(source)
        except (OSError, UnicodeError, SyntaxError):
            continue
        settings_by_source.append((source_path, settings))
        logical_references.update(names)
        for path in paths:
            resolved = _resolve_image_path(path, source_path, profile, project_root)
            path_references.add(os.path.normcase(resolved))
            path_references.add(os.path.normcase(os.path.basename(path)))

    for image_path in discover_image_files(profile):
        if cancel_event is not None and cancel_event.is_set():
            return []
        width, height = _image_dimensions(image_path)
        relative_name = None
        for folder in profile.get("image_folders", []):
            try:
                relative = os.path.relpath(image_path, folder)
            except ValueError:
                continue
            if not relative.startswith(".." + os.sep) and relative != "..":
                relative_name = os.path.splitext(relative)[0].replace(os.sep, "/")
                break
        name = relative_name or os.path.splitext(os.path.basename(image_path))[0]
        row = {
            "id": _detection_id(name, image_path, 0, "raw"),
            "name": name,
            "template_path": image_path,
            "threshold": 0.8,
            "crop": [0, 0, 0, 0],
            "use_gray": True,
            "description": "",
            "operator": "OR",
            "variant_index": 0,
            "template_width": width,
            "template_height": height,
            # Zero explicitly means the whole current frame.  The live frame
            # width is not assumed to be 1280 for offline profiles.
            "detection_width": 0,
            "variant_settings": {
                "template_path": image_path, "threshold": 0.8,
                "crop": [0, 0, 0, 0], "use_gray": True,
            },
            "source_defined": False,
            "source_paths": [],
            "score": None,
            "matched": False,
        }
        rows.append(row)
        by_path.setdefault(os.path.normcase(image_path), []).append(row)
        by_id[row["id"]] = row

    for source_path, settings in settings_by_source:
        if cancel_event is not None and cancel_event.is_set():
            return []
        for name, target in settings.items():
            if cancel_event is not None and cancel_event.is_set():
                return []
            for index, variant in enumerate(target.get("variants", [])):
                if cancel_event is not None and cancel_event.is_set():
                    return []
                image_path = _resolve_image_path(
                    variant.get("template_path", ""), source_path,
                    profile, project_root)
                signature = json.dumps(
                    variant, ensure_ascii=False, sort_keys=True,
                    separators=(",", ":"), default=str)
                row_id = _detection_id(name, image_path, index, signature)
                row = by_id.get(row_id)
                existing = by_path.get(os.path.normcase(image_path), [])
                if row is None and index == 0:
                    row = next((item for item in existing
                                if not item.get("source_defined")), None)
                    if row is not None:
                        by_id.pop(row["id"], None)
                        row["id"] = row_id
                        by_id[row_id] = row
                if row is None:
                    width, height = _image_dimensions(image_path)
                    row = {
                        "id": row_id,
                        "name": name,
                        "template_path": image_path,
                        "template_width": width,
                        "template_height": height,
                        "score": None,
                        "matched": False,
                    }
                    rows.append(row)
                    by_path.setdefault(os.path.normcase(image_path), []).append(row)
                    by_id[row_id] = row
                crop = variant.get("crop", [0, 0, 0, 0])
                if not isinstance(crop, (list, tuple)) or len(crop) != 4:
                    crop = [0, 0, 0, 0]
                try:
                    crop = [int(value) for value in crop]
                except (TypeError, ValueError):
                    crop = [0, 0, 0, 0]
                detection_width = (crop[2] - crop[0]) if crop[2] > crop[0] else 0
                row.update({
                    "id": row_id,
                    "name": name,
                    "template_path": image_path,
                    "threshold": float(variant.get("threshold", 0.8)),
                    "crop": crop,
                    "use_gray": bool(variant.get("use_gray", True)),
                    "description": target.get("description", ""),
                    "operator": target.get("operator", "OR"),
                    "variant_index": index,
                    "detection_width": int(detection_width or 0),
                    "variant_settings": dict(variant),
                    "source_defined": True,
                    "source_paths": sorted(set(
                        row.get("source_paths", []) + [source_path]),
                        key=str.casefold),
                })

    for row in rows:
        if cancel_event is not None and cancel_event.is_set():
            return []
        path_key = os.path.normcase(row["template_path"])
        basename_key = os.path.normcase(os.path.basename(row["template_path"]))
        if (row["name"] in logical_references or path_key in path_references or
                basename_key in path_references):
            row["source_defined"] = True
    return sorted(rows, key=detection_sort_key)


def detection_sort_key(row):
    score = row.get("score")
    try:
        score_value = float(score) if score is not None else -1.0
    except (TypeError, ValueError):
        score_value = -1.0
    try:
        threshold = float(row.get("threshold", 0.0))
    except (TypeError, ValueError):
        threshold = 0.0
    try:
        width = int(row.get("detection_width", 0))
    except (TypeError, ValueError):
        width = 0
    # Zero is the full frame and therefore the widest search area.
    width_order = 1000000000 if width <= 0 else width
    return (-score_value, -threshold, -width_order,
            str(row.get("name", "")).casefold())


def _assignment_nodes(tree, name):
    result = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if any(_container_name(target) == name for target in node.targets):
                result.append(node)
        elif isinstance(node, ast.AnnAssign) and _container_name(node.target) == name:
            result.append(node)
    return sorted(result, key=lambda node: int(getattr(node, "lineno", 1)))


def _direct_assignment_nodes(container, name):
    """Return assignments made directly in a module or class body."""
    result = []
    for node in getattr(container, "body", ()):
        if isinstance(node, ast.Assign):
            if any(_container_name(target) == name for target in node.targets):
                result.append(node)
        elif (isinstance(node, ast.AnnAssign) and
              _container_name(node.target) == name):
            result.append(node)
    return result


def _is_pokecon_command_marker(name):
    """Recognize the public PokeCon command base class names."""
    return name == "Command" or str(name).endswith("PythonCommand")


def _pokecon_command_class(tree):
    """Find the most-derived top-level PokeCon command class in *tree*.

    Source files may define helpers before their command. Resolve local base
    classes transitively and anchor the search at Command, PythonCommand, and
    bases such as ImageProcPythonCommand instead of relying on source order.
    """
    classes = [node for node in getattr(tree, "body", ())
               if isinstance(node, ast.ClassDef)]
    memo = {}

    def ancestry_depth(node, visiting):
        if node in memo:
            return memo[node]
        if node in visiting:
            return None
        visiting = set(visiting)
        visiting.add(node)
        best = 0 if _is_pokecon_command_marker(node.name) else None
        for base in node.bases:
            base_name = _container_name(base)
            if _is_pokecon_command_marker(base_name):
                depth = 1
            else:
                local_base = _local_top_level_base(tree, node, base)
                parent_depth = (ancestry_depth(local_base, visiting)
                                if local_base is not None else None)
                depth = None if parent_depth is None else parent_depth + 1
            if depth is not None and (best is None or depth > best):
                best = depth
        memo[node] = best
        return best

    candidates = []
    for index, node in enumerate(classes):
        depth = ancestry_depth(node, set())
        if depth is not None:
            candidates.append((depth, index, node))
    if not candidates:
        return None
    # Prefer a transitive leaf over an intermediate local command base. The
    # later declaration wins only when unrelated candidates are equally deep.
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def _statement_end_line(source, start_line):
    """Find a statement end even on Python AST versions without end_lineno."""
    reader = io.StringIO(source).readline
    depth = 0
    seen_assignment = False
    last_line = int(start_line)
    try:
        for token in tokenize.generate_tokens(reader):
            if token.start[0] < start_line:
                continue
            last_line = max(last_line, token.end[0])
            if token.type == tokenize.OP:
                if token.string in "([{":
                    depth += 1
                elif token.string in ")]}":
                    depth = max(0, depth - 1)
                elif token.string == "=":
                    seen_assignment = True
            if seen_assignment and depth == 0 and token.type in (
                    tokenize.NEWLINE, tokenize.ENDMARKER):
                return token.end[0]
    except (tokenize.TokenError, IndentationError):
        pass
    return last_line


def _replace_assignment(source, node, name, value):
    lines = source.splitlines(True)
    start = int(getattr(node, "lineno", 1)) - 1
    end_line = int(getattr(node, "end_lineno", 0) or 0)
    if not end_line:
        end_line = _statement_end_line(source, start + 1)
    original = lines[start] if 0 <= start < len(lines) else ""
    indent = original[:len(original) - len(original.lstrip(" \t"))]
    formatted = pprint.pformat(value, width=100)
    replacement = indent + name + " = " + formatted + "\n"
    lines[start:end_line] = [replacement]
    return "".join(lines)


def _variant_from_row(row, project_root):
    path = os.path.abspath(row["template_path"])
    serial_root = os.path.join(os.path.abspath(project_root), "SerialController")
    try:
        relative = os.path.relpath(path, serial_root)
    except ValueError:
        relative = path
    template_path = (relative.replace(os.sep, "/")
                     if not relative.startswith("../") and relative != ".."
                     else path.replace(os.sep, "/"))
    existing = row.get("variant_settings", {})
    variant = dict(existing) if isinstance(existing, dict) else {}
    # Keep advanced source-only settings (template_crop, exclude_regions,
    # display options, etc.) when a catalog row is re-registered, while the
    # fields editable in Studio take their current row values.
    variant.update({
        "template_path": template_path,
        "threshold": float(row.get("threshold", 0.8)),
        "use_gray": bool(row.get("use_gray", True)),
        "crop": list(row.get("crop", [0, 0, 0, 0])),
    })
    variant.setdefault("show_value", True)
    variant.setdefault("show_position", True)
    variant.setdefault("show_only_true_rect", False)
    variant.setdefault("ms", 2000)
    variant.setdefault("match_color", "blue")
    variant.setdefault("no_match_color", "red")
    return variant


def _variant_identity(variant, project_root=None):
    """Identify one matching geometry while allowing its options to update."""
    value = variant if isinstance(variant, dict) else {}
    template_path = str(value.get("template_path", "")).replace("/", os.sep)
    if project_root and template_path and not os.path.isabs(template_path):
        template_path = os.path.join(
            os.path.abspath(project_root), "SerialController", template_path)
    template_path = os.path.normcase(os.path.abspath(template_path)) \
        if template_path else ""

    def stable(item):
        return json.dumps(
            item, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), default=str)

    return (
        template_path,
        bool(value.get("use_gray", True)),
        stable(value.get("crop", [0, 0, 0, 0])),
        stable(value.get("template_crop", [0, 0, 0, 0])),
        stable(value.get("exclude_regions", [])),
    )


def add_detection_to_source(source, row, project_root):
    """Merge one selected detection registration without executing source."""
    tree = ast.parse(source)
    command_class = _pokecon_command_class(tree)
    name = str(row.get("name") or os.path.splitext(
        os.path.basename(row["template_path"]))[0])
    settings = source_detection_settings(source)
    target = settings.setdefault(name, {
        "operator": str(row.get("operator", "OR") or "OR").upper(),
        "description": str(row.get("description", "") or ""),
        "variants": [],
    })
    variant = _variant_from_row(row, project_root)

    variant_identity = _variant_identity(variant, project_root)
    if row.get("replace_template_path_variants"):
        # A recording-frame recapture overwrites the PNG itself.  Keeping an
        # older crop for that same file would point a now differently-sized
        # template at stale geometry and can make runtime matching fail.
        target["variants"] = [
            current for current in target["variants"]
            if _variant_identity(current, project_root)[0] !=
            variant_identity[0]
        ]
    already_registered = False
    for index, current in enumerate(target["variants"]):
        if _variant_identity(current, project_root) == variant_identity:
            # Keep the old same-variant update behavior (for example a newly
            # tuned threshold), while distinct crops/templates remain siblings.
            target["variants"][index] = variant
            already_registered = True
            break
    if not already_registered:
        target["variants"].append(variant)

    # The generated-code merge helper replaces all variants for one logical
    # target.  Pass the complete accumulated list, not only the latest row, so
    # sequential additions from a multi-selection cannot discard siblings.
    library = {
        "schema_version": 1,
        "targets": {name: {
            "operator": str(target.get("operator", "OR") or "OR").upper(),
            "description": str(target.get("description", "") or ""),
            "tags": ["PokeConStudio"],
            "variants": [dict(item) for item in target["variants"]],
        }},
        "lists": {"PokeConStudioSelection": {
            "description": "PokeConStudio selection",
            "members": [{"type": "target", "id": name}],
        }},
    }
    devstudio_root = os.path.join(os.path.abspath(project_root), "DevStudio")
    if os.path.isdir(devstudio_root) and devstudio_root not in sys.path:
        sys.path.insert(0, devstudio_root)
    if "# POKECON_IMAGE_CHECK_BEGIN" in source:
        try:
            from ImageCheckReferenceAudit import merge_library_targets_into_source
            updated, _added = merge_library_targets_into_source(
                source, library, [name])
            ast.parse(updated)
            return updated, name
        except ImportError:
            # Portable copies can still use the literal-assignment fallback.
            pass

    targets = {item_name: item["variants"] for item_name, item in settings.items()}
    operators = {item_name: item.get("operator", "OR")
                 for item_name, item in settings.items()}
    _old_targets, _old_operators, old_descriptions = \
        _source_detection_literal_maps(source)
    descriptions = dict(old_descriptions)
    nested_descriptions = descriptions.get("targets")
    if isinstance(nested_descriptions, dict):
        nested_descriptions = dict(nested_descriptions)
        nested_descriptions.update({
            item_name: item.get("description", "")
            for item_name, item in settings.items()
        })
        descriptions["targets"] = nested_descriptions
    else:
        # Preserve a legacy flat dictionary (and manual description-only keys)
        # in its original shape instead of replacing it with {"targets": ...}.
        descriptions.update({
            item_name: item.get("description", "")
            for item_name, item in settings.items()
        })
    class_target_nodes = (_direct_assignment_nodes(
        command_class, "IMAGE_DETECTION_TARGETS") if command_class else [])
    module_target_nodes = _direct_assignment_nodes(
        tree, "IMAGE_DETECTION_TARGETS")
    assignments_in_command = bool(class_target_nodes)
    target_nodes = class_target_nodes or module_target_nodes
    updated = source
    # Replace bottom-up by reparsing before every assignment.  Line counts can
    # change when pprint expands a dictionary, so stale AST locations are not
    # reused across replacements.
    for variable, value in (
            ("IMAGE_DETECTION_DESCRIPTIONS", descriptions),
            ("IMAGE_DETECTION_OPERATORS", operators),
            ("IMAGE_DETECTION_TARGETS", targets)):
        reparsed = ast.parse(updated)
        if assignments_in_command:
            container = _pokecon_command_class(reparsed)
        else:
            container = reparsed
        nodes = (_direct_assignment_nodes(container, variable)
                 if container is not None else [])
        if nodes:
            updated = _replace_assignment(updated, nodes[-1], variable, value)

    if target_nodes:
        return updated, name

    # A new PokeCon Commands class needs the matching helper methods as well
    # as the target dictionary.  Reuse DevStudio's canonical generator so the
    # source added here behaves exactly like registrations added there.
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    if command_class is not None:
        try:
            from ImageDetectionLibrary import generate_image_check
            generated = generate_image_check(
                library, "PokeConStudioSelection", "list")
            import_line = (
                "from LocalFunction.ImageDetection import "
                "SimilarityHistory, detect_image")
            with_import = source
            if import_line not in with_import:
                class_line = int(classes[0].lineno) - 1
                source_lines = with_import.splitlines(True)
                source_lines[class_line:class_line] = [import_line + "\n\n"]
                with_import = "".join(source_lines)
            reparsed = ast.parse(with_import)
            reparsed_command = _pokecon_command_class(reparsed)
            if reparsed_command is None:
                raise ValueError("PokeCon command class could not be resolved")
            insert_line = int(reparsed_command.body[0].lineno) - 1
            first_body = reparsed_command.body[0]
            if (isinstance(first_body, ast.Expr) and
                    isinstance(getattr(first_body, "value", None),
                               (getattr(ast, "Str", ()),
                                getattr(ast, "Constant", ()))) and
                    isinstance(getattr(first_body.value, "s",
                                       getattr(first_body.value, "value", None)), str)):
                insert_line = int(getattr(first_body, "end_lineno", 0) or
                                  first_body.lineno)
            indentation = " " * (int(reparsed_command.col_offset) + 4)
            block = "\n".join(
                indentation + line if line else ""
                for line in generated.rstrip().splitlines()) + "\n\n"
            source_lines = with_import.splitlines(True)
            source_lines[insert_line:insert_line] = [block]
            updated = "".join(source_lines)
            ast.parse(updated)
            return updated, name
        except ImportError:
            pass

    block = "\n".join([
        MANAGED_BEGIN,
        "# PokeConStudioから追加。エディタで修正しても再読込できます。",
        "IMAGE_DETECTION_TARGETS = " + pprint.pformat(targets, width=100),
        "IMAGE_DETECTION_OPERATORS = " + pprint.pformat(operators, width=100),
        "IMAGE_DETECTION_DESCRIPTIONS = " + pprint.pformat(descriptions, width=100),
        MANAGED_END,
    ])
    if command_class is not None and command_class.body:
        first_body_line = int(command_class.body[0].lineno) - 1
        lines = source.splitlines(True)
        indent = " " * (int(getattr(command_class, "col_offset", 0)) + 4)
        indented = "\n".join(indent + line if line else ""
                             for line in block.splitlines()) + "\n\n"
        lines[first_body_line:first_body_line] = [indented]
        updated = "".join(lines)
    else:
        updated = source.rstrip() + "\n\n" + block + "\n"
    ast.parse(updated)
    return updated, name


def operation_call_lines(source, patterns=None):
    """Return source lines that execute controller-like operation calls."""
    tree = ast.parse(source)
    compiled = []
    for pattern in patterns or DEFAULT_OPERATION_PATTERNS:
        try:
            compiled.append(re.compile(str(pattern), re.IGNORECASE))
        except re.error:
            continue
    lines = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _container_name(node.func)
        qualified = name
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            qualified = node.func.value.id + "." + name
        if any(regex.search(name) or regex.search(qualified)
               for regex in compiled):
            lines.add(int(getattr(node, "lineno", 1)))
    return sorted(lines)
