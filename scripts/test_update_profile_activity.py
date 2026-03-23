import unittest
from scripts.update_profile_activity import replace_latest_repo_section, START_MARKER, END_MARKER
class TestUpdateProfileActivity(unittest.TestCase):
    def test_replace_successful(self):
        readme_text = f"Header\n{START_MARKER}\nOld content\n{END_MARKER}\nFooter"
        repo_lines = ["- Repo 1", "- Repo 2"]
        expected = f"Header\n{START_MARKER}\n- Repo 1\n- Repo 2\n{END_MARKER}\nFooter"
        result = replace_latest_repo_section(readme_text, repo_lines)
        self.assertEqual(result, expected)

    def test_replace_marker_errors(self):
        repo_lines = ["- Repo 1"]
        error_message = "Required README markers are missing or out of order."
        test_cases = {
            "missing_start_marker": f"Header\nOld content\n{END_MARKER}\nFooter",
            "missing_end_marker": f"Header\n{START_MARKER}\nOld content\nFooter",
            "markers_out_of_order": f"Header\n{END_MARKER}\nOld content\n{START_MARKER}\nFooter",
        }
        for name, readme_text in test_cases.items():
            with self.subTest(msg=name):
                with self.assertRaisesRegex(ValueError, error_message):
                    replace_latest_repo_section(readme_text, repo_lines)

    def test_replace_empty_repo_lines(self):
        readme_text = f"Header\n{START_MARKER}\nOld content\n{END_MARKER}\nFooter"
        repo_lines = []
        expected = f"Header\n{START_MARKER}\n- No recent repos right now.\n{END_MARKER}\nFooter"
        result = replace_latest_repo_section(readme_text, repo_lines)
        self.assertEqual(result, expected)

if __name__ == "__main__":
    unittest.main()
