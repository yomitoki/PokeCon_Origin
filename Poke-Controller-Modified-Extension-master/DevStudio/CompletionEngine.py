#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lightweight completion data provider used by PokeCon DevStudio.

The class deliberately has no GUI dependency.  Expensive project files are
re-read only when their metadata changes; source-local names are extracted by
small regular expressions so this module can safely be called while typing.
"""
from __future__ import annotations

import builtins
import json
import keyword
import os
import re


_IDENTIFIER_RE = re.compile(r"[A-Za-z_]\w*")
_TOKEN_AT_END_RE = re.compile(r"[A-Za-z_]\w*$")
_SOURCE_NAMES_RE = re.compile(
    r"(?m)^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)|"
    r"(?m)^\s*([A-Za-z_]\w*)\s*(?::[^=\n]+)?=|"
    r"\bself\.([A-Za-z_]\w*)"
)
_METHOD_START_RE = re.compile(r"^ {4}def\s+([A-Za-z_]\w*)\s*(.*)$")


class CompletionEngine:
    """Build and filter completion candidates for the current source."""

    IMAGE_TARGET_FUNCTIONS = ("image_check",)
    IMAGE_SHORT_PATH_FUNCTIONS = (
        "isContainTemplate", "isContainTemplate_max", "image_detection_scale15"
    )
    IMAGE_RAW_PATH_FUNCTIONS = ("detect_image",)

    def __init__(self, root_dir_getter):
        self._root_dir_getter = root_dir_getter
        self._image_stamp = None
        self._image_candidates = {"target": [], "short_path": [], "raw_path": []}
        self._api_stamp = None
        self._api_candidates = []
        self._language_candidates = self._make_language_candidates()

    @staticmethod
    def _candidate(label, insert=None, kind="name", detail="", tags=None,
                   target_name=""):
        return {
            "label": str(label),
            "insert": str(label if insert is None else insert),
            "kind": str(kind),
            "detail": str(detail or ""),
            "tags": list(tags or []),
            "target_name": str(target_name or ""),
        }

    def _root(self):
        try:
            value = self._root_dir_getter() if callable(self._root_dir_getter) else self._root_dir_getter
        except Exception:
            value = ""
        return os.path.abspath(os.fspath(value)) if value else ""

    def _find_file(self, relative_candidates):
        root = self._root()
        for relative in relative_candidates:
            path = os.path.join(root, *relative)
            if os.path.isfile(path):
                return path
        return ""

    @staticmethod
    def _stamp(path, include_size=False):
        try:
            stat = os.stat(path)
            return (path, stat.st_mtime_ns, stat.st_size) if include_size else (path, stat.st_mtime_ns)
        except OSError:
            return (path, None, None) if include_size else (path, None)

    def _make_language_candidates(self):
        result = []
        for name in keyword.kwlist:
            result.append(self._candidate(name, kind="keyword", detail="Python keyword"))
        for name in dir(builtins):
            if not name.startswith("_"):
                result.append(self._candidate(name, kind="builtin", detail="Python built-in"))
        return result

    def _load_api_candidates(self):
        path = self._find_file((
            ("SerialController", "Commands", "PythonCommandBase.py"),
            ("Commands", "PythonCommandBase.py"),
        ))
        stamp = self._stamp(path)
        if stamp == self._api_stamp:
            return self._api_candidates
        candidates = []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as stream:
                source = stream.read()
            lines = source.splitlines()
            index = 0
            while index < len(lines):
                match = _METHOD_START_RE.match(lines[index])
                index += 1
                if not match:
                    continue
                name, tail = match.group(1), match.group(2)
                signature_parts = [tail]
                balance = tail.count("(") - tail.count(")")
                # Signatures in this base file are short; the bound also
                # protects typing latency if the file is temporarily invalid.
                consumed = 0
                while balance > 0 and index < len(lines) and consumed < 50:
                    part = lines[index].strip()
                    signature_parts.append(part)
                    balance += part.count("(") - part.count(")")
                    index += 1
                    consumed += 1
                signature_text = " ".join(signature_parts)
                left = signature_text.find("(")
                right = signature_text.rfind(")")
                signature = signature_text[left:right + 1] if left >= 0 and right >= left else "()"
                signature = re.sub(r"\s+", " ", signature).strip()
                if name.startswith("_") and name != "__init__":
                    continue
                candidates.append(self._candidate(
                    name, kind="PokeCon API", detail=name + signature,
                    tags=["PokeCon", "API"]
                ))
        except OSError:
            candidates = []
        self._api_stamp = stamp
        self._api_candidates = candidates
        return candidates

    @staticmethod
    def _strip_template_prefix(path):
        normalized = str(path).replace("\\", "/")
        return normalized[len("Template/"):] if normalized.lower().startswith("template/") else normalized

    def _load_image_candidates(self):
        path = self._find_file((
            ("SerialController", "Template", "image_detection_profiles.json"),
            ("Template", "image_detection_profiles.json"),
        ))
        # Both fields are used because rapid atomic rewrites can retain an mtime.
        stamp = self._stamp(path, include_size=True)
        if stamp == self._image_stamp:
            return self._image_candidates

        grouped = {"target": [], "short_path": [], "raw_path": []}
        try:
            with open(path, "r", encoding="utf-8") as stream:
                data = json.load(stream)
            targets = data.get("targets", {}) if isinstance(data, dict) else {}
            if isinstance(targets, dict):
                for target_name, value in targets.items():
                    if not isinstance(value, dict):
                        continue
                    tags = [str(tag) for tag in value.get("tags", []) if str(tag).strip()]
                    description = str(value.get("description", ""))
                    operator = str(value.get("operator", "OR")).upper()
                    detail = "{} / {}".format(operator, description).rstrip(" / ")
                    grouped["target"].append(self._candidate(
                        target_name, kind="image target", detail=detail, tags=tags,
                        target_name=target_name
                    ))
                    variants = value.get("variants", [])
                    for variant in variants if isinstance(variants, list) else []:
                        if not isinstance(variant, dict):
                            continue
                        image_path = variant.get("template_path") or variant.get("path")
                        if not image_path:
                            continue
                        raw_path = str(image_path).replace("\\", "/")
                        variant_detail = "{} / threshold {}".format(
                            target_name, variant.get("threshold", "-")
                        )
                        common = dict(kind="image path", detail=variant_detail,
                                      tags=tags, target_name=target_name)
                        grouped["raw_path"].append(self._candidate(raw_path, **common))
                        short_path = self._strip_template_prefix(raw_path)
                        grouped["short_path"].append(self._candidate(short_path, **common))
            lists = data.get("lists", {}) if isinstance(data, dict) else {}
            if isinstance(lists, dict):
                for list_name, value in lists.items():
                    detail = str(value.get("description", "")) if isinstance(value, dict) else ""
                    grouped["target"].append(self._candidate(
                        list_name, kind="image list", detail=detail,
                        tags=["list"], target_name=list_name
                    ))
        except (OSError, ValueError, TypeError):
            grouped = {"target": [], "short_path": [], "raw_path": []}

        # Keep deterministic order and avoid duplicate paths shared by targets.
        for group_name, values in grouped.items():
            unique = {}
            for item in values:
                key = (item["insert"], item["target_name"] if group_name == "target" else "")
                unique.setdefault(key, item)
            grouped[group_name] = sorted(unique.values(), key=lambda item: item["label"].lower())
        self._image_stamp = stamp
        self._image_candidates = grouped
        return grouped

    @staticmethod
    def _source_candidates(source):
        names = set()
        for match in _SOURCE_NAMES_RE.finditer(source):
            names.update(value for value in match.groups() if value)
        return [CompletionEngine._candidate(
            name, kind="source", detail="Current source identifier"
        ) for name in sorted(names, key=str.lower)]

    @staticmethod
    def _open_string(source_before_cursor):
        """Return (quote-content start, content) for a simple open string."""
        # Limit scanning to the current logical neighbourhood.  This avoids a
        # quote in a large comment or previous function influencing completion.
        floor = max(0, len(source_before_cursor) - 3000)
        text = source_before_cursor[floor:]
        quote_start = None
        quote_char = None
        escaped = False
        for index, char in enumerate(text):
            if quote_char is None:
                if char in ("'", '"'):
                    quote_start, quote_char = index, char
            elif escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote_char:
                quote_start = quote_char = None
        if quote_start is None:
            return None
        absolute = floor + quote_start + 1
        return absolute, source_before_cursor[absolute:]

    def _context_details(self, source_before_cursor):
        """Return completion context and replacement prefix information."""
        opened = self._open_string(source_before_cursor)
        if opened is not None:
            replace_start, prefix = opened
            before_quote = source_before_cursor[max(0, replace_start - 1000):replace_start - 1]
            # Named arguments override the surrounding function call.
            named = re.search(r"(?:^|[,\(])\s*(template_path(?:_list)?|detect_image)\s*=\s*$", before_quote)
            if named:
                return "raw_path", prefix, replace_start
            call_names = re.findall(r"([A-Za-z_]\w*)\s*\(", before_quote)
            function = call_names[-1] if call_names else ""
            if function in self.IMAGE_TARGET_FUNCTIONS:
                return "image_target", prefix, replace_start
            if function in self.IMAGE_SHORT_PATH_FUNCTIONS:
                return "short_path", prefix, replace_start
            if function in self.IMAGE_RAW_PATH_FUNCTIONS:
                return "raw_path", prefix, replace_start
        token = _TOKEN_AT_END_RE.search(source_before_cursor)
        prefix = token.group(0) if token else ""
        return "normal", prefix, len(source_before_cursor) - len(prefix)

    def context(self, source_before_cursor):
        """Return ``image_target``, ``short_path``, ``raw_path`` or ``normal``."""
        return self._context_details(source_before_cursor)[0]

    @staticmethod
    def _matches(candidate, query, tag):
        query_lower = query.casefold()
        searchable = " ".join((candidate["label"], candidate["insert"],
                               candidate["detail"], candidate["target_name"])).casefold()
        if query_lower and query_lower not in searchable:
            return False
        if tag:
            tag_lower = tag.casefold()
            if not any(tag_lower in value.casefold() for value in candidate["tags"]):
                return False
        return True

    @staticmethod
    def _rank(candidate, query):
        needle = query.casefold()
        label = candidate["label"].casefold()
        if not needle:
            return (0, label)
        if label == needle:
            return (0, label)
        if label.startswith(needle):
            return (1, label)
        if needle in label:
            return (2, label)
        return (3, label)

    def analyze(self, source, cursor_offset=None):
        """Analyze the cursor and return context/prefix/replacement offsets."""
        source = source or ""
        cursor = len(source) if cursor_offset is None else max(0, min(len(source), int(cursor_offset)))
        context, prefix, replace_start = self._context_details(source[:cursor])
        return {
            "context": context,
            "prefix": prefix,
            "replace_start": replace_start,
            "replace_length": cursor - replace_start,
            "cursor_offset": cursor,
        }

    def suggest(self, source, cursor_offset, query="", tag="", limit=100):
        """Return completion metadata and at most ``limit`` candidate dicts."""
        analysis = self.analyze(source, cursor_offset)
        context = analysis["context"]
        images = self._load_image_candidates()
        if context == "image_target":
            candidates = list(images["target"])
        elif context == "short_path":
            candidates = list(images["short_path"])
        elif context == "raw_path":
            candidates = list(images["raw_path"])
        else:
            candidates = (list(self._language_candidates) + self._load_api_candidates()
                          + self._source_candidates(source or ""))

            # The dedicated right-hand search can look up image targets even
            # when the caret is not currently inside image_check(...).  Insert
            # a usable statement/expression there; in-string completion above
            # continues to insert only the target name.
            if str(query).strip() or str(tag).strip():
                for target in images["target"]:
                    snippet = dict(target)
                    snippet["label"] = target["target_name"] or target["label"]
                    snippet["insert"] = 'self.image_check("{}")'.format(
                        target["target_name"] or target["insert"]
                    )
                    snippet["kind"] = "image check"
                    candidates.append(snippet)

        explicit_query = str(query).strip()
        tag = str(tag).strip()
        # A tag-only request comes from the dedicated search panel and must
        # not accidentally inherit the token currently under the editor caret.
        needle = explicit_query if (explicit_query or tag) else analysis["prefix"]
        candidates = [item for item in candidates if self._matches(item, needle, tag)]
        candidates.sort(key=lambda item: self._rank(item, needle))
        try:
            maximum = max(0, min(100, int(limit)))
        except (TypeError, ValueError):
            maximum = 100
        result = dict(analysis)
        result["candidates"] = candidates[:maximum]
        return result

    def image_tags(self):
        """Return cached image-library tags for the completion filter UI."""
        images = self._load_image_candidates()
        return sorted({tag for item in images["target"] for tag in item.get("tags", [])},
                      key=str.casefold)
