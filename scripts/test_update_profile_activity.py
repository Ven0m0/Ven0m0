import unittest
from unittest.mock import MagicMock, patch

from scripts.update_profile_activity import (
    replace_repo_section as replace_latest_repo_section,
    LATEST_START_MARKER as START_MARKER,
    LATEST_END_MARKER as END_MARKER,
    RepoEntry,
    GitHubClient,
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
    def test_to_markdown(self):
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




class TestGitHubClientValidRepo(unittest.TestCase):
    def setUp(self):
        self.client = GitHubClient("testuser")

    def test_is_valid_repo_archived(self):
        self.assertFalse(self.client._is_valid_repo({"archived": True}, "repo1"))

    def test_is_valid_repo_disabled(self):
        self.assertFalse(self.client._is_valid_repo({"disabled": True}, "repo1"))

    def test_is_valid_repo_fork(self):
        self.assertFalse(self.client._is_valid_repo({"fork": True}, "repo1"))

    def test_is_valid_repo_dot_github(self):
        self.assertFalse(self.client._is_valid_repo({}, ".github"))

    def test_is_valid_repo_self_named(self):
        self.assertFalse(self.client._is_valid_repo({}, "testuser"))
        self.assertFalse(self.client._is_valid_repo({}, "TestUser"))

    def test_is_valid_repo_valid(self):
        self.assertTrue(self.client._is_valid_repo({"archived": False, "disabled": False, "fork": False}, "normal-repo"))

    @patch.object(GitHubClient, '_request_json')
    def test_fetch_repos_filtering(self, mock_request_json):
        mock_repos = [
            {"name": "valid-repo", "html_url": "url1", "pushed_at": "date1", "stargazers_count": 1},
            {"name": ".github", "html_url": "url2", "pushed_at": "date2", "stargazers_count": 2},
            {"name": "forked-repo", "fork": True, "html_url": "url3", "pushed_at": "date3", "stargazers_count": 3},
            {"name": "testuser", "html_url": "url4", "pushed_at": "date4", "stargazers_count": 4},
        ]
        mock_request_json.side_effect = [mock_repos, []]

        repos = self.client.fetch_repos()

        self.assertEqual(len(repos), 1)
        self.assertEqual(repos[0].name, "valid-repo")

if __name__ == "__main__":
    unittest.main()
