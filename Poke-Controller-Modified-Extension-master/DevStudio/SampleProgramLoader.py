#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Safe validation loader for authored PythonSampleCommand modules."""
from __future__ import print_function

import ast
import os


def inspect_sample_program(path):
    with open(path, "r", encoding="utf-8") as stream:
        source = stream.read()
    tree = ast.parse(source, filename=path)
    classes = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(base.attr)
            if "PythonSampleCommand" in bases:
                classes.append(node.name)
    if len(classes) != 1:
        raise ValueError("Exactly one PythonSampleCommand subclass is required")
    return {"path": os.path.abspath(path), "class_name": classes[0], "source": source}
