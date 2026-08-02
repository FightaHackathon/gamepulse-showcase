import unittest
from pathlib import Path


class ImportCompatibilityTests(unittest.TestCase):
    def test_catalog_dataclasses_load_when_runtime_does_not_pre_register_module(self):
        """Protect the Streamlit Cloud import boundary used by the failing app."""
        source_path = Path(__file__).parents[1] / "gamepulse" / "catalog.py"
        namespace = {
            "__name__": "gamepulse_catalog_cloud_loader",
            "__file__": str(source_path),
        }

        exec(compile(source_path.read_text(encoding="utf-8"), str(source_path), "exec"), namespace)

        self.assertIn("GameSummary", namespace)
        self.assertIn("PreferenceOptions", namespace)


if __name__ == "__main__":
    unittest.main()
