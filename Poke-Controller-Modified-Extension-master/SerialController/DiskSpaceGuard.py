"""Drive-capacity checks shared by recording UI and tests."""
from __future__ import annotations

import os
import shutil


def disk_space_violations(paths, min_free_gb=5.0, max_usage_percent=95.0,
                          usage_provider=shutil.disk_usage):
    """Return threshold violations for the unique drives containing *paths*.

    Recording folders do not have to exist yet; the nearest existing parent
    is used. A query error is a violation because recording without a reliable
    capacity check is unsafe.
    """
    min_free_gb = max(0.0, float(min_free_gb))
    max_usage_percent = min(100.0, max(0.0, float(max_usage_percent)))
    drives = {}
    for label, path in paths:
        requested_path = os.path.abspath(path or os.curdir)
        existing_path = requested_path
        while not os.path.exists(existing_path):
            parent = os.path.dirname(existing_path)
            if parent == existing_path:
                break
            existing_path = parent
        drive, _ = os.path.splitdrive(existing_path)
        drive_key = (drive or os.path.abspath(os.sep)).casefold()
        item = drives.setdefault(drive_key, {
            "labels": [], "path": requested_path, "query_path": existing_path,
        })
        if label not in item["labels"]:
            item["labels"].append(label)

    violations = []
    gib = float(1024 ** 3)
    for drive_key, item in drives.items():
        result = {
            "drive": drive_key,
            "label": " / ".join(item["labels"]),
            "path": item["path"],
        }
        try:
            usage = usage_provider(item["query_path"])
            free_gb = usage.free / gib
            used_percent = 100.0 * usage.used / usage.total if usage.total else 100.0
            result.update(free_gb=free_gb, used_percent=used_percent)
            if free_gb < min_free_gb or used_percent >= max_usage_percent:
                violations.append(result)
        except (OSError, ValueError) as error:
            result["error"] = str(error)
            violations.append(result)
    return violations
