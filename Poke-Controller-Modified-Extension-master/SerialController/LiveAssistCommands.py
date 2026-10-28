"""Hot registration of small controller scripts, without imports or restarts."""
import ast
import json
from pathlib import Path
import re

from SubscriptionAgent import atomic_json


CALLS = {"press", "press_rep", "hold", "release", "release_all", "stick",
         "wait", "log", "image_check", "check_cancelled", "cancelled", "range", "Direction"}
ENUMS = {"Button", "Hat", "Stick"}


def validate_operation(code):
    if not isinstance(code, str) or not code.strip() or len(code) > 32000:
        raise ValueError("操作コードは1～32000文字で指定してください")
    tree = ast.parse(code, mode="exec")
    banned = (ast.Import, ast.ImportFrom, ast.ClassDef, ast.FunctionDef,
              ast.AsyncFunctionDef, ast.While, ast.With, ast.Try, ast.Lambda,
              ast.Delete, ast.Global, ast.Nonlocal)
    for node in ast.walk(tree):
        if isinstance(node, banned):
            raise ValueError("操作コードではimport・関数定義・while等は使用できません")
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            raise ValueError("内部変数は使用できません")
        if isinstance(node, ast.Attribute) and not (
                isinstance(node.value, ast.Name) and node.value.id in ENUMS
                and isinstance(node.ctx, ast.Load) and not node.attr.startswith("_")):
            raise ValueError("属性参照はButton / Hat / Stickのみ使用できます")
        if isinstance(node, ast.Call) and not (
                isinstance(node.func, ast.Name) and node.func.id in CALLS):
            raise ValueError("登録操作はpress / stick / wait等の操作用関数を使用してください")
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id in CALLS | ENUMS:
            raise ValueError("操作用関数・定数の上書きはできません")
    compile(tree, "<registered-operation>", "exec")
    return code


class LiveCommandRegistry:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.items = {}
        self.errors = []
        self.signature = None
        self.file_signature = None

    def scan(self, force=False):
        files = sorted(self.directory.glob("*.json"))[:101]
        file_signature = [(str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in files]
        if not force and file_signature == self.file_signature:
            return False
        items, errors, seen = {}, [], set()
        for path in files[:100]:
            try:
                if path.is_symlink() or path.stat().st_size > 65536:
                    raise ValueError("ファイルサイズ／リンクが不正です")
                value = json.loads(path.read_text(encoding="utf-8-sig"))
                key, name = str(value.get("id", "")), str(value.get("name", "")).strip()
                if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key) or not name or len(name) > 80:
                    raise ValueError("id / nameが不正です")
                if key in items or name.casefold() in seen:
                    raise ValueError("idまたは名前が重複しています")
                code = validate_operation(value.get("code"))
                items[key] = {"id": key, "name": name, "code": code}
                seen.add(name.casefold())
            except (OSError, ValueError, TypeError, AttributeError, SyntaxError) as error:
                errors.append(path.name + ": " + str(error))
        if len(files) > 100:
            errors.append("登録上限は100件です")
        signature = json.dumps(items, sort_keys=True, ensure_ascii=False)
        changed = signature != self.signature or errors != self.errors
        self.items, self.errors, self.signature = items, errors, signature
        self.file_signature = file_signature
        return changed

    def register(self, key, name, code):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key):
            raise ValueError("idは英数字・_・-の64文字以内です")
        validate_operation(code)
        name = name.strip()
        if not name or len(name) > 80:
            raise ValueError("名前は1～80文字で指定してください")
        self.scan()
        if any(item["id"] != key and item["name"].casefold() == name.casefold() for item in self.items.values()):
            raise ValueError("同じ名前の操作が登録済みです。既存IDを指定して更新してください")
        if key not in self.items and len(self.items) >= 100:
            raise ValueError("登録上限は100件です")
        atomic_json(self.directory / (key + ".json"), {"id": key, "name": name, "code": code})
        self.scan()
