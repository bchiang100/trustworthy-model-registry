#!/usr/bin/env python3
"""
Example demonstrating the Reviewedness metric.

This script shows how the Reviewedness metric measures the fraction of code
introduced through reviewed pull requests in a linked GitHub repository.

Scoring:
- 1.0: All code contributions came through reviewed PRs
- 0.0: No code came through reviewed PRs (or no GitHub repo linked)
- -1.0: No GitHub repository linked in code_urls
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from acme_cli.metrics.reviewedness import ReviewednessMetric, GitHubClient
from acme_cli.types import (
    LocalRepository,
    ModelContext,
    ModelMetadata,
    RepoFile,
    ScoreTarget,
)


def create_model_context(code_urls: list[str]) -> ModelContext:
    """Create a model context with code URLs."""
    return ModelContext(
        target=ScoreTarget(
            model_url="https://huggingface.co/test/model",
            code_urls=code_urls,
        ),
        model_metadata=ModelMetadata(
            repo_id="test/model",
            display_name="model",
            card_data={},
            downloads=1000,
            likes=100,
            last_modified=datetime.now(),
            tags=["nlp", "transformers"],
            files=[],
            pipeline_tag="text-classification",
            library_name="transformers",
        ),
        dataset_metadata=None,
        local_repo=LocalRepository(
            repo_id="test/model",
            repo_type="model",
            path=None,
        ),
        dataset_local_repo=None,
        readme_text=None,
        dataset_readme_text=None,
        commit_authors=["alice", "bob"],
        commit_total=100,
    )


def example_1_no_github_repo():
    """Example 1: Model with no GitHub repository linked."""
    print("\n" + "=" * 70)
    print("Example 1: No GitHub Repository Linked")
    print("=" * 70)

    metric = ReviewednessMetric()

    context = create_model_context(
        code_urls=[
            "https://huggingface.co/fine-tuned-model",
            "https://example.com/documentation",
        ]
    )

    score = metric.compute(context)

    print("\nCode URLs: (no GitHub repositories)")
    print(f"  - https://huggingface.co/fine-tuned-model")
    print(f"  - https://example.com/documentation")
    print(f"\nReviewedness Score: {score}")
    print(f"Interpretation: No GitHub repository found -> return -1.0")


def example_2_all_code_reviewed():
    """Example 2: All code contributions came through reviewed PRs."""
    print("\n" + "=" * 70)
    print("Example 2: All Code Contributions Reviewed")
    print("=" * 70)

    context = create_model_context(
        code_urls=["https://github.com/huggingface/transformers"]
    )

    # Mock the GitHub client
    mock_client = MagicMock(spec=GitHubClient)

    # Mock PR data - 2 merged PRs, both with reviews
    merged_prs = [
        {
            "number": 1,
            "merged_at": "2023-01-01T00:00:00Z",
            "review_comments": 5,
            "requested_reviewers": ["reviewer1", "reviewer2"],
        },
        {
            "number": 2,
            "merged_at": "2023-01-15T00:00:00Z",
            "review_comments": 3,
            "requested_reviewers": ["reviewer1"],
        },
    ]
    mock_client.get_pull_requests.return_value = merged_prs

    # Each PR has 10 commits
    mock_client.get_commits_by_pr.return_value = [{"sha": f"c{i}"} for i in range(10)]

    metric = ReviewednessMetric(github_client=mock_client)
    score = metric.compute(context)

    print("\nRepository: https://github.com/huggingface/transformers")
    print("\nMerged PRs with Reviews:")
    print(f"  PR #1: 5 review comments, 2 requested reviewers, 10 commits")
    print(f"  PR #2: 3 review comments, 1 requested reviewer, 10 commits")
    print(f"\nTotal Commits: 20")
    print(f"Reviewed Commits: 20 (100%)")
    print(f"\nReviewedness Score: {score:.2f}")
    print(f"Interpretation: All code went through code review")


def example_3_partial_code_reviewed():
    """Example 3: Only some code contributions came through reviewed PRs."""
    print("\n" + "=" * 70)
    print("Example 3: Partial Code Review Coverage")
    print("=" * 70)

    context = create_model_context(code_urls=["https://github.com/pytorch/pytorch"])

    # Mock the GitHub client
    mock_client = MagicMock(spec=GitHubClient)

    # Mock PR data - 3 merged PRs
    # PR 1: Reviewed (5 commits)
    # PR 2: Not reviewed (3 commits)
    # PR 3: Reviewed (7 commits)
    merged_prs = [
        {
            "number": 1,
            "merged_at": "2023-01-01T00:00:00Z",
            "review_comments": 4,
            "requested_reviewers": ["reviewer1"],
        },
        {
            "number": 2,
            "merged_at": "2023-01-10T00:00:00Z",
            "review_comments": 0,
            "requested_reviewers": [],
        },
        {
            "number": 3,
            "merged_at": "2023-01-20T00:00:00Z",
            "review_comments": 6,
            "requested_reviewers": ["reviewer2", "reviewer3"],
        },
    ]
    mock_client.get_pull_requests.return_value = merged_prs

    # Different commit counts per PR
    def get_commits(owner, repo, pr_num):
        counts = {1: 5, 2: 3, 3: 7}
        return [{"sha": f"c{i}"} for i in range(counts.get(pr_num, 0))]

    mock_client.get_commits_by_pr.side_effect = get_commits

    metric = ReviewednessMetric(github_client=mock_client)
    score = metric.compute(context)

    print("\nRepository: https://github.com/pytorch/pytorch")
    print("\nMerged PRs:")
    print(f"  PR #1: 4 review comments, 1 reviewer - 5 commits [REVIEWED]")
    print(f"  PR #2: 0 review comments, 0 reviewers - 3 commits [NOT REVIEWED]")
    print(f"  PR #3: 6 review comments, 2 reviewers - 7 commits [REVIEWED]")
    print(f"\nTotal Commits: 15")
    print(f"Reviewed Commits: 12 (80%)")
    print(f"\nReviewedness Score: {score:.2f}")
    print(f"Interpretation: {score*100:.0f}% of code went through code review")


def example_4_multiple_github_repos():
    """Example 4: Model with multiple GitHub repositories."""
    print("\n" + "=" * 70)
    print("Example 4: Multiple GitHub Repositories (Average Score)")
    print("=" * 70)

    context = create_model_context(
        code_urls=[
            "https://github.com/openai/gpt-2",
            "https://github.com/huggingface/transformers",
        ]
    )

    # Mock the GitHub client
    mock_client = MagicMock(spec=GitHubClient)

    def get_prs(owner, repo, state="closed"):
        # GPT-2 repo: 100% reviewed (5 PRs, all reviewed)
        if repo == "gpt-2":
            return [
                {
                    "number": i,
                    "merged_at": "2023-01-01T00:00:00Z",
                    "review_comments": 3,
                }
                for i in range(1, 6)
            ]
        # Transformers repo: 50% reviewed (4 PRs, 2 reviewed)
        else:
            return [
                {
                    "number": i,
                    "merged_at": "2023-01-01T00:00:00Z",
                    "review_comments": 2 if i <= 2 else 0,
                }
                for i in range(1, 5)
            ]

    mock_client.get_pull_requests.side_effect = get_prs
    mock_client.get_commits_by_pr.return_value = [{"sha": f"c{i}"} for i in range(5)]

    metric = ReviewednessMetric(github_client=mock_client)
    score = metric.compute(context)

    print("\nRepositories:")
    print(f"  - https://github.com/openai/gpt-2")
    print(f"    → 5 PRs, all reviewed → Score: 1.0")
    print(f"\n  - https://github.com/huggingface/transformers")
    print(f"    → 4 PRs, 2 reviewed → Score: 0.5")
    print(f"\nReviewedness Score: {score:.2f}")
    print(f"Interpretation: Average of repo scores = (1.0 + 0.5) / 2 = 0.75")


def example_5_no_prs():
    """Example 5: Repository with no pull requests."""
    print("\n" + "=" * 70)
    print("Example 5: Repository with No Pull Requests")
    print("=" * 70)

    context = create_model_context(code_urls=["https://github.com/example/repository"])

    # Mock the GitHub client
    mock_client = MagicMock(spec=GitHubClient)
    mock_client.get_pull_requests.return_value = []  # No PRs

    metric = ReviewednessMetric(github_client=mock_client)
    score = metric.compute(context)

    print("\nRepository: https://github.com/example/repository")
    print(f"\nMerged PRs: 0")
    print(f"\nReviewedness Score: {score:.2f}")
    print(f"Interpretation: No pull requests found -> conservative score of 0.0")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("Reviewedness Metric Examples")
    print("=" * 70)
    print("\nMeasures the fraction of code introduced through reviewed PRs")

    example_1_no_github_repo()
    example_2_all_code_reviewed()
    example_3_partial_code_reviewed()
    example_4_multiple_github_repos()
    example_5_no_prs()

    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
