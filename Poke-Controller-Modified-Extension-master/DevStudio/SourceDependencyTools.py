#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyze and safely register/apply a callable source-function group."""
from __future__ import print_function

import ast
import json
import os
import textwrap

from SampleLibrary import catalog, load_fragment
from SourceFunctionTools import (function_content_hash, function_sync_record,
                                 register_source_functions, source_imports)


FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)

# These settings are owned by DevStudio's Image detection library.  Copying the
# generated dictionaries into every function group would create a second,
# quickly-stale source of truth (and can add several hundred KB to one sample).
MANAGED_EXTERNAL_CLASS_VARIABLES = {
    "IMAGE_DETECTION_TARGETS",
    "IMAGE_DETECTION_SETS",
    "IMAGE_DETECTION_OPERATORS",
}


def _node_end_line(node, lines):
    end = getattr(node, "end_lineno", None)
    if end is not None:
        return end
    compound_nodes = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                      ast.If, ast.For, ast.While, ast.Try, ast.With)
    async_for = getattr(ast, "AsyncFor", ())
    async_with = getattr(ast, "AsyncWith", ())
    if isinstance(node, async_for if isinstance(async_for, tuple) else (async_for,)) or \
            isinstance(node, async_with if isinstance(async_with, tuple) else (async_with,)):
        compound_nodes = compound_nodes + tuple(
            value for value in (async_for, async_with) if not isinstance(value, tuple))
    if not isinstance(node, compound_nodes):
        balance = 0
        for index in range(node.lineno - 1, len(lines)):
            value = lines[index]
            balance += sum(value.count(mark) for mark in "([{")
            balance -= sum(value.count(mark) for mark in ")]}")
            if balance <= 0 and not value.rstrip().endswith("\\"):
                return index + 1
        return len(lines)
    header_end = node.lineno - 1
    balance = 0
    for index in range(node.lineno - 1, len(lines)):
        value = lines[index]
        balance += sum(value.count(mark) for mark in "([{")
        balance -= sum(value.count(mark) for mark in ")]}")
        if balance <= 0 and value.rstrip().endswith(":"):
            header_end = index
            break
    for index in range(header_end + 1, len(lines)):
        value = lines[index]
        stripped = value.strip()
        if stripped and not stripped.startswith("#") and \
                len(value) - len(value.lstrip(" \t")) <= node.col_offset:
            return index
    return len(lines)


def _string_literal(node):
    value = getattr(node, "value", None)
    if isinstance(value, str):
        return value
    value = getattr(node, "s", None)
    return value if isinstance(value, str) else None


def _first_class(tree):
    command = next((node for node in tree.body if isinstance(node, ast.ClassDef)), None)
    if command is None:
        raise ValueError("ソース内にクラスがありません。")
    return command


def _source_segment(source, node):
    value = ast.get_source_segment(source, node)
    if value is None:
        lines = source.splitlines(True)
        value = "".join(lines[node.lineno - 1:_node_end_line(node, lines)])
    return value


def _dedent_structural(source, node):
    lines = source.splitlines(True)
    raw = "".join(lines[node.lineno - 1:_node_end_line(node, lines)])
    prefix = lines[node.lineno - 1][:node.col_offset]
    return "".join(
        line[len(prefix):] if prefix and line.startswith(prefix) else line
        for line in raw.splitlines(True)).rstrip() + "\n"


def _self_attributes(node):
    methods, attributes = set(), set()
    for value in ast.walk(node):
        if not isinstance(value, ast.Attribute) or \
                not isinstance(value.value, ast.Name) or value.value.id != "self":
            continue
        attributes.add(value.attr)
    return methods, attributes


def _assigned_self_attributes(node):
    names = set()
    for value in ast.walk(node):
        if isinstance(value, ast.Attribute) and \
                isinstance(value.ctx, (ast.Store, ast.Del)) and \
                isinstance(value.value, ast.Name) and value.value.id == "self":
            names.add(value.attr)
    return names


def _assignment_names(node):
    names = set()
    for value in ast.walk(node):
        if isinstance(value, ast.Name) and isinstance(value.ctx, ast.Store):
            names.add(value.id)
    return names


def analyze_source_dependencies(source, roots, seed_attributes=None):
    """Return the transitive self-method group and required support code.

    State-machine handlers referenced in ``self.STATE_*`` initializer
    dictionaries are followed as method dependencies as well.
    """
    tree = ast.parse(source)
    command = _first_class(tree)
    methods = {
        node.name: node for node in command.body if isinstance(node, FUNCTION_NODES)}
    roots = [str(name) for name in roots]
    missing = sorted(set(roots) - set(methods), key=str.casefold)
    if missing:
        raise ValueError("起点関数がありません: " + ", ".join(missing))

    initializer = methods.get("__init__")
    initializer_statements = list(initializer.body) if initializer else []
    initializer_by_attribute = {}
    for statement in initializer_statements:
        for name in _assigned_self_attributes(statement):
            initializer_by_attribute.setdefault(name, []).append(statement)

    class_by_name = {}
    for statement in command.body:
        if isinstance(statement, FUNCTION_NODES):
            continue
        for name in _assignment_names(statement):
            class_by_name.setdefault(name, []).append(statement)

    included_methods = set()
    required_attributes = set(str(value) for value in (seed_attributes or []))
    external_class_variables = set()
    selected_initializer_ids = set()
    selected_class_ids = set()
    edges = {}
    method_queue = list(roots)
    attribute_queue = sorted(required_attributes, key=str.casefold)

    def scan(value):
        method_refs, attributes = set(), set()
        for node in ast.walk(value):
            if isinstance(node, ast.Attribute) and \
                    isinstance(node.value, ast.Name) and node.value.id == "self":
                if node.attr in methods:
                    method_refs.add(node.attr)
                else:
                    attributes.add(node.attr)
        return method_refs, attributes

    while method_queue or attribute_queue:
        while method_queue:
            name = method_queue.pop(0)
            if name in included_methods or name not in methods or name == "__init__":
                continue
            included_methods.add(name)
            method_refs, attributes = scan(methods[name])
            edges[name] = sorted(method_refs, key=str.casefold)
            method_queue.extend(sorted(method_refs - included_methods, key=str.casefold))
            for attribute in sorted(attributes - required_attributes, key=str.casefold):
                required_attributes.add(attribute)
                attribute_queue.append(attribute)
        while attribute_queue:
            attribute = attribute_queue.pop(0)
            for statement in initializer_by_attribute.get(attribute, []):
                if id(statement) in selected_initializer_ids:
                    continue
                selected_initializer_ids.add(id(statement))
                method_refs, attributes = scan(statement)
                method_queue.extend(sorted(method_refs - included_methods, key=str.casefold))
                for dependency in sorted(attributes - required_attributes, key=str.casefold):
                    required_attributes.add(dependency)
                    attribute_queue.append(dependency)
            for statement in class_by_name.get(attribute, []):
                assigned_names = _assignment_names(statement)
                managed_names = assigned_names & MANAGED_EXTERNAL_CLASS_VARIABLES
                if managed_names:
                    external_class_variables.update(managed_names)
                    continue
                if id(statement) in selected_class_ids:
                    continue
                selected_class_ids.add(id(statement))
                method_refs, attributes = scan(statement)
                method_queue.extend(sorted(method_refs - included_methods, key=str.casefold))
                for dependency in sorted(attributes - required_attributes, key=str.casefold):
                    required_attributes.add(dependency)
                    attribute_queue.append(dependency)

    selected_initializers = [
        statement for statement in initializer_statements
        if id(statement) in selected_initializer_ids]
    selected_class = [
        statement for statement in command.body
        if id(statement) in selected_class_ids]
    initialized = set().union(*(
        _assigned_self_attributes(statement) for statement in selected_initializers)) \
        if selected_initializers else set()
    class_names = set().union(*(
        _assignment_names(statement) for statement in selected_class)) \
        if selected_class else set()
    unresolved = sorted(
        required_attributes - initialized - class_names - external_class_variables,
        key=str.casefold)
    state_dictionaries = {}
    for attribute in sorted(required_attributes, key=str.casefold):
        if not (attribute.startswith("STATE_") and attribute.endswith("_FUNCTION")):
            continue
        entries = []
        for statement in initializer_by_attribute.get(attribute, []):
            assignment = next((node for node in ast.walk(statement)
                               if isinstance(node, (ast.Assign, ast.AnnAssign)) and
                               isinstance(node.value, ast.Dict)), None)
            if assignment is None:
                continue
            for key, value in zip(assignment.value.keys, assignment.value.values):
                key_value = _string_literal(key)
                if key_value is not None and \
                        isinstance(value, ast.Attribute) and \
                        isinstance(value.value, ast.Name) and value.value.id == "self":
                    entries.append({"state": key_value, "handler": value.attr})
        if entries:
            state_dictionaries[attribute] = entries
    ordered_methods = [
        node.name for node in command.body
        if isinstance(node, FUNCTION_NODES) and node.name in included_methods]
    return {
        "class_name": command.name,
        "roots": roots,
        "methods": ordered_methods,
        "method_text": {
            name: _dedent_structural(source, methods[name]) for name in ordered_methods},
        "edges": edges,
        "imports": source_imports(source),
        "class_variables": [
            _dedent_structural(source, statement).rstrip()
            for statement in selected_class],
        "initializer": "\n".join(
            _dedent_structural(source, statement).rstrip()
            for statement in selected_initializers),
        "required_attributes": sorted(required_attributes, key=str.casefold),
        "unresolved_attributes": unresolved,
        "external_class_variables": sorted(
            external_class_variables, key=str.casefold),
        "state_dictionaries": state_dictionaries,
    }


def state_dictionary_current_state(source, dictionary_name):
    """Find the current-state attribute initialized with a key of a state dict."""
    entries = state_dictionary_handlers(source, dictionary_name)
    states = set(state for state, _handler in entries)
    tree = ast.parse(source)
    command = _first_class(tree)
    initializer = next((node for node in command.body
                        if isinstance(node, FUNCTION_NODES) and
                        node.name == "__init__"), None)
    if initializer is not None:
        candidates = []
        for statement in initializer.body:
            assigned = _assigned_self_attributes(statement)
            values = {_string_literal(node) for node in ast.walk(statement)}
            if states & values:
                candidates.extend(
                    name for name in assigned
                    if name.endswith("current_state") or name.endswith("_state"))
        if candidates:
            return sorted(candidates, key=lambda name: (
                0 if dictionary_name[6:-9].lower() in name.lower() else 1,
                name.casefold()))[0]
    base = dictionary_name
    if base.startswith("STATE_"):
        base = base[6:]
    if base.endswith("_FUNCTION"):
        base = base[:-9]
    return base.lower() + "_current_state"


def analyze_state_dictionary_dependencies(source, dictionary_name,
                                          main_function_name=""):
    """Analyze a state group using its dictionary as the authoritative root.

    An existing main function may be included, but is not required.  Every
    handler in the dictionary and any nested state dictionary it reaches is
    followed recursively.
    """
    entries = state_dictionary_handlers(source, dictionary_name)
    handlers = [handler for _state, handler in entries]
    tree = ast.parse(source)
    command = _first_class(tree)
    available = {
        node.name for node in command.body if isinstance(node, FUNCTION_NODES)}
    roots = []
    if main_function_name and main_function_name in available:
        roots.append(main_function_name)
    roots.extend(handler for handler in handlers if handler not in roots)
    current_state = state_dictionary_current_state(source, dictionary_name)
    analysis = analyze_source_dependencies(
        source, roots, seed_attributes=[dictionary_name, current_state])
    analysis["root_state_dictionary"] = dictionary_name
    analysis["current_state_attribute"] = current_state
    analysis["root_state_handlers"] = [
        {"state": state, "handler": handler} for state, handler in entries]
    return analysis


def suggest_state_dictionary(analysis, root_name=""):
    """Choose the state dictionary most closely describing a selected main."""
    dictionaries = list(analysis.get("state_dictionaries", {}))
    if not dictionaries:
        return ""
    root_tokens = {
        token for token in str(root_name).upper().split("_")
        if token and token not in {"FUNCTION", "STATE"}}

    def score(name):
        tokens = {
            token for token in name.upper().split("_")
            if token and token not in {"FUNCTION", "STATE"}}
        return (-len(root_tokens & tokens), dictionaries.index(name))
    return sorted(dictionaries, key=score)[0]


def state_dictionary_handlers(source, dictionary_name):
    """Return ordered string-state -> self-handler entries from ``__init__``."""
    tree = ast.parse(source)
    command = _first_class(tree)
    initializer = next((node for node in command.body
                        if isinstance(node, FUNCTION_NODES) and
                        node.name == "__init__"), None)
    if initializer is None:
        raise ValueError("__init__ がありません。")
    for statement in initializer.body:
        assigned = _assigned_self_attributes(statement)
        if dictionary_name not in assigned:
            continue
        assignment = next((node for node in ast.walk(statement)
                           if isinstance(node, (ast.Assign, ast.AnnAssign)) and
                           isinstance(node.value, ast.Dict)), None)
        if assignment is None:
            continue
        entries = []
        for key, value in zip(assignment.value.keys, assignment.value.values):
            key_value = _string_literal(key)
            if key_value is not None and \
                    isinstance(value, ast.Attribute) and \
                    isinstance(value.value, ast.Name) and value.value.id == "self":
                entries.append((key_value, value.attr))
        if entries:
            return entries
    raise ValueError("状態辞書が見つかりません: " + str(dictionary_name))


def state_dictionary_names(source):
    """Return state dictionary attributes declared in the first class init."""
    tree = ast.parse(source)
    command = _first_class(tree)
    initializer = next((node for node in command.body
                        if isinstance(node, FUNCTION_NODES) and
                        node.name == "__init__"), None)
    if initializer is None:
        return []
    result = []
    for statement in initializer.body:
        for name in sorted(_assigned_self_attributes(statement), key=str.casefold):
            if name.startswith("STATE_") and name.endswith("_FUNCTION") and \
                    name not in result:
                result.append(name)
    return result


def generate_state_machine_main(function_name, dictionary_name,
                                current_state_name, wait_expression="0.02"):
    """Generate the common PokeCon state-dictionary main loop."""
    if not all(str(value).isidentifier() for value in (
            function_name, dictionary_name, current_state_name)):
        raise ValueError("関数名・辞書名・状態変数名を確認してください。")
    code = (
        "def {function}(self):\n"
        "    while True:\n"
        "        self.{state} = self.{dictionary}[self.{state}]()\n"
        "        self.wait({wait})\n"
        "        self.checkIfAlive()\n"
        "    return True\n"
    ).format(
        function=function_name, state=current_state_name,
        dictionary=dictionary_name, wait=str(wait_expression))
    ast.parse(code)
    return code


def _normalized_function(value):
    tree = ast.parse(textwrap.dedent(str(value)))
    function = next((node for node in tree.body if isinstance(node, FUNCTION_NODES)), None)
    if function is None:
        raise ValueError("関数コードではありません。")
    return ast.dump(function, annotate_fields=True, include_attributes=False)


def catalog_function_candidates(fragment_root):
    """Map every function found in registered fragments to its fragment ID."""
    result = {}
    for item in catalog(fragment_root):
        try:
            metadata, body, _, body_path = load_fragment(fragment_root, item["id"])
            tree = ast.parse(body)
        except (OSError, ValueError, KeyError, SyntaxError):
            continue
        lines = body.splitlines(True)
        for node in tree.body:
            if not isinstance(node, FUNCTION_NODES):
                continue
            text = "".join(lines[node.lineno - 1:_node_end_line(node, lines)])
            result.setdefault(node.name, []).append({
                "id": item["id"], "metadata": metadata,
                "body_path": body_path, "text": text.rstrip() + "\n",
                "normalized": _normalized_function(text),
            })
    return result


def plan_dependency_registration(source, roots, fragment_root,
                                 state_dictionary="", analysis=None):
    """Compare a dependency analysis with registered sample functions.

    ``analysis`` may be supplied by a caller that already parsed the source.
    Large Commands can contain thousands of methods, so parsing them again
    immediately before the fragment-library scan caused a noticeable pause.
    """
    if analysis is None:
        if state_dictionary:
            analysis = analyze_state_dictionary_dependencies(
                source, state_dictionary,
                main_function_name=roots[0] if len(roots) == 1 else "")
        else:
            analysis = analyze_source_dependencies(source, roots)
    candidates = catalog_function_candidates(fragment_root)
    rows = []
    for name in analysis["methods"]:
        wanted = _normalized_function(analysis["method_text"][name])
        found = candidates.get(name, [])
        exact = [item for item in found if item["normalized"] == wanted]
        if exact:
            status, selected = "reuse", exact[0]
        elif found:
            status, selected = "different", None
        else:
            status, selected = "missing", None
        rows.append({
            "name": name, "status": status, "selected": selected,
            "candidates": found, "exact_count": len(exact)})
    analysis["registration"] = rows
    return analysis


def _write_support_fragment(fragment_root, folder, list_name, analysis,
                            source_path=""):
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in list_name)
    support_name = safe + "__support"
    directory = os.path.join(fragment_root, *folder.replace("\\", "/").split("/"), support_name)
    os.makedirs(directory, exist_ok=True)
    body_path = os.path.join(directory, support_name + ".pyfrag")
    metadata_path = os.path.join(directory, support_name + ".pokesample.json")
    metadata = {
        "schema_version": 1,
        "name": support_name,
        "tags": ["source", "dependency-group", list_name],
        "imports": analysis["imports"],
        "class_variables": analysis["class_variables"],
        "initializer": analysis["initializer"],
        "fragment": os.path.basename(body_path),
        "source": {"path": str(source_path or ""), "function": analysis["roots"][0]},
        "dependency_group": {
            "roots": analysis["roots"], "methods": analysis["methods"],
            "required_attributes": analysis["required_attributes"],
            "unresolved_attributes": analysis["unresolved_attributes"],
            "state_dictionaries": analysis.get("state_dictionaries", {}),
            "root_state_dictionary": analysis.get("root_state_dictionary", ""),
            "current_state_attribute": analysis.get("current_state_attribute", ""),
            "external_class_variables": analysis.get(
                "external_class_variables", []),
        },
    }
    with open(body_path + ".tmp", "w", encoding="utf-8", newline="\n") as stream:
        stream.write("# Support settings for dependency group: {}\n".format(list_name))
    with open(metadata_path + ".tmp", "w", encoding="utf-8", newline="\n") as stream:
        json.dump(metadata, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(body_path + ".tmp", body_path)
    os.replace(metadata_path + ".tmp", metadata_path)
    return os.path.relpath(metadata_path, fragment_root).replace("\\", "/")


def register_dependency_group(source, roots, fragment_root, folder, list_name,
                              source_path="", state_dictionary="", analysis=None):
    """Register missing methods and return function-scoped list members."""
    plan = plan_dependency_registration(
        source, roots, fragment_root, state_dictionary=state_dictionary,
        analysis=analysis)
    different = [row["name"] for row in plan["registration"]
                 if row["status"] == "different"]
    if different:
        raise ValueError(
            "登録済みサンプルと内容が異なります。先に差分確認してください: " +
            ", ".join(different))
    missing = [row["name"] for row in plan["registration"]
               if row["status"] == "missing"]
    if missing:
        created = register_source_functions(
            source, missing, fragment_root, folder=folder,
            tags=["source", "dependency-group", list_name], overwrite=False,
            source_path=source_path)
        # The former implementation rescanned and reparsed every registered
        # sample after writing the missing methods.  Use the files we just
        # created to complete the plan instead.  Existing samples were already
        # fully checked by the first scan above.
        created_by_name = {item["name"]: item for item in created}
        for row in plan["registration"]:
            item = created_by_name.get(row["name"])
            if item is None:
                continue
            method_text = plan["method_text"][row["name"]]
            selected = {
                "id": item["id"],
                "metadata": {},
                "body_path": item["body_path"],
                "text": method_text.rstrip() + "\n",
                "normalized": _normalized_function(method_text),
            }
            row.update({
                "status": "created", "selected": selected,
                "candidates": [selected], "exact_count": 1,
            })
    support_id = _write_support_fragment(
        fragment_root, folder, list_name, plan, source_path=source_path)
    # Reused functions can live inside a multi-function fragment whose
    # metadata name is not the function name.  Record the exact reused body as
    # a synchronization baseline so both the registration tab and later
    # function-level new/old checks recognize it correctly.
    metadata_updates = {}
    for row in plan["registration"]:
        selected = row.get("selected")
        if row.get("status") != "reuse" or not selected:
            continue
        source_text = plan["method_text"].get(row["name"], "")
        if function_content_hash(source_text) != function_content_hash(
                selected.get("text", "")):
            continue
        metadata_path = os.path.abspath(os.path.join(
            fragment_root, selected["id"]))
        metadata = metadata_updates.get(metadata_path)
        if metadata is None:
            with open(metadata_path, "r", encoding="utf-8") as stream:
                metadata = json.load(stream)
            metadata_updates[metadata_path] = metadata
        history = dict(metadata.get("function_sync", {}))
        history[row["name"]] = function_sync_record(
            row["name"], source_text)
        metadata["function_sync"] = history
    for metadata_path, metadata in metadata_updates.items():
        temporary = metadata_path + ".dependency-sync.tmp"
        with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(metadata, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, metadata_path)
    members = [{"type": "fragment", "id": support_id}]
    seen = set()
    for row in plan["registration"]:
        selected = row.get("selected")
        if not selected:
            raise ValueError("サンプル登録に失敗しました: " + row["name"])
        key = (selected["id"], row["name"])
        if key in seen:
            continue
        seen.add(key)
        members.append({
            "type": "fragment", "id": selected["id"],
            "function": row["name"],
            "origin_path": str(source_path or ""),
            "origin_function": row["name"]})
    return plan, members


def compare_preview_functions(source, preview):
    """Classify preview methods against the first class in source."""
    tree = ast.parse(source)
    command = _first_class(tree)
    current = {
        node.name: _dedent_structural(source, node)
        for node in command.body if isinstance(node, FUNCTION_NODES)}
    samples = {}
    duplicates = set()
    for body in preview.get("bodies", []):
        parsed = ast.parse(body)
        lines = body.splitlines(True)
        for node in parsed.body:
            if not isinstance(node, FUNCTION_NODES):
                continue
            text = "".join(lines[node.lineno - 1:_node_end_line(node, lines)])
            if node.name in samples:
                duplicates.add(node.name)
            samples[node.name] = text.rstrip() + "\n"
    rows = []
    for name, text in samples.items():
        if name in duplicates:
            status = "duplicate"
        elif name not in current:
            status = "missing"
        elif _normalized_function(current[name]) == _normalized_function(text):
            status = "match"
        else:
            status = "different"
        rows.append({
            "name": name, "status": status, "sample": text,
            "source": current.get(name, "")})
    return rows


def _statement_dump(statement):
    return ast.dump(statement, annotate_fields=True, include_attributes=False)


def _parse_class_variable(value):
    tree = ast.parse("class _Sample:\n" + textwrap.indent(str(value).rstrip(), "    ") + "\n")
    statement = tree.body[0].body[0]
    return statement, _assignment_names(statement)


def _parse_initializer(value):
    if not str(value).strip():
        return []
    tree = ast.parse(
        "def _sample_initializer(self):\n" +
        textwrap.indent(str(value).rstrip(), "    ") + "\n")
    return list(tree.body[0].body)


def compare_preview_support(source, preview):
    """Compare class variables and initializer statements by assigned names."""
    tree = ast.parse(source)
    command = _first_class(tree)
    class_by_name = {}
    for statement in command.body:
        if isinstance(statement, FUNCTION_NODES):
            continue
        for name in _assignment_names(statement):
            class_by_name[name] = statement
    initializer = next((node for node in command.body
                        if isinstance(node, FUNCTION_NODES) and
                        node.name == "__init__"), None)
    init_by_name = {}
    if initializer:
        for statement in initializer.body:
            for name in _assigned_self_attributes(statement):
                init_by_name[name] = statement

    rows = []
    for value in preview.get("class_variables", []):
        statement, names = _parse_class_variable(value)
        existing = [class_by_name[name] for name in names if name in class_by_name]
        status = "missing" if not existing else (
            "match" if all(_statement_dump(item) == _statement_dump(statement)
                           for item in existing) else "different")
        rows.append({
            "kind": "class_variable", "name": ", ".join(sorted(names)),
            "status": status, "text": str(value).rstrip()})
    for value in preview.get("initializers", []):
        for statement in _parse_initializer(value):
            names = _assigned_self_attributes(statement)
            existing = [init_by_name[name] for name in names if name in init_by_name]
            status = "missing" if not existing else (
                "match" if all(_statement_dump(item) == _statement_dump(statement)
                               for item in existing) else "different")
            rows.append({
                "kind": "initializer", "name": ", ".join(sorted(names)),
                "status": status,
                "text": _dedent_structural(
                    "def _sample_initializer(self):\n" +
                    textwrap.indent(str(value).rstrip(), "    ") + "\n",
                    statement).rstrip()})
    return rows


def merge_preview_support_safely(source, preview):
    """Add only missing imports/class variables/initializer statements."""
    support_rows = compare_preview_support(source, preview)
    blocked = [row for row in support_rows if row["status"] == "different"]
    if blocked:
        raise ValueError(
            "初期化・変数の差分確認が必要です: " +
            ", ".join(row["name"] for row in blocked))
    updated = source
    missing_imports = [
        value for value in preview.get("imports", [])
        if value and value not in updated.splitlines()]
    if missing_imports:
        tree = ast.parse(updated)
        imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
        insert_at = max((getattr(node, "end_lineno", node.lineno)
                         for node in imports), default=0)
        lines = updated.splitlines(True)
        lines[insert_at:insert_at] = [
            value.rstrip() + "\n" for value in missing_imports] + ["\n"]
        updated = "".join(lines)

    missing_class = [row["text"] for row in support_rows
                     if row["kind"] == "class_variable" and
                     row["status"] == "missing"]
    if missing_class:
        tree = ast.parse(updated)
        command = _first_class(tree)
        lines = updated.splitlines(True)
        insert_at = command.lineno
        block = []
        for value in missing_class:
            block.append(textwrap.indent(value.rstrip(), "    ") + "\n")
        block.append("\n")
        lines[insert_at:insert_at] = block
        updated = "".join(lines)

    missing_init = [row["text"] for row in support_rows
                    if row["kind"] == "initializer" and
                    row["status"] == "missing"]
    if missing_init:
        tree = ast.parse(updated)
        command = _first_class(tree)
        initializer = next((node for node in command.body
                            if isinstance(node, FUNCTION_NODES) and
                            node.name == "__init__"), None)
        if initializer is None:
            raise ValueError("初期化処理の反映先 __init__ がありません。")
        lines = updated.splitlines(True)
        insert_at = getattr(initializer, "end_lineno", initializer.lineno)
        block = ["        # POKECON_DEPENDENCY_INITIALIZER\n"]
        block.extend(textwrap.indent(value.rstrip(), "        ") + "\n"
                     for value in missing_init)
        lines[insert_at:insert_at] = block
        updated = "".join(lines)
    ast.parse(updated)
    return updated, support_rows


def merge_preview_functions_safely(source, preview, list_name):
    """Reuse equal methods and add only missing ones; never overwrite a diff."""
    rows = compare_preview_functions(source, preview)
    blocked = [row for row in rows if row["status"] in ("different", "duplicate")]
    if blocked:
        raise ValueError("差分確認が必要です: " + ", ".join(row["name"] for row in blocked))
    missing = [row for row in rows if row["status"] == "missing"]
    if not missing:
        return source, rows
    tree = ast.parse(source)
    command = _first_class(tree)
    lines = source.splitlines(True)
    insert_at = getattr(command, "end_lineno", len(lines))
    block = ["\n    # POKECON_DEPENDENCY_GROUP_BEGIN {}\n".format(list_name)]
    for row in missing:
        block.append(textwrap.indent(row["sample"].rstrip(), "    ") + "\n\n")
    block.append("    # POKECON_DEPENDENCY_GROUP_END {}\n".format(list_name))
    lines[insert_at:insert_at] = block
    updated = "".join(lines)
    ast.parse(updated)
    return updated, rows
