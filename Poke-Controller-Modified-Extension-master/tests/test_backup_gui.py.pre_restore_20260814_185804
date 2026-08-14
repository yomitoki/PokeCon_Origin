import importlib.util
from pathlib import Path
import unittest


REPOSITORY = Path(__file__).resolve().parents[1]
GUI_PATH = REPOSITORY / "PortablePackageTool" / "backup_gui.py"
SPEC = importlib.util.spec_from_file_location("backup_gui", GUI_PATH)
backup_gui = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup_gui)


class BackupGuiCommandTests(unittest.TestCase):
    def test_local_dry_run_command(self):
        result = backup_gui.build_create_command(
            "python.exe", Path("tool.py"), Path("source"), "migration",
            Path("output"), 1024, dry_run=True)
        self.assertEqual(
            result[:5], ["python.exe", "-u", "tool.py", "--source-root", "source"])
        self.assertIn("migration", result)
        self.assertIn("--dry-run", result)

    def test_command_package_uses_safe_assets(self):
        result = backup_gui.build_create_command(
            "python.exe", Path("tool.py"), Path("source"), "command",
            Path("output"), 512, Path("command.py"), safe_assets=True)
        self.assertIn("command.py", result)
        self.assertEqual(result[result.index("--asset-mode") + 1], "safe")

    def test_restore_defaults_can_be_built(self):
        result = backup_gui.build_restore_command(
            Path("package"), Path("target"), "Backup", verify_only=True)
        self.assertIn("Restore-PokeConPackage.ps1", result[5])
        self.assertIn("Backup", result)
        self.assertEqual(result[-1], "-VerifyOnly")


if __name__ == "__main__":
    unittest.main()
