#!/usr/bin/env python3
"""Read-only release alignment check. No Homebrew or third-party Python packages."""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

OWNER = "rossbuckley1990-hash"
UPSTREAM = f"{OWNER}/rightclick"
TAP = f"{OWNER}/homebrew-tap"
ROOT = f"https://github.com/{UPSTREAM}/releases/download"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def one(pattern, text, label):
    matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
    require(len(matches) == 1, f"Expected exactly one {label}")
    return matches[0]


def pins(formula):
    url = one(r'^  url "([^"]+)"$', formula, "source URL")
    sha = one(r'^  sha256 "([0-9a-f]{64})"$', formula, "source SHA256")
    match = re.fullmatch(re.escape(ROOT) + r'/v(\d+\.\d+\.\d+)/rightclick-\1-source\.tar\.gz', url)
    require(match is not None, "Source URL must name one versioned RIGHTCLICK release asset")
    return match.group(1), url, sha


def resources(formula):
    found = {}
    for name, body in re.findall(r'^  resource "([^"]+)" do\n(.*?)^  end$', formula, re.M | re.S):
        require(name not in found, "Duplicate formula resource")
        found[name] = (
            one(r'^    url "([^"]+)"$', body, "resource URL"),
            one(r'^    sha256 "([0-9a-f]{64})"$', body, "resource SHA256"),
        )
    require("openai-tunnel-client" in found, "Pinned tunnel-client resource is missing")
    return found


def asset(release, name, url):
    matches = [a for a in release.get("assets", []) if a.get("name") == name]
    require(len(matches) == 1, f"Missing or duplicate release asset: {name}")
    result = matches[0]
    require(result.get("state") == "uploaded", f"Asset not uploaded: {name}")
    require(result.get("browser_download_url") == url, f"Unexpected asset URL: {name}")
    return result


def verify_source(formula, release, upstream_formula, read):
    version, url, sha = pins(formula)
    require(release.get("draft") is False and release.get("prerelease") is False,
            "Expected a published stable upstream release")
    require(release.get("tag_name") == f"v{version}", "Upstream release and formula versions differ")
    require(pins(upstream_formula) == pins(formula), "Formula differs from upstream generated source pins")
    require(resources(upstream_formula) == resources(formula), "Tunnel/dependency resource pins differ")
    name = f"rightclick-{version}-source.tar.gz"
    source = asset(release, name, url)
    # Metadata is corroboration, never a substitute for hashing downloaded bytes.
    require(source.get("digest") in (None, f"sha256:{sha}"), "Release metadata digest mismatch")
    require(hashlib.sha256(read(url)).hexdigest() == sha, "Downloaded source SHA256 mismatch")
    sums_url = f"{ROOT}/v{version}/SHA256SUMS-source"
    asset(release, "SHA256SUMS-source", sums_url)
    lines = [line.split() for line in read(sums_url).decode("ascii").splitlines()]
    sums = [row[0] for row in lines if len(row) == 2 and row[1].lstrip("*") == name]
    require(sums == [sha], "Published checksum file does not uniquely match source")
    return {"upstream": f"v{version}", "source_sha256": sha, "source_aligned": True}


def verify_bottle(formula, release, read):
    version, _, _ = pins(formula)
    tag = f"rightclick-{version}"
    require(release.get("tag_name") == tag and release.get("draft") is False
            and release.get("prerelease") is False, "Matching published bottle release is missing")
    body = one(r'^  bottle do\n(.*?)^  end$', formula, "bottle block")
    root = f"https://github.com/{TAP}/releases/download/{tag}"
    require(one(r'^    root_url "([^"]+)"$', body, "bottle root URL") == root, "Stale bottle root URL")
    platforms = re.findall(r'\b(arm64_[a-z0-9_]+):\s*"([0-9a-f]{64})"', body)
    require(platforms and len({p for p, _ in platforms}) == len(platforms), "No unique Apple Silicon bottle pins")
    rebuilds = re.findall(r'^    rebuild (\d+)$', body, re.M)
    require(len(rebuilds) <= 1, "Duplicate bottle rebuild")
    rebuild = int(rebuilds[0]) if rebuilds else 0
    revisions = re.findall(r'^  revision (\d+)$', formula, re.M)
    require(len(revisions) <= 1, "Duplicate formula revision")
    revision = int(revisions[0]) if revisions else 0
    package = version + (f"_{revision}" if revision else "")
    suffix = f".{rebuild}" if rebuild else ""
    names = []
    for platform, sha in platforms:
        name = f"rightclick-{package}.{platform}.bottle{suffix}.tar.gz"
        url = f"{root}/{name}"
        bottle = asset(release, name, url)
        require(bottle.get("digest") in (None, f"sha256:{sha}"), "Bottle metadata digest mismatch")
        require(hashlib.sha256(read(url)).hexdigest() == sha, "Downloaded bottle SHA256 mismatch")
        names.append(name)
    return names


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        require(newurl.startswith("https://"), "Refusing insecure download redirect")
        result = super().redirect_request(req, fp, code, msg, headers, newurl)
        if result is not None:
            result.remove_header("Authorization")
        return result


def read_url(url):
    headers = {"User-Agent": "rightclick-tap-alignment"}
    token = os.environ.get("GH_TOKEN")
    if url.startswith("https://api.github.com/") and token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.build_opener(SafeRedirect()).open(request, timeout=60) as response:
        data = response.read(256 * 1024 * 1024 + 1)
    require(len(data) <= 256 * 1024 * 1024, "Download exceeds 256 MiB limit")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formula", type=Path, default=Path("Formula/rightclick.rb"))
    parser.add_argument("--require-bottle", action="store_true")
    args = parser.parse_args()
    formula = args.formula.read_text(encoding="utf-8")
    version, _, _ = pins(formula)
    upstream = json.loads(read_url(f"https://api.github.com/repos/{UPSTREAM}/releases/latest"))
    generated = read_url(f"https://raw.githubusercontent.com/{UPSTREAM}/v{version}/packaging/tap/Formula/rightclick.rb").decode("utf-8")
    result = verify_source(formula, upstream, generated, read_url)
    result["bottle_check"] = "not_requested"
    print(json.dumps(result, sort_keys=True), flush=True)
    if args.require_bottle:
        release = json.loads(read_url(f"https://api.github.com/repos/{TAP}/releases/tags/rightclick-{version}"))
        result["bottles"] = verify_bottle(formula, release, read_url)
        result["bottle_check"] = "verified"
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"DISTRIBUTION_ALIGNMENT_FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
