import codecs
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile


REPOSITORY = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY / "PortablePackageTool" / "Apply-PokeConCompatibilityFixes.ps1"


class PortableCompatibilityTests(unittest.TestCase):
    def test_compatibility_script_keeps_windows_powershell_utf8_bom(self):
        self.assertTrue(SCRIPT.read_bytes().startswith(codecs.BOM_UTF8))

    @unittest.skipUnless(shutil.which("powershell.exe"), "Windows PowerShell is required")
    def test_focus_fix_is_targeted_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            serial = root / "SerialController"
            serial.mkdir()
            window = serial / "Window.py"
            gui_assets = serial / "GuiAssets.py"
            window.write_text(
                "def focused(self):\n"
                "    try:\n"
                "        return self.root.focus_displayof() is not None\n"
                "    except tk.TclError:\n"
                "        return False\n\n"
                "def unrelated(self):\n"
                "    try:\n"
                "        return self.root.winfo_exists()\n"
                "    except tk.TclError:\n"
                "        return False\n",
                encoding="utf-8",
            )
            gui_assets.write_text(
                "def capture(self):\n"
                "    try:\n"
                "        focused = self.focus_displayof() is not None\n"
                "    except tk.TclError:\n"
                "        focused = True\n",
                encoding="utf-8",
            )

            command = [
                "powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(SCRIPT), "-TargetRoot", str(root),
            ]
            first = subprocess.run(command, capture_output=True, check=False)
            first_output = (first.stdout + first.stderr).decode("utf-8-sig", "replace")
            self.assertEqual(first.returncode, 0, first_output)
            first_window = window.read_text(encoding="utf-8")
            first_gui = gui_assets.read_text(encoding="utf-8")
            self.assertEqual(first_window.count("except (tk.TclError, KeyError):"), 1)
            self.assertEqual(first_window.count("except tk.TclError:"), 1)
            self.assertEqual(first_gui.count("except (tk.TclError, KeyError):"), 1)
            self.assertIn("(1 ", first_output)

            second = subprocess.run(command, capture_output=True, check=False)
            second_output = (second.stdout + second.stderr).decode("utf-8-sig", "replace")
            self.assertEqual(second.returncode, 0, second_output)
            self.assertEqual(window.read_text(encoding="utf-8"), first_window)
            self.assertEqual(gui_assets.read_text(encoding="utf-8"), first_gui)

    def test_restore_script_has_warning_and_applied_dialogs(self):
        restore = (REPOSITORY / "PortablePackageTool" / "Restore-PokeConPackage.ps1").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("互換修正が戻る可能性", restore)
        self.assertIn("状態: 反映済み", restore)
        self.assertIn("NoCompatibilityDialogs", restore)

    @unittest.skipUnless(shutil.which("powershell.exe"), "Windows PowerShell is required")
    def test_restore_reapplies_fix_after_old_window_is_installed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            target = root / "target"
            package.mkdir()
            (target / "SerialController").mkdir(parents=True)
            destination = target / "SerialController" / "Window.py"
            protected = (
                "try:\n"
                "    focused = self.root.focus_displayof() is not None\n"
                "except (tk.TclError, KeyError):\n"
                "    focused = False\n"
            )
            vulnerable = protected.replace(
                "except (tk.TclError, KeyError):", "except tk.TclError:"
            )
            destination.write_text(protected, encoding="utf-8")

            volume = package / "volume-0001.zip"
            entry = "files/00000001"
            payload = vulnerable.encode("utf-8")
            with zipfile.ZipFile(volume, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(entry, payload)
            manifest = {
                "format": "pokecon-portable-package",
                "format_version": 1,
                "volumes": [{
                    "name": volume.name,
                    "size": volume.stat().st_size,
                    "sha256": hashlib.sha256(volume.read_bytes()).hexdigest(),
                }],
                "files": [{
                    "relative_path": "SerialController/Window.py",
                    "size": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "mtime_utc": "2026-01-01T00:00:00Z",
                    "storage": {"kind": "zip", "volume": volume.name, "entry": entry},
                }],
            }
            (package / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            shutil.copy2(
                REPOSITORY / "PortablePackageTool" / "Apply-PokeConCompatibilityFixes.ps1",
                package,
            )
            restore = REPOSITORY / "PortablePackageTool" / "Restore-PokeConPackage.ps1"
            command = [
                "powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(restore), "-PackageRoot", str(package),
                "-TargetRoot", str(target), "-Overwrite", "Backup",
                "-NoCompatibilityDialogs",
            ]
            result = subprocess.run(command, capture_output=True, check=False)
            output = (result.stdout + result.stderr).decode("utf-8-sig", "replace")
            self.assertEqual(result.returncode, 0, output)
            restored = destination.read_text(encoding="utf-8")
            self.assertIn("except (tk.TclError, KeyError):", restored)
            self.assertEqual(len(list(destination.parent.glob("Window.py.pre_restore_*"))), 1)
            logs = list(target.glob(".pokecon-package-restore-*.log"))
            self.assertEqual(len(logs), 1)
            log_text = logs[0].read_text(encoding="utf-8-sig")
            self.assertIn("互換修正が戻る可能性", log_text)
            self.assertIn("互換修正を適用", log_text)


if __name__ == "__main__":
    unittest.main()
