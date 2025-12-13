"""Tests for the Reviewedness metric."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from acme_cli.metrics.reviewedness import ReviewednessMetric, GitHubClient
from acme_cli.types import (
    LocalRepository,
    MetricResult,
    ModelContext,
    ModelMetadata,
    RepoFile,
    ScoreTarget,
)


def _create_model_context(
    tmp_path: Path,
    code_urls: list[str] | None = None,
) -> ModelContext:
    """Helper to create a model context with optional code URLs."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True, exist_ok=True)

    return ModelContext(
        target=ScoreTarget(
            model_url="https://huggingface.co/test/model",
            code_urls=code_urls or [],
        ),
        model_metadata=ModelMetadata(
            repo_id="test/model",
            display_name="model",
            card_data={},
            downloads=100,
            likes=10,
            last_modified=datetime.now(),
            tags=[],
            files=[],
            pipeline_tag=None,
            library_name=None,
        ),
        dataset_metadata=None,
        local_repo=LocalRepository(
            repo_id="test/model",
            repo_type="model",
            path=repo_path,
        ),
        dataset_local_repo=None,
        readme_text=None,
        dataset_readme_text=None,
        commit_authors=[],
        commit_total=0,
    )


class TestGitHubClient:
    """Tests for GitHubClient."""

    def test_client_initialization(self):
        """Test client can be initialized with and without token."""
        client1 = GitHubClient()
        assert client1.token is None or isinstance(client1.token, str)

        client2 = GitHubClient(token="test_token")
        assert client2.token == "test_token"

    @patch("acme_cli.metrics.reviewedness.GitHubClient._get_session")
    def test_get_pull_requests(self, mock_get_session):
        """Test fetching pull requests."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        # Mock response that returns data on first call, empty on second (pagination)
        prs_data = [
            {"number": 1, "merged_at": "2023-01-01T00:00:00Z", "review_comments": 2},
            {"number": 2, "merged_at": None, "review_comments": 0},  # Not merged
        ]

        mock_response = MagicMock()
        mock_response.json.side_effect = [
            prs_data,
            [],
        ]  # First page has data, second is empty
        mock_session.get.return_value = mock_response

        client = GitHubClient()
        prs = client.get_pull_requests("owner", "repo", state="closed")

        assert len(prs) == 2
        assert prs[0]["number"] == 1
        mock_session.get.assert_called()

    @patch("acme_cli.metrics.reviewedness.GitHubClient._get_session")
    def test_get_commits_by_pr(self, mock_get_session):
        """Test fetching commits in a PR."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        commits_data = [
            {"sha": "abc123", "commit": {"message": "fix: bug"}},
            {"sha": "def456", "commit": {"message": "feat: feature"}},
        ]

        mock_response = MagicMock()
        mock_response.json.side_effect = [commits_data, []]  # First page, then empty
        mock_session.get.return_value = mock_response

        client = GitHubClient()
        commits = client.get_commits_by_pr("owner", "repo", 1)

        assert len(commits) == 2
        assert commits[0]["sha"] == "abc123"


class TestReviewednessMetric:
    """Tests for ReviewednessMetric."""

    def test_no_code_urls(self, tmp_path):
        """Test metric returns -1 when no code URLs provided."""
        metric = ReviewednessMetric()
        context = _create_model_context(tmp_path, code_urls=[])

        score = metric.compute(context)
        assert score == -1.0

    def test_non_github_code_urls(self, tmp_path):
        """Test metric returns -1 when code URLs are not GitHub."""
        metric = ReviewednessMetric()
        context = _create_model_context(
            tmp_path,
            code_urls=["https://gitlab.com/owner/repo"],
        )

        score = metric.compute(context)
        assert score == -1.0

    def test_extract_github_repos(self, tmp_path):
        """Test extraction of GitHub repositories from URLs."""
        metric = ReviewednessMetric()
        context = _create_model_context(
            tmp_path,
            code_urls=[
                "https://github.com/torvalds/linux",
                "https://github.com/pytorch/pytorch",
                "https://gitlab.com/owner/repo",  # Should be ignored
                "https://huggingface.co/models",  # Should be ignored
            ],
        )

        repos = metric._extract_github_repos(context)
        assert len(repos) == 2
        assert ("torvalds", "linux") in repos
        assert ("pytorch", "pytorch") in repos

    @patch("acme_cli.metrics.reviewedness.ReviewednessMetric._compute_repo_score")
    def test_single_github_repo(self, mock_compute_score, tmp_path):
        """Test metric with single GitHub repository."""
        mock_compute_score.return_value = 0.85

        metric = ReviewednessMetric()
        context = _create_model_context(
            tmp_path,
            code_urls=["https://github.com/owner/repo"],
        )

        score = metric.compute(context)
        assert score == 0.85
        mock_compute_score.assert_called_once_with("owner", "repo")

    @patch("acme_cli.metrics.reviewedness.ReviewednessMetric._compute_repo_score")
    def test_multiple_github_repos_average(self, mock_compute_score, tmp_path):
        """Test metric returns average score for multiple repos."""
        # First call returns 0.8, second returns 0.6
        mock_compute_score.side_effect = [0.8, 0.6]

        metric = ReviewednessMetric()
        context = _create_model_context(
            tmp_path,
            code_urls=[
                "https://github.com/owner1/repo1",
                "https://github.com/owner2/repo2",
            ],
        )

        score = metric.compute(context)
        assert abs(score - 0.7) < 0.01  # Average of 0.8 and 0.6

    @patch("acme_cli.metrics.reviewedness.ReviewednessMetric._compute_repo_score")
    def test_multiple_repos_some_invalid(self, mock_compute_score, tmp_path):
        """Test that invalid scores (-1) are excluded from averaging."""
        # First returns valid, second returns -1 (no data), third returns valid
        mock_compute_score.side_effect = [0.8, -1.0, 0.4]

        metric = ReviewednessMetric()
        context = _create_model_context(
            tmp_path,
            code_urls=[
                "https://github.com/owner1/repo1",
                "https://github.com/owner2/repo2",
                "https://github.com/owner3/repo3",
            ],
        )

        score = metric.compute(context)
        # Average of 0.8 and 0.4, skipping -1
        assert abs(score - 0.6) < 0.01

    @patch.object(GitHubClient, "get_pull_requests")
    @patch.object(GitHubClient, "get_commits_by_pr")
    def test_compute_repo_score_all_reviewed(self, mock_commits, mock_prs):
        """Test repo score when all PRs are reviewed."""
        # Mock two merged PRs, both with reviews
        mock_prs.return_value = [
            {
                "number": 1,
                "merged_at": "2023-01-01T00:00:00Z",
                "review_comments": 2,
                "requested_reviewers": ["user1"],
            },
            {
                "number": 2,
                "merged_at": "2023-01-02T00:00:00Z",
                "review_comments": 1,
            },
        ]

        # Each PR has 5 commits
        mock_commits.return_value = [{"sha": f"commit{i}"} for i in range(5)]

        metric = ReviewednessMetric()
        score = metric._compute_repo_score("owner", "repo")

        # All 10 commits (2 PRs * 5 commits) went through review
        assert score == 1.0

    @patch.object(GitHubClient, "get_pull_requests")
    @patch.object(GitHubClient, "get_commits_by_pr")
    def test_compute_repo_score_partial_reviewed(self, mock_commits, mock_prs):
        """Test repo score when only some PRs are reviewed."""
        # Two merged PRs, one with review and one without
        mock_prs.return_value = [
            {
                "number": 1,
                "merged_at": "2023-01-01T00:00:00Z",
                "review_comments": 2,
                "requested_reviewers": ["user1"],
            },
            {
                "number": 2,
                "merged_at": "2023-01-02T00:00:00Z",
                "review_comments": 0,
                "requested_reviewers": [],
            },
        ]

        # First PR has 4 commits, second has 6
        def commits_side_effect(owner, repo, pr_num):
            if pr_num == 1:
                return [{"sha": f"c{i}"} for i in range(4)]
            else:
                return [{"sha": f"c{i}"} for i in range(6)]

        mock_commits.side_effect = commits_side_effect

        metric = ReviewednessMetric()
        score = metric._compute_repo_score("owner", "repo")

        # 4 out of 10 commits went through review
        assert abs(score - 0.4) < 0.01

    @patch.object(GitHubClient, "get_pull_requests")
    def test_compute_repo_score_no_prs(self, mock_prs):
        """Test repo score when repository has no PRs."""
        mock_prs.return_value = []

        metric = ReviewednessMetric()
        score = metric._compute_repo_score("owner", "repo")

        assert score == 0.0

    @patch.object(GitHubClient, "get_pull_requests")
    def test_compute_repo_score_all_unmerged(self, mock_prs):
        """Test repo score when all PRs are closed but not merged."""
        mock_prs.return_value = [
            {
                "number": 1,
                "merged_at": None,  # Not merged
                "review_comments": 2,
            },
        ]

        metric = ReviewednessMetric()
        score = metric._compute_repo_score("owner", "repo")

        assert score == 0.0

    @patch.object(GitHubClient, "get_pull_requests")
    def test_compute_repo_score_error_handling(self, mock_prs):
        """Test that errors are handled gracefully."""
        mock_prs.side_effect = Exception("Network error")

        metric = ReviewednessMetric()
        score = metric._compute_repo_score("owner", "repo")

        # Should return conservative score on error
        assert score == 0.0

    def test_metric_name(self):
        """Test metric name is set correctly."""
        metric = ReviewednessMetric()
        assert metric.name == "reviewedness"
