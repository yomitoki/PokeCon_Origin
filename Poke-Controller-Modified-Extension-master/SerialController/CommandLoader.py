#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import importlib.util
import os
import sys

import Utility as util

from logging import getLogger, DEBUG, NullHandler

logger = getLogger(__name__)
logger.addHandler(NullHandler())
logger.setLevel(DEBUG)
logger.propagate = True


class CommandLoader:
    def __init__(self, base_path, base_class):
        self.path = base_path
        self.base_type = base_class
        self.modules = []
        self.errors = []

    def load(self):
        if not self.modules:  # load if empty
            self.errors = []
            self.modules = util.importAllModules(self.path, errors=self.errors)

        # return command class types
        return self.getCommandClasses()

    def reload(self):
        self.errors = []
        loaded_module_dic = {mod.__name__: mod for mod in self.modules}
        cur_module_names = util.getModuleNames(self.path)

        # Load only not loaded modules
        not_loaded_module_names = list(set(cur_module_names) - set(loaded_module_dic.keys()))
        if len(not_loaded_module_names) > 0:
            self.modules.extend(util.importAllModules(
                self.path, not_loaded_module_names, errors=self.errors))

        # Reload commands except deleted ones
        for mod_name in list(set(cur_module_names) & set(loaded_module_dic.keys())):
            try:
                importlib.reload(loaded_module_dic[mod_name])
            except Exception as error:
                logger.exception("Could not reload command module: %s", mod_name)
                self.errors.append({"module": str(mod_name), "error": str(error)})

        # Unload deleted commands
        for mod_name in list(set(loaded_module_dic.keys()) - set(cur_module_names)):
            self.modules.remove(loaded_module_dic[mod_name])
            sys.modules.pop(loaded_module_dic[mod_name].__name__)  # Un-import module forcefully

        # return command class types
        return self.getCommandClasses()

    def getCommandClasses(self):
        classes = []
        for mod in self.modules:
            # extract module of having "NAME"
            class_list = [
                c
                for c in util.getClassesInModule(mod)
                if issubclass(c, self.base_type) and hasattr(c, "NAME") and c.NAME
            ]

            # make tags of directory name
            for c in class_list:
                dir_name = "/".join(mod.__name__.split(".")[2:])
                dir_tags = ["@" + t for t in mod.__name__.split(".")[2:-1]]

                # add tags of directory name
                if hasattr(c, "TAGS"):
                    if isinstance(c.TAGS, list):
                        logger.debug(f"TAGS name add: {dir_tags}")
                        c.TAGS = c.TAGS + dir_tags
                    elif isinstance(c.TAGS, str):
                        logger.debug(f"TAGS name add: {dir_tags}")
                        c.TAGS = [c.TAGS] + dir_tags
                    else:
                        logger.debug(f"TAGS Type error: {mod.__name__} {c.NAME} {type(c.TAGS)}")
                else:
                    logger.debug(f"TAGS do not exist: {mod.__name__} {c.NAME}")
                    c.TAGS = dir_tags

                # rename NAME
                c.NAME = f"{c.NAME} ({dir_name})"
                classes.append(c)

        return classes


class FileCommandLoader(CommandLoader):
    """Load command modules recursively from an absolute directory."""
    def __init__(self, base_path, base_class, module_prefix="DevStudio.SampleCommands"):
        super().__init__(os.path.abspath(base_path), base_class)
        self.module_prefix = module_prefix

    def _load_files(self):
        modules = []
        if not os.path.isdir(self.path):
            return modules
        for directory, dirs, names in os.walk(self.path):
            dirs[:] = sorted(item for item in dirs if item != "__pycache__")
            for filename in sorted(names):
                if not filename.endswith(".py") or filename.startswith("__"):
                    continue
                path = os.path.join(directory, filename)
                relative = os.path.relpath(path[:-3], self.path).replace(os.sep, ".")
                module_name = self.module_prefix + "." + relative
                spec = importlib.util.spec_from_file_location(module_name, path)
                if spec is None or spec.loader is None:
                    continue
                try:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    modules.append(module)
                except Exception:
                    sys.modules.pop(module_name, None)
                    logger.exception("Could not load PythonSampleCommand: %s", path)
                    self.errors.append({"module": path, "error": "import failed"})
        return modules

    def load(self):
        self.errors = []
        self.modules = self._load_files()
        return self.getCommandClasses()

    def reload(self):
        self.errors = []
        for module in self.modules:
            sys.modules.pop(module.__name__, None)
        self.modules = self._load_files()
        return self.getCommandClasses()
