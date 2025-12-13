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
        
        Args:
            owner: Repository owner
            repo: Repository name
            state: PR state ("closed" for merged, "open", "all")
            
        Returns:
            List of PR objects from the GitHub API
        """
        try:
            session = self._get_session()
            url = f"{self._api_url}/repos/{owner}/{repo}/pulls"
            params = {
                "state": state,
                "per_page": 100,  # Paginate as needed
            }
            
            all_prs = []
            page = 1
            while True:
                params["page"] = page
                response = session.get(url, params=params, timeout=10)
                response.raise_for_status()
                prs = response.json()
                
                if not prs:
                    break
                    
                all_prs.extend(prs)
                
                # Stop after reasonable limit to avoid rate limits
                if len(all_prs) >= 1000:
                    break
                    
                page += 1
            
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
            # Get merged PRs with code review
            prs = self.client.get_pull_requests(owner, repo, state="closed")
            
            if not prs:
                logger.warning(f"No PRs found for {owner}/{repo}")
                return 0.0

            # Count PRs with reviews
            reviewed_prs = 0
            reviewed_commits = 0
            total_commits = 0

            for pr in prs:
                # Check if PR was actually merged (in closed state, some may just be closed)
                if not pr.get("merged_at"):
                    continue

                # Count this PR's commits
                commits = self.client.get_commits_by_pr(owner, repo, pr["number"])
                pr_commit_count = len(commits)
                total_commits += pr_commit_count

                # Check if PR has reviews
                # A PR with reviews will have review_comments > 0 or was approved
                has_review = (
                    pr.get("review_comments", 0) > 0 
                    or pr.get("requested_reviewers", [])
                    or pr.get("reviews_count", 0) > 0
                )

                if has_review:
                    reviewed_prs += 1
                    reviewed_commits += pr_commit_count

            if total_commits == 0:
                logger.warning(f"No commits found in merged PRs for {owner}/{repo}")
                return 0.0

            # Return fraction of commits that went through review
            score = reviewed_commits / total_commits
            return score

        except Exception as e:
            logger.error(f"Error computing reviewedness for {owner}/{repo}: {e}")
            return 0.0


__all__ = ["ReviewednessMetric", "GitHubClient"]
