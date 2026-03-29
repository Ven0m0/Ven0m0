import unittest
from scripts.update_profile_activity import (
    replace_repo_section as replace_latest_repo_section,
    LATEST_START_MARKER as START_MARKER,
    LATEST_END_MARKER as END_MARKER,
    RepoEntry,
)
class TestUpdateProfileActivity(unittest.TestCase):
    def test_replace_successful(self):
        readme_text = f"Header\n{START_MARKER}\nOld content\n{END_MARKER}\nFooter"
        repo_lines = ["- Repo 1", "- Repo 2"]
        expected = f"Header\n{START_MARKER}\n- Repo 1\n- Repo 2\n{END_MARKER}\nFooter"
        result = replace_latest_repo_section(readme_text, START_MARKER, END_MARKER, repo_lines, '- No recent repos right now.')
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
                    replace_latest_repo_section(readme_text, START_MARKER, END_MARKER, repo_lines, '- No recent repos right now.')

    def test_replace_empty_repo_lines(self):
        readme_text = f"Header\n{START_MARKER}\nOld content\n{END_MARKER}\nFooter"
        repo_lines = []
        expected = f"Header\n{START_MARKER}\n- No recent repos right now.\n{END_MARKER}\nFooter"
        result = replace_latest_repo_section(readme_text, START_MARKER, END_MARKER, repo_lines, '- No recent repos right now.')
        self.assertEqual(result, expected)


class TestRepoEntry(unittest.TestCase):
    def test_to_markdown_basic(self):
        entry = RepoEntry(
            name="test-repo",
            html_url="https://github.com/user/test-repo",
            description="A test repository",
            pushed_at="2023-10-27T10:00:00Z",
            stargazers_count=0
        )
        expected = "- [test-repo](https://github.com/user/test-repo) — A test repository <sub>2023-10-27</sub>"
        self.assertEqual(entry.to_markdown(), expected)

    def test_to_markdown_html_escape(self):
        entry = RepoEntry(
            name="<test & repo>",
            html_url="https://github.com/user/test-repo",
            description="<script>alert(1)</script> & more",
            pushed_at="2023-10-27T10:00:00Z",
            stargazers_count=0
        )
        expected = "- [&lt;test &amp; repo&gt;](https://github.com/user/test-repo) — &lt;script&gt;alert(1)&lt;/script&gt; &amp; more <sub>2023-10-27</sub>"
        self.assertEqual(entry.to_markdown(), expected)


if __name__ == "__main__":
    unittest.main()
