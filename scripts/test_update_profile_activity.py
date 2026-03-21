import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

_module_path = Path(__file__).resolve().parent / "update_profile_activity.py"
_update_profile_activity = SourceFileLoader(
    "update_profile_activity",
    str(_module_path),
).load_module()
replace_latest_repo_section = _update_profile_activity.replace_latest_repo_section
START_MARKER = _update_profile_activity.START_MARKER
END_MARKER = _update_profile_activity.END_MARKER
class TestUpdateProfileActivity(unittest.TestCase):
    def test_replace_latest_repo_section_success(self):
        readme_text = f"Header\n{START_MARKER}\nOld Content\n{END_MARKER}\nFooter"
        repo_lines = ["- Repo 1", "- Repo 2"]
        expected_body = "\n".join(repo_lines)
        expected = f"Header\n{START_MARKER}\n{expected_body}\n{END_MARKER}\nFooter"
        result = replace_latest_repo_section(readme_text, repo_lines)
        self.assertEqual(result, expected)

    def test_replace_latest_repo_section_empty_repos(self):
        readme_text = f"Header\n{START_MARKER}\nOld Content\n{END_MARKER}\nFooter"
        repo_lines = []
        expected_body = "- No recent repos right now."
        expected = f"Header\n{START_MARKER}\n{expected_body}\n{END_MARKER}\nFooter"
        result = replace_latest_repo_section(readme_text, repo_lines)
        self.assertEqual(result, expected)

    def test_replace_latest_repo_section_missing_markers(self):
        readme_text = "No markers here"
        with self.assertRaises(ValueError):
            replace_latest_repo_section(readme_text, ["- Repo 1"])

    def test_replace_latest_repo_section_out_of_order(self):
        readme_text = f"{END_MARKER}\n{START_MARKER}"
        with self.assertRaises(ValueError):
            replace_latest_repo_section(readme_text, ["- Repo 1"])

    def test_replace_latest_repo_section_unrelated_early_end_marker(self):
        # An unrelated END_MARKER appears before the valid START_MARKER/END_MARKER pair.
        readme_text = (
            f"Intro section\n"
            f"{END_MARKER}\n"
            f"Some other content\n"
            f"{START_MARKER}\n"
            f"Old Content\n"
            f"{END_MARKER}\n"
            f"Footer section"
        )
        with self.assertRaises(ValueError):
            replace_latest_repo_section(readme_text, ["- Repo 1"])
if __name__ == "__main__":
    unittest.main()
