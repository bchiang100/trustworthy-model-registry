from urllib.parse import urlparse, urlunparse 
import hashlib
import re 

# regex used to detect urls 
URL_REGEX = re.compile(r"https?://[^\s]+")

# detects if a string is a single url of valid format and http(s)
def validate_url_string(url: str) -> bool:
    url = url.strip()
    matches = re.findall(URL_REGEX) 
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
    

