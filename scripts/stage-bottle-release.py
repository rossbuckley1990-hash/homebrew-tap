#!/usr/bin/env python3
"""Stage verified Homebrew bottles before publishing or pushing their pins."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

spec = importlib.util.spec_from_file_location("distribution", Path(__file__).with_name("check-distribution.py"))
distribution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(distribution)
REPO = distribution.TAP


def require(condition, message):
    if not condition:
        raise ValueError(message)


def gh(*args, data=None, missing=False):
    result = subprocess.run(["gh", *args], input=data, capture_output=True, check=False)
    if result.returncode:
        try:
            body = json.loads(result.stdout)
        except (ValueError, UnicodeError):
            body = {}
        if missing and str(body.get("status")) == "404":
            return None
        # Never echo captured stderr, environment values or untrusted API text.
        raise ValueError("GitHub operation failed; no release/pin success inferred")
    return result.stdout


def api(path, data=None, missing=False):
    args = ["api", "-H", "X-GitHub-Api-Version: 2026-03-10", path]
    if data is not None:
        args += ["--method", "POST" if path.endswith("/releases") else "PATCH", "--input", "-"]
    raw = gh(*args, data=json.dumps(data).encode() if data is not None else None, missing=missing)
    return json.loads(raw) if raw is not None else None


def without_bottle(formula):
    return re.sub(r"^  bottle do\n.*?^  end\n\n", "", formula, flags=re.M | re.S)


def bottles(directory, formula):
    directory = directory.resolve()
    version, _, source = distribution.pins(formula)
    root = f"https://github.com/{REPO}/releases/download/rightclick-{version}"
    block = distribution.one(r"^  bottle do\n(.*?)^  end$", formula, "bottle block")
    require(distribution.one(r'^    root_url "([^"]+)"$', block, "bottle root URL") == root,
            "Bottle root does not identify this exact version")
    pins = dict(re.findall(r'\b(arm64_[a-z0-9_]+):\s*"([0-9a-f]{64})"', block))
    require(pins, "No Apple Silicon bottle pins")
    assets, revisions, observed = {}, set(), {}
    for path in sorted(directory.glob("*.bottle.json")):
        payload(path)
        rows = json.loads(path.read_text())
        require(len(rows) == 1, "Expected exactly one RIGHTCLICK formula")
        row = next(iter(rows.values()))
        require(row["formula"]["name"] == "rightclick" and row["formula"]["pkg_version"] == version,
                "Bottle formula/version mismatch")
        revision = row["formula"]["tap_git_revision"]
        require(re.fullmatch(r"[0-9a-f]{40}", revision), "Invalid build revision")
        revisions.add(revision)
        require(row["bottle"]["root_url"] == root, "Stale bottle metadata URL")
        for platform, entry in row["bottle"]["tags"].items():
            name, local, digest = entry["filename"], entry["local_filename"], entry["sha256"]
            require(platform in pins and platform not in observed and pins[platform] == digest,
                    "Missing, duplicate or mismatched platform digest")
            require(re.fullmatch(rf"rightclick-{re.escape(version)}\.arm64_[a-z0-9_]+\.bottle(?:\.\d+)?\.tar\.gz", name),
                    "Unexpected bottle asset name")
            file = directory / local
            require(Path(local).name == local and not file.is_symlink() and file.resolve().parent == directory,
                    "Bottle path escapes its retained artifact directory")
            require(local == name.replace("rightclick-", "rightclick--", 1), "Unexpected local bottle filename")
            require(file.stat().st_size <= 256 * 1024 * 1024, "Bottle exceeds bounded download size")
            require(hashlib.sha256(file.read_bytes()).hexdigest() == digest, "Local bottle bytes do not match pins")
            require(name not in assets, "Duplicate bottle asset name")
            assets[name] = {"local": local, "SHA256": digest, "bytes": file.stat().st_size}
            observed[platform] = digest
    require(observed == pins and len(revisions) == 1, "Incomplete or mixed-revision bottle artifacts")
    return {"version": version, "sourceSHA256": source, "tag": f"rightclick-{version}",
            "formulaSHA256": hashlib.sha256(formula.encode()).hexdigest(),
            "builtRevision": revisions.pop(), "assets": assets}


def validate_release(release, record, read, complete=True):
    require(release["tag_name"] == record["tag"] and not release["prerelease"], "Wrong release identity")
    assets = {a["name"]: a for a in release["assets"]}
    require(len(assets) == len(release["assets"]) and set(assets).issubset(record["assets"]),
            "Release assets are incomplete, duplicate or unexpected")
    require(not complete or set(assets) == set(record["assets"]), "Release assets are incomplete")
    for name, asset in assets.items():
        expected = record["assets"][name]
        require(asset["state"] == "uploaded" and asset.get("digest") in (None, "sha256:" + expected["SHA256"]),
                "Release asset is not uploaded or its metadata digest differs")
        require(asset["size"] == expected["bytes"], "Release asset size differs")
        require(hashlib.sha256(read(asset)).hexdigest() == expected["SHA256"], "Downloaded bottle bytes differ")


def draft_asset(asset):
    return gh("api", "-H", "Accept: application/octet-stream",
              f"repos/{REPO}/releases/assets/{asset['id']}")


def validate_tag(record):
    ref = api(f"repos/{REPO}/git/ref/tags/{record['tag']}")
    obj = ref["object"]
    if obj["type"] == "tag":
        obj = api(f"repos/{REPO}/git/tags/{obj['sha']}")["object"]
    require(obj["type"] == "commit" and obj["sha"] == record["reviewedHead"], "Published tag target differs from reviewed head")


def git(tap, *args):
    result = subprocess.run(["git", "-C", str(tap), *args], capture_output=True, check=False)
    require(result.returncode == 0, "Git integrity operation failed; no public push inferred")
    return result.stdout.decode().strip()


def payload(path):
    require(path.is_file() and not path.is_symlink(), "Handoff payload is missing or a symlink")
    require(path.stat().st_size <= 256 * 1024 * 1024, "Handoff payload exceeds bounded size")
    return {"SHA256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}


def produce_handoff(args, formula):
    record = bottles(args.bottle_dir, formula)
    require(re.fullmatch(r"[0-9a-f]{40}", args.producer_base or ""), "Producer workflow base is missing")
    tap = args.tap_path
    require(tap is not None and git(tap, "status", "--porcelain", "--untracked-files=no") == "",
            "Producer checkout has uncommitted tracked changes")
    require(args.run_id and args.run_id > 0 and args.run_attempt > 0, "Producer run identity is missing")
    commit = git(tap, "rev-parse", "HEAD")
    parent = git(tap, "rev-parse", "HEAD^")
    git(tap, "merge-base", "--is-ancestor", args.producer_base, commit)
    git(tap, "merge-base", "--is-ancestor", args.producer_base, args.head_sha)
    require(git(tap, "diff", "--name-only", args.producer_base, args.head_sha) == "Formula/rightclick.rb",
            "Reviewed source PR changes files beyond the formula")
    require(git(tap, "rev-parse", parent + "^{tree}") == git(tap, "rev-parse", args.head_sha + "^{tree}"),
            "Applied source tree differs from the reviewed PR")
    require(git(tap, "diff", "--name-only", parent, commit) == "Formula/rightclick.rb",
            "Producer bottle commit changed files beyond the formula")
    require(git(tap, "show", commit + ":Formula/rightclick.rb") + "\n" == formula,
            "Producer formula does not match its committed bytes")
    directory = args.bottle_dir
    (directory / "reviewed-formula.rb").write_text(formula)
    git(tap, "bundle", "create", str(directory / "reviewed-bottle.bundle"), "HEAD", "^" + args.producer_base)
    files = {"reviewed-formula.rb", "reviewed-bottle.bundle"}
    files.update(p.name for p in directory.glob("*.bottle.json"))
    files.update(asset["local"] for asset in record["assets"].values())
    record.update(reviewedHead=args.head_sha, pullRequest=args.pull_request, producerBase=args.producer_base,
                  producerCommit=commit, runID=args.run_id, runAttempt=args.run_attempt, payloads={name: payload(directory / name) for name in sorted(files)})
    (directory / "bottle-handoff.json").write_text(json.dumps(record, indent=2) + "\n")
    print("PREPARED: committed formula and bottle bytes retained for attested host finalization; public pins unchanged")
    return 0


def verify_handoff(args):
    directory = args.bottle_dir.resolve()
    payload(directory / "bottle-handoff.json")
    record = json.loads((directory / "bottle-handoff.json").read_text())
    require(args.run_id and args.run_id > 0 and args.run_attempt > 0 and
            record.get("runID") == args.run_id and record.get("runAttempt") == args.run_attempt,
            "Handoff does not match the selected producer run/attempt")
    run = api(f"repos/{REPO}/actions/runs/{args.run_id}/attempts/{args.run_attempt}")
    require(run["path"] == ".github/workflows/publish.yml" and run["event"] == "workflow_dispatch" and
            run["head_branch"] == "main" and run["head_sha"] == args.producer_base and
            run["status"] == "completed" and run["conclusion"] == "success",
            "Selected producer run is not a successful exact-base main publisher")
    require(record["reviewedHead"] == args.head_sha and record["pullRequest"] == args.pull_request and
            record["producerBase"] == args.producer_base and re.fullmatch(r"[0-9a-f]{40}", record["producerCommit"]),
            "Handoff does not match the selected workflow base and reviewed PR")
    names = set(record["payloads"])
    require({"reviewed-formula.rb", "reviewed-bottle.bundle"}.issubset(names), "Required handoff payload is missing")
    for name, expected in record["payloads"].items():
        path = directory / name
        require(Path(name).name == name and path.resolve().parent == directory and payload(path) == expected,
                "Handoff payload identity changed or escapes its directory")
    formula = (directory / "reviewed-formula.rb").read_text()
    actual = bottles(directory, formula)
    require(all(record.get(k) == value for k, value in actual.items()), "Handoff formula/bottle inventory changed")
    expected_names = {"reviewed-formula.rb", "reviewed-bottle.bundle"}
    expected_names.update(p.name for p in directory.glob("*.bottle.json"))
    expected_names.update(asset["local"] for asset in actual["assets"].values())
    require(names == expected_names, "Unexpected or missing handoff payloads")
    for name in sorted(names | {"bottle-handoff.json"}):
        verified = json.loads(gh("attestation", "verify", str(directory / name), "--repo", REPO,
           "--signer-workflow", REPO + "/.github/workflows/publish.yml",
           "--source-ref", "refs/heads/main", "--source-digest", args.producer_base,
           "--signer-digest", args.producer_base,
           "--deny-self-hosted-runners", "--format", "json"))
        invocation = f"https://github.com/{REPO}/actions/runs/{args.run_id}/attempts/{args.run_attempt}"
        require(any(row["verificationResult"]["signature"]["certificate"].get("runInvocationURI") == invocation
                    for row in verified), "Verified certificate does not identify the selected producer run")
    return record, formula


def finalize(args):
    require(args.tap_path is not None and re.fullmatch(r"[0-9a-f]{40}", args.producer_base or ""),
            "Finalizer requires a private tap checkout and selected producer workflow base")
    record, formula = verify_handoff(args)
    tap = args.tap_path
    require(git(tap, "status", "--porcelain", "--untracked-files=no") == "", "Private finalizer checkout is dirty")
    require(git(tap, "remote", "get-url", "origin") in
            [f"https://github.com/{REPO}.git", f"git@github.com:{REPO}.git"], "Finalizer origin is not the canonical tap")
    git(tap, "fetch", "origin", "refs/heads/main:refs/remotes/origin/main", args.head_sha)
    require(git(tap, "rev-parse", "refs/remotes/origin/main") == args.producer_base,
            "Public main advanced since producer run; review and rebuild the new base")
    git(tap, "bundle", "verify", str(args.bottle_dir / "reviewed-bottle.bundle"))
    git(tap, "fetch", str(args.bottle_dir / "reviewed-bottle.bundle"), "HEAD")
    require(git(tap, "rev-parse", "FETCH_HEAD") == record["producerCommit"], "Bundle commit differs from handoff")
    git(tap, "checkout", "--detach", record["producerCommit"])
    parent = git(tap, "rev-parse", "HEAD^")
    git(tap, "merge-base", "--is-ancestor", args.producer_base, "HEAD")
    require(git(tap, "rev-parse", parent + "^{tree}") == git(tap, "rev-parse", args.head_sha + "^{tree}") and
            git(tap, "diff", "--name-only", parent, "HEAD") == "Formula/rightclick.rb",
            "Bundled source or bottle commit differs from reviewed scope")
    require(git(tap, "show", "HEAD:Formula/rightclick.rb") + "\n" == formula,
            "Bundled formula differs from independently attested bytes")
    args.formula = tap / "Formula/rightclick.rb"
    args.mode = "stage"
    publication(args, formula)
    args.mode = "publish"
    publication(args, formula)
    # A normal non-forced push also fails if another writer advances main.
    require(api(f"repos/{REPO}/git/ref/heads/main")["object"]["sha"] == args.producer_base,
            "Public main advanced before push; immutable assets retained for reviewed recovery")
    git(tap, "push", "origin", record["producerCommit"] + ":refs/heads/main")
    print("FINALIZED: independently verified immutable bottles and exact formula committed by ordinary fast-forward")
    return 0


def publication(args, formula):
    record = bottles(args.bottle_dir, formula)
    pr = api(f"repos/{REPO}/pulls/{args.pull_request}")
    require(pr["state"] == "open" and pr["head"]["sha"] == args.head_sha and pr["base"]["ref"] == "main",
            "PR no longer matches its reviewed open head")
    for revision in [args.head_sha, record["builtRevision"]]:
        built = distribution.read_url(f"https://raw.githubusercontent.com/{REPO}/{revision}/Formula/rightclick.rb").decode()
        require(without_bottle(built) == without_bottle(formula), "Installer differs from reviewed/built formula")
    checks = api(f"repos/{REPO}/commits/{args.head_sha}/check-runs?per_page=100")
    runs = checks["check_runs"]
    require(checks["total_count"] == len(runs), "Check inventory is incomplete; pagination required")
    latest = {}
    for run in runs:
        if run["name"] == "pr-pull":
            continue  # The current publisher is not a completed PR acceptance check.
        if run["id"] > latest.get(run["name"], {}).get("id", -1):
            latest[run["name"]] = run
    require("distribution-invariants" in latest and any(n.startswith("test-bot") for n in latest),
            "Required distribution/bottle checks are missing")
    require(all(r["status"] == "completed" and r["conclusion"] in ["success", "skipped"] for r in latest.values()),
            "Exact-head checks are incomplete or failed")
    require(latest["distribution-invariants"]["conclusion"] == "success" and
            all(r["conclusion"] == "success" for n, r in latest.items() if n.startswith("test-bot")),
            "Required distribution/bottle checks did not pass")
    upstream = api(f"repos/{distribution.UPSTREAM}/releases/latest")
    require(upstream.get("immutable") is True, "Upstream accepted source is not immutable")
    generated = distribution.read_url(f"https://raw.githubusercontent.com/{distribution.UPSTREAM}/v{record['version']}/packaging/tap/Formula/rightclick.rb").decode()
    distribution.verify_source(formula, upstream, generated, distribution.read_url)
    require(api(f"repos/{REPO}/immutable-releases").get("enabled") is True, "Future tap releases are not immutable")
    state = args.bottle_dir / "staged-release.json"
    def require_selected_base():
        current = api(f"repos/{REPO}/git/ref/heads/main")["object"]["sha"]
        require(current == args.producer_base, "Public main advanced; preserve published formula and review the new base")
        return current
    main_sha = require_selected_base()
    if args.mode == "stage":
        releases = api(f"repos/{REPO}/releases?per_page=100")
        require(len(releases) < 100, "Release inventory requires pagination; no creation inferred")
        matches = [r for r in releases if r["tag_name"] == record["tag"]]
        require(len(matches) <= 1, "Duplicate release identity")
        release = matches[0] if matches else None
        if release is None:
            require(api(f"repos/{REPO}/git/ref/tags/{record['tag']}", missing=True) is None,
                    "Existing tag without owned matching release must be preserved")
            require_selected_base()
            release = api(f"repos/{REPO}/releases", {"tag_name": record["tag"], "target_commitish": args.head_sha,
                          "name": record["tag"], "draft": True, "prerelease": False,
                          "body": "Matching tested RIGHTCLICK Homebrew bottle; source version and assets are independently verified before publication."})
        require(release["target_commitish"] == args.head_sha, "Existing release belongs to another reviewed head")
        record.update(releaseID=release["id"], mainSHA=main_sha, reviewedHead=args.head_sha)
        if api(f"repos/{REPO}/git/ref/tags/{record['tag']}", missing=True) is not None:
            validate_tag(record)
        if release["draft"] is True:
            # Recovery verifies existing bytes; it never overwrites or deletes.
            validate_release(release, record, draft_asset, complete=False)
            existing = {a["name"] for a in release["assets"]}
            for name, entry in record["assets"].items():
                if name not in existing:
                    require_selected_base()
                    gh("api", "--method", "POST", "-H", "Content-Type: application/octet-stream",
                       f"https://uploads.github.com/repos/{REPO}/releases/{release['id']}/assets?name={name}",
                       "--input", str(args.bottle_dir / entry["local"]))
            release = api(f"repos/{REPO}/releases/{release['id']}")
            require(release["draft"] is True, "Bottle release became public before validation")
            validate_release(release, record, draft_asset)
        else:
            require(release.get("immutable") is True, "Existing published release is not immutable")
            distribution.verify_bottle(formula, release, distribution.read_url)
            validate_tag(record)
        state.write_text(json.dumps(record, indent=2) + "\n")
        print("STAGED: all bottle assets independently hashed; public pins unchanged")
    else:
        saved = json.loads(state.read_text())
        require(all(saved.get(k) == v for k, v in record.items()) and saved["reviewedHead"] == args.head_sha,
                "Staged bytes/formula/review identity changed")
        require(main_sha == saved["mainSHA"], "Public main advanced; preserve published formula and review the new base")
        release = api(f"repos/{REPO}/releases/{saved['releaseID']}")
        require(release["target_commitish"] == args.head_sha, "Release is no longer the reviewed identity")
        if release["draft"] is True:
            if api(f"repos/{REPO}/git/ref/tags/{record['tag']}", missing=True) is not None:
                validate_tag(saved)
            validate_release(release, record, draft_asset)
            require_selected_base()
            release = api(f"repos/{REPO}/releases/{saved['releaseID']}", {"draft": False})
        require(release.get("immutable") is True and release["draft"] is False, "Published release did not become immutable")
        distribution.verify_bottle(formula, release, distribution.read_url)
        validate_tag(saved)
        record.update(saved, publishedImmutable=True)
        state.write_text(json.dumps(record, indent=2) + "\n")
        print("PUBLISHED: immutable bottles independently downloaded; new formula pins may now be pushed")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["root", "handoff", "finalize"])
    parser.add_argument("--bottle-dir", type=Path, required=True)
    parser.add_argument("--formula", type=Path)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--pull-request", type=int, required=True)
    parser.add_argument("--tap-path", type=Path)
    parser.add_argument("--producer-base")
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--run-attempt", type=int, default=1)
    args = parser.parse_args()
    require(re.fullmatch(r"[0-9a-f]{40}", args.head_sha) and args.pull_request > 0, "Invalid reviewed PR identity")
    if args.mode == "finalize":
        return finalize(args)
    require(args.formula is not None, "Formula path is required")
    formula = args.formula.read_text()
    if args.mode == "root":
        version, _, _ = distribution.pins(formula)
        print(f"https://github.com/{REPO}/releases/download/rightclick-{version}")
        return 0
    if args.mode == "handoff":
        return produce_handoff(args, formula)
    raise ValueError("Unsupported operation; release writes require finalizer provenance")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("BOTTLE_PUBLICATION_FAILED: " + str(exc), file=sys.stderr)
        sys.exit(1)
