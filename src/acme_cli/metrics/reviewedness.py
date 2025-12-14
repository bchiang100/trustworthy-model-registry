"""Reviewedness metric measuring code review coverage in linked repositories."""
from __future__ import annotations

import logging
from typing import Optional

from acme_cli.metrics.base import Metric
from acme_cli.types import ModelContext
from acme_cli.urls import parse_artifact_url

logger = logging.getLogger(__name__)


class GitHubClient:
    """Simple GitHub API client for PR and commit analysis."""

    def __init__(self, token: Optional[str] = None):
        """Initialize GitHub client.
        
        Args:
            token: Optional GitHub API token for increased rate limits.
        """
        import os
        
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.session = None
        self._api_url = "https://api.github.com"

    def _get_session(self):
        """Lazy-load requests session."""
        if self.session is None:
            import requests
            self.session = requests.Session()
            if self.token:
                self.session.headers.update({"Authorization": f"token {self.token}"})
            self.session.headers.update({"Accept": "application/vnd.github.v3+json"})
        return self.session

    def get_pull_requests(self, owner: str, repo: str, state: str = "closed") -> list[dict]:
        """Get merged pull requests from a repository.

        Optimized to fetch fewer PRs and stop early to avoid rate limiting.

        Args:
            owner: Repository owner
            repo: Repository name
            state: PR state ("closed" for merged, "open", "all")

        Returns:
            List of PR objects from the GitHub API (limited to recent PRs)
        """
        try:
            session = self._get_session()
            url = f"{self._api_url}/repos/{owner}/{repo}/pulls"
            params = {
                "state": state,
                "per_page": 100,  # Max per page
                "sort": "updated",  # Get most recently updated PRs
                "direction": "desc",  # Most recent first
            }

            all_prs = []
            page = 1
            max_pages = 3  # Limit to first 300 PRs to avoid rate limiting

            while page <= max_pages:
                params["page"] = page
                response = session.get(url, params=params, timeout=10)
                response.raise_for_status()
                prs = response.json()

                if not prs:
                    break

                all_prs.extend(prs)
                page += 1

                # Early termination if we hit rate limits or get enough data
                if len(all_prs) >= 200:  # Reasonable sample size
                    break

            logger.debug(f"Fetched {len(all_prs)} PRs for {owner}/{repo}")
            return all_prs
        except Exception as e:
            logger.warning(f"Failed to fetch PRs for {owner}/{repo}: {e}")
            return []

    def get_commits_by_pr(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        """Get commits in a pull request.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            
        Returns:
            List of commit objects
        """
        try:
            session = self._get_session()
            url = f"{self._api_url}/repos/{owner}/{repo}/pulls/{pr_number}/commits"
            params = {"per_page": 100}
            
            all_commits = []
            page = 1
            while True:
                params["page"] = page
                response = session.get(url, params=params, timeout=10)
                response.raise_for_status()
                commits = response.json()
                
                if not commits:
                    break
                    
                all_commits.extend(commits)
                
                if len(all_commits) >= 500:
                    break
                    
                page += 1
            
            return all_commits
        except Exception as e:
            logger.warning(f"Failed to fetch commits for PR #{pr_number}: {e}")
            return []

    def get_repository_stats(self, owner: str, repo: str) -> Optional[dict]:
        """Get basic repository stats (language breakdown, size, etc).

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Repository info dict or None on error
        """
        try:
            session = self._get_session()
            url = f"{self._api_url}/repos/{owner}/{repo}"
            response = session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Failed to fetch repo stats for {owner}/{repo}: {e}")
            return None

    def _get_detailed_pr(self, owner: str, repo: str, pr_number: int) -> Optional[dict]:
        """Get detailed PR information including review comments, commits count, etc.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            Detailed PR dict or None on error
        """
        try:
            session = self._get_session()
            url = f"{self._api_url}/repos/{owner}/{repo}/pulls/{pr_number}"
            response = session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.debug(f"Failed to fetch detailed PR #{pr_number}: {e}")
            return None


class ReviewednessMetric(Metric):
    """Metric measuring fraction of code introduced through reviewed PRs.
    
    Computes the ratio of lines/commits in merged PRs with reviews to total
    code contributions in the repository.
    
    Score interpretation:
    - 1.0: All code went through code review
    - 0.0: No code went through code review
    - -1.0: No linked GitHub repository found
    """

    name = "reviewedness"

    def __init__(self, github_client: Optional[GitHubClient] = None):
        """Initialize the reviewedness metric.
        
        Args:
            github_client: Optional GitHub client. If not provided, a new one
                          will be created using the GITHUB_TOKEN environment variable.
        """
        self.client = github_client or GitHubClient()

    def compute(self, context: ModelContext) -> float:
        """Compute the reviewedness score.
        
        Args:
            context: Model context containing code_urls
            
        Returns:
            float: Score between -1.0 (no repo) and 1.0 (fully reviewed),
                   or dict with per-repo scores if multiple repos
        """
        # Find GitHub repositories in code URLs
        github_repos = self._extract_github_repos(context)

        if not github_repos:
            logger.debug("No GitHub repositories found in code URLs")
            return -1.0

        # If single repo, return scalar score
        if len(github_repos) == 1:
            owner, repo = github_repos[0]
            score = self._compute_repo_score(owner, repo)
            return score

        # If multiple repos, return average score
        scores = []
        for owner, repo in github_repos:
            score = self._compute_repo_score(owner, repo)
            if score >= 0:  # Only include valid scores in average
                scores.append(score)

        if scores:
            return sum(scores) / len(scores)
        
        return -1.0

    def _extract_github_repos(self, context: ModelContext) -> list[tuple[str, str]]:
        """Extract GitHub owner/repo pairs from code URLs.
        
        Args:
            context: Model context
            
        Returns:
            List of (owner, repo) tuples
        """
        repos = []
        for url in context.target.code_urls:
            parsed = parse_artifact_url(url)
            if parsed.platform == "github" and parsed.repo_id:
                parts = parsed.repo_id.split("/")
                if len(parts) == 2:
                    repos.append((parts[0], parts[1]))
        
        return repos

    def _compute_repo_score(self, owner: str, repo: str) -> float:
        """Compute reviewedness score for a single repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Score between 0.0 and 1.0
        """
        try:
            # Get recent merged PRs (limit to avoid rate limiting)
            prs = self.client.get_pull_requests(owner, repo, state="closed")

            if not prs:
                logger.warning(f"No PRs found for {owner}/{repo}")
                return 0.0

            sample_prs = prs[:50] if len(prs) > 50 else prs

            # Count PRs with reviews vs total PRs
            reviewed_prs = 0
            total_analyzed_prs = 0

            for pr in sample_prs:
                # Check if PR was actually merged (in closed state, some may just be closed)
                if not pr.get("merged_at"):
                    continue

                total_analyzed_prs += 1

                # Fetch detailed PR data if basic data is missing
                detailed_pr = self.client._get_detailed_pr(owner, repo, pr.get('number', 0))
                if detailed_pr:
                    pr = detailed_pr

                # Check if PR has code reviews (more comprehensive check)
                has_review = self._pr_has_code_review(pr)

                # Debug logging for PR analysis
                logger.debug(f"PR #{pr.get('number')}: review_comments={pr.get('review_comments', 0)}, "
                           f"comments={pr.get('comments', 0)}, commits={pr.get('commits', 0)}, "
                           f"author={pr.get('user', {}).get('login', '')}, "
                           f"merged_by={pr.get('merged_by', {}).get('login', '')}, "
                           f"has_review={has_review}")

                if has_review:
                    reviewed_prs += 1

            if total_analyzed_prs == 0:
                logger.warning(f"No merged PRs found for analysis in {owner}/{repo}")
                return 0.0

            # Return fraction of PRs that went through code review
            score = reviewed_prs / total_analyzed_prs
            logger.debug(f"Reviewedness for {owner}/{repo}: {reviewed_prs}/{total_analyzed_prs} = {score:.3f}")
            return score

        except Exception as e:
            logger.error(f"Error computing reviewedness for {owner}/{repo}: {e}")
            return 0.0

    def _pr_has_code_review(self, pr: dict) -> bool:
        """Check if a PR has evidence of code review.

        Args:
            pr: Pull request data from GitHub API

        Returns:
            bool: True if PR shows evidence of code review
        """
        # Multiple indicators of code review:
        # 1. Review comments on the PR
        if pr.get("review_comments", 0) > 0:
            return True

        # 2. General comments (may indicate review discussion)
        if pr.get("comments", 0) > 1:  # More than just the initial comment
            return True

        # 3. Multiple commits (may indicate review feedback addressed)
        if pr.get("commits", 0) > 1:
            return True

        # 4. PR was not merged by the author (indicates review by someone else)
        author = pr.get("user", {}).get("login", "")
        merged_by = pr.get("merged_by", {})
        if merged_by and merged_by.get("login", "") != author:
            return True

        # 5. PR has requested reviewers
        if pr.get("requested_reviewers", []):
            return True

        return False


__all__ = ["ReviewednessMetric", "GitHubClient"]
