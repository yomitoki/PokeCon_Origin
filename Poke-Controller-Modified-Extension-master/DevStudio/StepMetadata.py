#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read and update user-facing Step names and descriptions in Commands."""
from __future__ import print_function

import ast


LABEL_NAMES = (
    "STEP_DISPLAY_NAMES", "RUN_LOCATION_LABELS", "COMMAND_STEP_LABELS")
DESCRIPTION_NAMES = (
    "STEP_DESCRIPTIONS", "RUN_LOCATION_DESCRIPTIONS",
    "COMMAND_STEP_DESCRIPTIONS")
CANONICAL_LABEL_NAME = "COMMAND_STEP_LABELS"
CANONICAL_DESCRIPTION_NAME = "COMMAND_STEP_DESCRIPTIONS"


def _assigned_name(statement):
    targets = (statement.targets if isinstance(statement, ast.Assign)
               else [statement.target] if isinstance(statement, ast.AnnAssign)
               else [])
    for target in targets:
        if isinstance(target, ast.Name):
            return target.id
    return ""


def _command_class(tree, class_name=""):
    command = next((node for node in tree.body
                    if isinstance(node, ast.ClassDef)
                    and (not class_name or node.name == class_name)), None)
    if command is None:
        raise ValueError("Commandsクラスがありません。")
    return command


def _literal_mapping(command, names):
    result = {}
    for wanted in names:
        for statement in command.body:
            if _assigned_name(statement) != wanted:
                continue
            try:
                value = ast.literal_eval(statement.value)
            except (ValueError, TypeError):
                value = {}
            if isinstance(value, dict):
                result.update({str(key): str(item)
                               for key, item in value.items()
                               if str(key) and str(item).strip()})
    return result


def read_step_metadata(source, class_name=""):
    """Return display-name and description maps from one command class."""
    tree = ast.parse(source)
    commands = ([_command_class(tree, class_name)] if class_name else
                [node for node in tree.body if isinstance(node, ast.ClassDef)])
    if not commands:
        raise ValueError("Commandsクラスがありません。")
    labels, descriptions = {}, {}
    for command in commands:
        labels.update(_literal_mapping(command, LABEL_NAMES))
        descriptions.update(_literal_mapping(command, DESCRIPTION_NAMES))
    return {
        "labels": labels,
        "descriptions": descriptions,
    }


def _mapping_block(indent, name, mapping, newline):
    if not mapping:
        return []
    lines = ["{}{} = {{{}".format(indent, name, newline)]
    for key, value in mapping.items():
        lines.append("{}    {!r}: {!r},{}".format(
            indent, str(key), str(value), newline))
    lines.append("{}}}{}".format(indent, newline))
    return lines


def _replace_assignment(source, class_name, assignment_name, mapping):
    tree = ast.parse(source)
    command = _command_class(tree, class_name)
    statement = next((item for item in command.body
                      if _assigned_name(item) == assignment_name), None)
    if statement is None:
        return source, False
    newline = "\r\n" if "\r\n" in source else "\n"
    lines = source.splitlines(True)
    indent = " " * (command.col_offset + 4)
    start = statement.lineno - 1
    end = int(getattr(statement, "end_lineno", statement.lineno))
    lines[start:end] = _mapping_block(
        indent, assignment_name, mapping, newline)
    return "".join(lines), True


def _metadata_insert_line(command):
    preferred = ("COMMAND_RUN_SETTINGS", "TAGS", "NAME")
    for name in preferred:
        statement = next((item for item in command.body
                          if _assigned_name(item) == name), None)
        if statement is not None:
            return int(getattr(statement, "end_lineno", statement.lineno))
    if command.body and isinstance(command.body[0], ast.Expr):
        value = command.body[0].value
        if isinstance(value, (ast.Str, ast.Constant)) and \
                isinstance(getattr(value, "s", getattr(value, "value", None)), str):
            return int(getattr(command.body[0], "end_lineno",
                               command.body[0].lineno))
    return command.lineno


def update_step_metadata(source, labels=None, descriptions=None,
                         class_name=""):
    """Upsert canonical Step metadata without reformatting the whole source."""
    labels = {str(key): str(value).strip()
              for key, value in (labels or {}).items()
              if str(key) and str(value).strip()
              and str(key) != str(value).strip()}
    descriptions = {str(key): str(value).strip()
                    for key, value in (descriptions or {}).items()
                    if str(key) and str(value).strip()}

    updated, has_labels = _replace_assignment(
        source, class_name, CANONICAL_LABEL_NAME, labels)
    updated, has_descriptions = _replace_assignment(
        updated, class_name, CANONICAL_DESCRIPTION_NAME, descriptions)

    missing = []
    newline = "\r\n" if "\r\n" in updated else "\n"
    tree = ast.parse(updated)
    command = _command_class(tree, class_name)
    indent = " " * (command.col_offset + 4)
    if labels and not has_labels:
        missing.extend(_mapping_block(
            indent, CANONICAL_LABEL_NAME, labels, newline))
    if descriptions and not has_descriptions:
        missing.extend(_mapping_block(
            indent, CANONICAL_DESCRIPTION_NAME, descriptions, newline))
    if missing:
        lines = updated.splitlines(True)
        insert_at = _metadata_insert_line(command)
        if insert_at and lines[insert_at - 1].strip():
            missing.append(newline)
        lines[insert_at:insert_at] = missing
        updated = "".join(lines)

    ast.parse(updated)
    return updated
