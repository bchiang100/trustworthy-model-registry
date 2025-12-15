import base64
import os
from urllib.parse import urlparse, urlunparse 
import hashlib
import re

import requests 

# regex used to detect urls 
# information to analyze public github repos for license check
URL_REGEX = re.compile(r"https?://[^\s]+")
GITHUB_API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json"
}

# detects if a string is a single url of valid format and http(s)
def validate_url_string(url: str) -> bool:
    url = url.strip()
    matches = re.findall(URL_REGEX, url) 
    if len(matches) == 0 or len(matches) > 1:
        return False 
    else:
        match = matches[0]
        # extra text around url
        if match != url:
            return False 

        parsed = urlparse(match)

        # invalid url scheme / netloc
        if parsed.scheme not in ['https', 'http'] or not parsed.netloc:
            return False
        return True 


# standardize
def standardize_url(url: str) -> str:
    parsed = urlparse(url.strip())

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # remove default ports
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    path = parsed.path.rstrip("/") or "/"

    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def make_id(url: str) -> str:
    hashed = hashlib.sha256(url.encode("utf-8")).digest()
    id_num = int.from_bytes(hashed[:5], "big") % 10_000_000_000
    return f"{id_num:010d}"
    

# ensures validity of github url
def parse_github_repo_url(url: str) -> tuple[bool, str, str]:
    parsed = urlparse(url.strip())

    if parsed.scheme not in {"http", "https"}:
        return False, '', ''

    if parsed.netloc != "github.com":
        return False, '', ''

    parts = parsed.path.strip("/").split("/")
    if len(parts) != 2:
        return False, '', ''

    owner, repo = parts
    return True, owner, repo

# checks that repo is public and exists
def is_valid_repo(owner: str, repo: str) -> bool:
    timeout = int(os.getenv("ACME_README_TIMEOUT", "2"))
    try:
        r = requests.get(
            f"{GITHUB_API}/repos/{owner}/{repo}",
            headers=HEADERS,
            timeout=timeout,
        )
    except Exception:
        return False

    if r.status_code == 404:
        return False

    if r.status_code != 200:
        return False

    data = r.json()

    if data.get("private"):
        return False

    return True

# fetches readme from repo
def fetch_readme(owner: str, repo: str) -> tuple[bool, str]:
    timeout = int(os.getenv("ACME_README_TIMEOUT", "2"))
    try:
        r = requests.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/readme",
            headers=HEADERS,
            timeout=timeout,
        )
    except Exception:
        return False, ''

    if r.status_code == 404:
        return False, ''

    if r.status_code != 200:
        return False, ''

    data = r.json()

    if data.get("encoding") != "base64":
        return False, ''

    content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    return True, content

def get_github_readme(repo_url: str, timeout: int | None = None) -> tuple[bool, str]:
    """Fetch README for a GitHub repo.

    If `timeout` is provided it will override the default `ACME_README_TIMEOUT`.
    Returns (valid, readme_text).
    """
    good_url, owner, repo = parse_github_repo_url(repo_url)
    if not good_url:
        return False, ''

    # allow overriding timeout via env or explicit argument
    if timeout is not None:
        prev = os.getenv("ACME_README_TIMEOUT")
        os.environ["ACME_README_TIMEOUT"] = str(timeout)
    try:
        good_repo = is_valid_repo(owner, repo)  # validates repo existence and visibility
        if not good_repo:
            return False, ''

        good_readme, readme = fetch_readme(owner, repo)
        if not good_readme:
            return False, ''

        return True, readme
    finally:
        # restore previous env var if we changed it
        if timeout is not None:
            if prev is None:
                os.environ.pop("ACME_README_TIMEOUT", None)
            else:
                os.environ["ACME_README_TIMEOUT"] = prev