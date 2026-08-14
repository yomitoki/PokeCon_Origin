#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create bounded, verified PokeCon migration and command packages."""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import fnmatch
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile


FORMAT_VERSION = 1
DEFAULT_MAX_VOLUME_MIB = 1024
ZIP_HEADROOM = 8 * 1024 * 1024
CHUNK_HEADROOM = 2 * 1024 * 1024
BUFFER_SIZE = 1024 * 1024
RESOURCE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp",
    ".json", ".jsonc", ".yaml", ".yml", ".csv", ".txt",
    ".wav", ".mp3", ".ini", ".toml",
}
MIGRATION_EXCLUDES = (
    ".venv*/**",
    "**/__pycache__/**",
    "**/*.pyc",
    "bk/**",
    "DevStudio/Backups/**",
    "SerialController/Recordings/**",
    "SerialController/CommandsRecording/**",
    "SerialController/OperationSessions/**",
    "SerialController/Captures/**",
    "SerialController/Captures_Area/**",
    "SerialController/Controller_Log/**",
    "SerialController/log/**",
    "log/**",
)
COMMAND_RECORDINGS_PATTERN = "SerialController/CommandsRecording/**"


def _now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(BUFFER_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _relative(path: Path, root: Path) -> str:
    resolved = path.resolve()
    base = root.resolve()
    if not _is_relative_to(resolved, base):
        raise ValueError(f"対象ルート外のパスです: {path}")
    return resolved.relative_to(base).as_posix()


def _match_any(relative_path: str, patterns: tuple[str, ...]) -> bool:
    value = relative_path.replace("\\", "/").casefold()
    return any(fnmatch.fnmatchcase(value, pattern.casefold())
               for pattern in patterns)


def _run_git(root: Path, arguments: list[str], *, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), "-c", "core.quotePath=false", *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"gitコマンドに失敗しました: {message}")
    return result.stdout


def _git_root(source_root: Path) -> Path:
    value = _run_git(source_root, ["rev-parse", "--show-toplevel"])
    return Path(value.decode("utf-8", "replace").strip()).resolve()


def _git_paths(git_root: Path, arguments: list[str]) -> list[Path]:
    if not arguments:
        return []
    raw = _run_git(git_root, [arguments[0], "-z", *arguments[1:]])
    paths = []
    for value in raw.split(b"\0"):
        if value:
            paths.append((git_root / value.decode("utf-8", "surrogateescape")).resolve())
    return paths


def collect_local_files(source_root: Path, profile: str, output: Path | None = None):
    """Return Git-untracked/ignored files and profile exclusions."""
    source_root = source_root.resolve()
    git_root = _git_root(source_root)
    source_pathspec = source_root.relative_to(git_root).as_posix()
    untracked = _git_paths(
        git_root, ["ls-files", "--others", "--exclude-standard", "--", source_pathspec])
    ignored = _git_paths(
        git_root,
        ["ls-files", "--others", "--ignored", "--exclude-standard", "--", source_pathspec],
    )
    candidates = sorted(set(untracked + ignored), key=lambda p: str(p).casefold())
    selected, excluded = [], []
    output = output.resolve() if output else None
    for path in candidates:
        if not path.is_file() or not _is_relative_to(path, source_root):
            continue
        if output and (_is_relative_to(path, output) or path == output):
            excluded.append((path, "出力先"))
            continue
        relative_path = _relative(path, source_root)
        excludes = MIGRATION_EXCLUDES
        if profile == "command-recordings":
            excludes = tuple(pattern for pattern in MIGRATION_EXCLUDES
                             if pattern != COMMAND_RECORDINGS_PATTERN)
        if profile != "complete" and _match_any(relative_path, excludes):
            excluded.append((path, "migrationプロファイルの除外"))
        else:
            selected.append(path)
    return selected, excluded


def _iter_string_literals(path: Path):
    try:
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, UnicodeError):
        return "", []
    values = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            values.append(node.value)
    return source, values


def _resource_index(root: Path):
    by_name: dict[str, list[Path]] = {}
    if root.is_dir():
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.casefold() in RESOURCE_EXTENSIONS:
                by_name.setdefault(path.name.casefold(), []).append(path.resolve())
    return by_name


def _add_tree(files: set[Path], directory: Path):
    if directory.is_dir():
        for path in directory.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                files.add(path.resolve())


def collect_command_files(source_root: Path, command: Path, asset_mode: str = "safe"):
    """Collect one command and its local/config/template dependencies."""
    source_root = source_root.resolve()
    command = command.resolve()
    if not _is_relative_to(command, source_root):
        raise ValueError(f"コマンドは対象ルート配下を指定してください: {command}")
    files: set[Path] = set()
    if command.is_dir():
        _add_tree(files, command)
        command_sources = sorted(command.rglob("*.py"))
    elif command.is_file():
        files.add(command)
        command_sources = [command] if command.suffix.casefold() == ".py" else []
        # JSON/JSONCなど、同じコマンドフォルダの補助設定は常に同梱する。
        for sibling in command.parent.iterdir():
            if sibling.is_file() and sibling.suffix.casefold() in RESOURCE_EXTENSIONS:
                files.add(sibling.resolve())
    else:
        raise FileNotFoundError(f"コマンドが見つかりません: {command}")

    serial_root = source_root / "SerialController"
    commands_root = serial_root / "Commands" / "PythonCommands"
    template_root = serial_root / "Template"
    resource_by_name = _resource_index(template_root)
    combined_source = []
    literals: list[tuple[Path, str]] = []
    for source_path in command_sources:
        source, values = _iter_string_literals(source_path)
        combined_source.append(source)
        literals.extend((source_path, value) for value in values)

    search_roots = [command.parent, serial_root, template_root, commands_root, source_root]
    unresolved = []
    for source_path, value in literals:
        cleaned = value.strip().replace("\\", "/")
        suffix = Path(cleaned).suffix.casefold()
        if suffix not in RESOURCE_EXTENSIONS:
            continue
        candidates = []
        candidate_value = Path(cleaned)
        if candidate_value.is_absolute():
            candidates.append(candidate_value)
        else:
            candidates.append(source_path.parent / candidate_value)
            candidates.extend(root / candidate_value for root in search_roots)
        matched = False
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            if resolved.is_file() and _is_relative_to(resolved, source_root):
                files.add(resolved)
                matched = True
        if not matched:
            by_name = resource_by_name.get(candidate_value.name.casefold(), [])
            for resolved in by_name:
                files.add(resolved)
                matched = True
        if not matched:
            unresolved.append(cleaned)

    source_text = "\n".join(combined_source)
    image_api_used = any(
        marker in source_text for marker in (
            "ImageProcPythonCommand", "isContainTemplate", "isContainedImage",
            "detect_image", "IMAGE_DETECTION_", "POKEMON_",
        ))
    if image_api_used:
        profile = template_root / "image_detection_profiles.json"
        if profile.is_file():
            files.add(profile.resolve())
        # 動的な検出IDや組み立てパスは静的解析だけでは保証できない。
        if asset_mode == "safe":
            _add_tree(files, template_root)

    return sorted(files, key=lambda p: str(p).casefold()), sorted(set(unresolved))


def _inventory(files: list[Path], source_root: Path):
    total = sum(path.stat().st_size for path in files)
    groups: dict[str, list[int]] = {}
    for path in files:
        relative_path = Path(_relative(path, source_root))
        group = relative_path.parts[0] if relative_path.parts else "(root)"
        values = groups.setdefault(group, [0, 0])
        values[0] += 1
        values[1] += path.stat().st_size
    return total, groups


def print_inventory(files: list[Path], source_root: Path, excluded=None, unresolved=None):
    total, groups = _inventory(files, source_root)
    print(f"対象: {len(files):,}ファイル / {total / 1024 / 1024:,.2f} MiB")
    for group, (count, size) in sorted(groups.items(), key=lambda item: -item[1][1]):
        print(f"  {group}: {count:,}ファイル / {size / 1024 / 1024:,.2f} MiB")
    if excluded:
        excluded_size = sum(path.stat().st_size for path, _ in excluded if path.exists())
        print(f"除外: {len(excluded):,}ファイル / {excluded_size / 1024 / 1024:,.2f} MiB")
    if unresolved:
        print("見つからなかった参照（実行時生成ファイルを含む場合があります）:")
        for value in unresolved:
            print(f"  - {value}")
    sys.stdout.flush()


def _format_size(value: int | float) -> str:
    return f"{value / 1024 / 1024 / 1024:,.2f} GiB"


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}時間{minutes:02d}分"
    if minutes:
        return f"{minutes}分{seconds:02d}秒"
    return f"{seconds}秒"


def _required_free_bytes(source_bytes: int) -> int:
    """Allow for archive headers and small incompressible-data expansion."""
    reserve = max(64 * 1024 * 1024, min(source_bytes // 100, 4 * 1024**3))
    return source_bytes + reserve


def _free_bytes_at(path: Path) -> int:
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return shutil.disk_usage(probe).free


class ProgressReporter:
    def __init__(self, total_bytes: int, interval: float = 2.0):
        self.total_bytes = max(0, total_bytes)
        self.processed_bytes = 0
        self.started = time.monotonic()
        self.last_report = 0.0
        self.interval = interval

    def advance(self, amount: int, relative_path: str):
        self.processed_bytes += amount
        now = time.monotonic()
        complete = self.total_bytes == 0 or self.processed_bytes >= self.total_bytes
        if not complete and now - self.last_report < self.interval:
            return
        self.last_report = now
        elapsed = max(now - self.started, 0.001)
        speed = self.processed_bytes / elapsed
        remaining = max(self.total_bytes - self.processed_bytes, 0)
        eta = remaining / speed if speed else 0
        percent = 100.0 if self.total_bytes == 0 else min(
            self.processed_bytes * 100 / self.total_bytes, 100.0)
        print(
            f"進捗: {percent:5.1f}% | "
            f"{_format_size(self.processed_bytes)} / {_format_size(self.total_bytes)} | "
            f"{speed / 1024 / 1024:,.1f} MiB/秒 | "
            f"残り目安 {_format_duration(eta)} | {relative_path}",
            flush=True,
        )

    @staticmethod
    def volume_complete(name: str, size: int):
        print(f"分割ファイル完成: {name} ({_format_size(size)})", flush=True)


def _write_zip_volume(
        package_root: Path, number: int, paths: list[Path], source_root: Path,
        progress: ProgressReporter | None = None):
    name = f"volume-{number:04d}.zip"
    destination = package_root / name
    records = []
    with zipfile.ZipFile(
            destination, "w", compression=zipfile.ZIP_DEFLATED,
            compresslevel=6, allowZip64=True) as archive:
        for path in paths:
            relative_path = _relative(path, source_root)
            digest = hashlib.sha256()
            with path.open("rb") as source, archive.open(relative_path, "w", force_zip64=True) as target:
                for block in iter(lambda: source.read(BUFFER_SIZE), b""):
                    digest.update(block)
                    target.write(block)
                    if progress:
                        progress.advance(len(block), relative_path)
            stat = path.stat()
            records.append({
                "relative_path": relative_path,
                "size": stat.st_size,
                "sha256": digest.hexdigest(),
                "mtime_utc": dt.datetime.fromtimestamp(
                    stat.st_mtime, dt.timezone.utc).isoformat().replace("+00:00", "Z"),
                "storage": {"kind": "zip", "volume": name, "entry": relative_path},
            })
    volume = {
        "name": name,
        "size": destination.stat().st_size,
        "sha256": _sha256(destination),
        "kind": "zip",
    }
    if progress:
        progress.volume_complete(name, volume["size"])
    return records, volume


def _write_chunked_file(
        package_root: Path, file_number: int, path: Path, source_root: Path,
        max_volume_bytes: int, progress: ProgressReporter | None = None):
    chunk_input_size = max_volume_bytes - CHUNK_HEADROOM
    if chunk_input_size <= 0:
        raise ValueError("分割上限が小さすぎます。4 MiB以上を指定してください。")
    file_digest = hashlib.sha256()
    chunks = []
    relative_path = _relative(path, source_root)
    with path.open("rb") as source:
        part = 0
        while True:
            block = source.read(min(BUFFER_SIZE, chunk_input_size))
            if not block:
                break
            part += 1
            name = f"large-{file_number:04d}-part-{part:04d}.gz"
            destination = package_root / name
            remaining = chunk_input_size
            with gzip.GzipFile(
                    filename=str(destination), mode="wb", compresslevel=6, mtime=0) as target:
                while block:
                    file_digest.update(block)
                    target.write(block)
                    if progress:
                        progress.advance(len(block), relative_path)
                    remaining -= len(block)
                    if remaining <= 0:
                        break
                    block = source.read(min(BUFFER_SIZE, remaining))
            if destination.stat().st_size > max_volume_bytes:
                raise RuntimeError(f"分割片が指定上限を超えました: {name}")
            chunks.append({
                "name": name,
                "size": destination.stat().st_size,
                "sha256": _sha256(destination),
            })
            if progress:
                progress.volume_complete(name, destination.stat().st_size)
    stat = path.stat()
    record = {
        "relative_path": relative_path,
        "size": stat.st_size,
        "sha256": file_digest.hexdigest(),
        "mtime_utc": dt.datetime.fromtimestamp(
            stat.st_mtime, dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "storage": {"kind": "gzip_chunks", "chunks": chunks},
    }
    volumes = [dict(chunk, kind="gzip_chunk") for chunk in chunks]
    return record, volumes


def create_package(
        files: list[Path], source_root: Path, output: Path, package_type: str,
        max_volume_mib: int, metadata: dict | None = None):
    source_root = source_root.resolve()
    output = output.resolve()
    max_volume_bytes = int(max_volume_mib) * 1024 * 1024
    if max_volume_bytes < 4 * 1024 * 1024:
        raise ValueError("max-volume-mibは4以上を指定してください。")
    if output.exists():
        if not output.is_dir():
            raise FileExistsError(f"出力先がフォルダではありません: {output}")
        if any(output.iterdir()):
            raise FileExistsError(f"出力先が空ではありません: {output}")
    files = sorted(set(path.resolve() for path in files), key=lambda p: str(p).casefold())
    total_source_bytes = sum(path.stat().st_size for path in files)
    required_free = _required_free_bytes(total_source_bytes)
    available_free = _free_bytes_at(output)
    if available_free < required_free:
        raise RuntimeError(
            "バックアップ保存先の空き容量が不足しています。\n"
            f"必要目安: {_format_size(required_free)}\n"
            f"現在の空き: {_format_size(available_free)}\n"
            "別の保存先を選ぶか、空き容量を増やしてください。"
        )
    print(
        f"バックアップ開始: {len(files):,}ファイル / {_format_size(total_source_bytes)}\n"
        f"保存先空き容量: {_format_size(available_free)}",
        flush=True,
    )
    output.mkdir(parents=True, exist_ok=True)
    progress = ProgressReporter(total_source_bytes)
    records, volumes = [], []
    batch, batch_size = [], 0
    zip_headroom = min(ZIP_HEADROOM, max_volume_bytes // 16)
    zip_budget = max_volume_bytes - zip_headroom
    zip_number = 0
    large_number = 0

    def flush_batch():
        nonlocal batch, batch_size, zip_number
        if not batch:
            return
        zip_number += 1
        new_records, volume = _write_zip_volume(
            output, zip_number, batch, source_root, progress)
        if volume["size"] > max_volume_bytes:
            raise RuntimeError(f"ZIPが指定上限を超えました: {volume['name']}")
        records.extend(new_records)
        volumes.append(volume)
        batch, batch_size = [], 0

    for path in files:
        size = path.stat().st_size
        if size > zip_budget:
            flush_batch()
            large_number += 1
            record, chunk_volumes = _write_chunked_file(
                output, large_number, path, source_root, max_volume_bytes, progress)
            records.append(record)
            volumes.extend(chunk_volumes)
            continue
        if batch and batch_size + size > zip_budget:
            flush_batch()
        batch.append(path)
        batch_size += size
    flush_batch()

    git_commit = ""
    try:
        git_commit = _run_git(source_root, ["rev-parse", "HEAD"]).decode().strip()
    except (RuntimeError, UnicodeError):
        pass
    manifest = {
        "format": "pokecon-portable-package",
        "format_version": FORMAT_VERSION,
        "created_utc": _now_utc(),
        "package_type": package_type,
        "source_root_name": source_root.name,
        "source_git_commit": git_commit,
        "max_volume_bytes": max_volume_bytes,
        "file_count": len(records),
        "source_bytes": sum(record["size"] for record in records),
        "metadata": metadata or {},
        "volumes": volumes,
        "files": records,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tool_root = Path(__file__).resolve().parent
    for name in ("Restore-PokeConPackage.ps1", "Install-PokeConPackage.cmd"):
        source = tool_root / name
        if source.is_file():
            shutil.copy2(source, output / name)
    print(
        f"バックアップ完成: {len(records):,}ファイル / {len(volumes):,}分割\n"
        f"保存先: {output}",
        flush=True,
    )
    return manifest


def _default_output(source_root: Path, kind: str, label: str = "") -> Path:
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{label}" if label else ""
    return source_root.parent / "PokeCon_Portable_Packages" / f"{kind}{suffix}_{timestamp}"


def _resolve_command(source_root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    direct = (Path.cwd() / candidate).resolve()
    if direct.exists():
        return direct
    return (source_root / "SerialController" / "Commands" / "PythonCommands" / candidate).resolve()


def build_parser():
    parser = argparse.ArgumentParser(
        description="PokeConのローカルデータ／指定Commandsを分割・検証可能な形で固めます。")
    parser.add_argument(
        "--source-root", type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Poke-Controller-Modified-Extension-masterフォルダ")
    subparsers = parser.add_subparsers(dest="action", required=True)

    local = subparsers.add_parser("local", help="Git管理外ローカルデータを固める")
    local.add_argument("--profile", choices=(
        "migration", "command-recordings", "complete"), default="migration")
    local.add_argument("--output", type=Path)
    local.add_argument("--max-volume-mib", type=int, default=DEFAULT_MAX_VOLUME_MIB)
    local.add_argument("--dry-run", action="store_true")

    command = subparsers.add_parser("command", help="指定Commandsと必要リソースを固める")
    command.add_argument("--command", required=True, help="PythonCommandsからの相対パスまたは絶対パス")
    command.add_argument("--asset-mode", choices=("safe", "minimal"), default="safe")
    command.add_argument("--output", type=Path)
    command.add_argument("--max-volume-mib", type=int, default=DEFAULT_MAX_VOLUME_MIB)
    command.add_argument("--dry-run", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    source_root = args.source_root.resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"対象ルートが見つかりません: {source_root}")

    if args.action == "local":
        output = (args.output or _default_output(source_root, "local", args.profile)).resolve()
        files, excluded = collect_local_files(source_root, args.profile, output)
        print_inventory(files, source_root, excluded=excluded)
        if args.dry_run:
            print("ドライランのため、パッケージは作成していません。")
            return 0
        manifest = create_package(
            files, source_root, output, f"local-{args.profile}", args.max_volume_mib,
            {"profile": args.profile, "excluded_count": len(excluded)})
    else:
        command = _resolve_command(source_root, args.command)
        output = (args.output or _default_output(source_root, "command", command.stem)).resolve()
        files, unresolved = collect_command_files(source_root, command, args.asset_mode)
        print_inventory(files, source_root, unresolved=unresolved)
        if args.dry_run:
            print("ドライランのため、パッケージは作成していません。")
            return 0
        manifest = create_package(
            files, source_root, output, "command", args.max_volume_mib,
            {"command": _relative(command, source_root), "asset_mode": args.asset_mode,
             "unresolved_references": unresolved})

    package_size = sum(volume["size"] for volume in manifest["volumes"])
    print(f"作成完了: {output}")
    print(f"  {manifest['file_count']:,}ファイル / {len(manifest['volumes']):,}分割")
    print(f"  パッケージ容量: {package_size / 1024 / 1024:,.2f} MiB")
    print("復元例:")
    print(f"  powershell -ExecutionPolicy Bypass -File \"{output / 'Restore-PokeConPackage.ps1'}\" -TargetRoot <復元先>")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        raise SystemExit(1)
