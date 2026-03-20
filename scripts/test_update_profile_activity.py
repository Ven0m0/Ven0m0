import unittest
from scripts.update_profile_activity import replace_latest_repo_section, START_MARKER, END_MARKER

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

if __name__ == "__main__":
    unittest.main()
