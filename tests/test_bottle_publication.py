import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("publication", Path(__file__).parents[1] / "scripts/stage-bottle-release.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class BottlePublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.head, self.built, self.base = "a" * 40, "b" * 40, "c" * 40
        self.producer_base = self.base
        self.source = b"owned deterministic source fixture"
        source_sha = hashlib.sha256(self.source).hexdigest()
        original = (Path(__file__).parents[1] / "Formula/rightclick.rb").read_text()
        old_version, _, old_sha = m.distribution.pins(original)
        self.original = m.without_bottle(original).replace(old_sha, source_sha).replace(
            f"/v{old_version}/rightclick-{old_version}-source.tar.gz", "/v0.2.3/rightclick-0.2.3-source.tar.gz")
        self.payload = b"owned bottle bytes"
        self.digest = hashlib.sha256(self.payload).hexdigest()
        self.name = "rightclick-0.2.3.arm64_tahoe.bottle.tar.gz"
        self.local = "rightclick--0.2.3.arm64_tahoe.bottle.tar.gz"
        (self.root / self.local).write_bytes(self.payload)
        self.url = f"https://github.com/{m.REPO}/releases/download/rightclick-0.2.3"
        block = f'  bottle do\n    root_url "{self.url}"\n    sha256 arm64_tahoe: "{self.digest}"\n  end\n\n'
        self.formula = self.original.replace('  license "Apache-2.0"\n\n', '  license "Apache-2.0"\n\n' + block)
        self.formula_file = self.root / "rightclick.rb"
        self.formula_file.write_text(self.formula)
        self.row = {"formula": {"name": "rightclick", "pkg_version": "0.2.3", "tap_git_revision": self.built},
                    "bottle": {"root_url": self.url, "tags": {"arm64_tahoe": {
                        "filename": self.name, "local_filename": self.local, "sha256": self.digest}}}}
        self.json_file = self.root / "rightclick.bottle.json"
        self.save_row()
        self.release = None
        self.remote = {}
        self.events = []
        self.checks = [{"id": 1, "name": "distribution-invariants", "status": "completed", "conclusion": "success"},
                       {"id": 2, "name": "test-bot (macos-26)", "status": "completed", "conclusion": "success"},
                       {"id": 3, "name": "pr-pull", "status": "in_progress", "conclusion": None}]
        self.upstream = {"tag_name": "v0.2.3", "draft": False, "prerelease": False, "immutable": True, "assets": [
            {"name": "rightclick-0.2.3-source.tar.gz", "state": "uploaded", "browser_download_url": m.distribution.pins(self.formula)[1], "digest": "sha256:" + source_sha},
            {"name": "SHA256SUMS-source", "state": "uploaded", "browser_download_url": m.distribution.ROOT + "/v0.2.3/SHA256SUMS-source"}]}

    def save_row(self):
        self.json_file.write_text(json.dumps({"rossbuckley1990-hash/tap/rightclick": self.row}))

    def api(self, path, data=None, missing=False):
        if "/pulls/" in path:
            return {"state": "open", "head": {"sha": self.head}, "base": {"ref": "main"}}
        if "/check-runs?" in path:
            return {"total_count": len(self.checks), "check_runs": copy.deepcopy(self.checks)}
        if path == f"repos/{m.distribution.UPSTREAM}/releases/latest":
            return copy.deepcopy(self.upstream)
        if path.endswith("/immutable-releases"):
            return {"enabled": True}
        if path.endswith("/git/ref/heads/main"):
            return {"object": {"sha": self.base}}
        if "/git/ref/tags/" in path:
            return {"object": {"type": "commit", "sha": self.head}} if self.release and not self.release["draft"] else None
        if path.endswith("/releases?per_page=100"):
            return [copy.deepcopy(self.release)] if self.release else []
        if path.endswith("/releases") and data:
            self.events.append(("create", data["draft"]))
            self.release = dict(data, id=42, immutable=False, assets=[])
            return copy.deepcopy(self.release)
        if path.endswith("/releases/42"):
            if data:
                self.events.append(("publish",))
                self.release.update(data, immutable=True)
            return copy.deepcopy(self.release)
        raise AssertionError("Unexpected API route: " + path)

    def gh(self, *args, **kwargs):
        if "--method" in args and "POST" in args:
            self.assertTrue(self.release["draft"], "Uploading after publication is the inherited ordering defect")
            name = next(a.split("?name=", 1)[1] for a in args if "?name=" in a)
            data = Path(args[args.index("--input") + 1]).read_bytes()
            self.events.append(("upload", name))
            self.remote[name] = data
            self.release["assets"].append({"id": 11, "name": name, "state": "uploaded", "size": len(data),
                                           "digest": "sha256:" + hashlib.sha256(data).hexdigest(), "browser_download_url": self.url + "/" + name})
            return b"{}"
        if "Accept: application/octet-stream" in args:
            self.events.append(("draft-download",))
            return self.remote[self.name]
        raise AssertionError("Unexpected gh operation")

    def read(self, url):
        if url.startswith("https://raw.githubusercontent.com/"):
            return self.original.encode()
        if url == m.distribution.pins(self.formula)[1]:
            return self.source
        if url.endswith("/SHA256SUMS-source"):
            return (hashlib.sha256(self.source).hexdigest() + "  rightclick-0.2.3-source.tar.gz\n").encode()
        if url == self.url + "/" + self.name:
            self.events.append(("public-download",))
            return self.remote[self.name]
        raise AssertionError("Unexpected download URL")

    def run_mode(self, mode):
        args = SimpleNamespace(mode=mode, bottle_dir=self.root, formula=self.formula_file,
                               head_sha=self.head, pull_request=14, producer_base=self.producer_base)
        with patch.object(m, "api", self.api), patch.object(m, "gh", self.gh), patch.object(m.distribution, "read_url", self.read):
            return m.publication(args, self.formula)

    def test_cli_cannot_bypass_handoff_provenance_with_stage_or_publish(self):
        for mode in ["stage", "publish"]:
            with self.subTest(mode=mode), patch("sys.argv", ["stage-bottle-release.py", mode]), \
                 patch.object(m, "api") as api, patch.object(m, "publication") as publication:
                with self.assertRaises(SystemExit) as error:
                    m.main()
                self.assertEqual(error.exception.code, 2)
                api.assert_not_called()
                publication.assert_not_called()

    def test_base_advance_immediately_before_stage_prevents_every_release_write(self):
        self.base = "d" * 40
        with self.assertRaisesRegex(ValueError, "main advanced"):
            self.run_mode("stage")
        self.assertEqual(self.events, [])
        self.assertIsNone(self.release)

    def test_base_advance_after_inventory_before_create_prevents_release_write(self):
        original = self.api
        def changed(path, data=None, missing=False):
            result = original(path, data, missing)
            if path.endswith("/releases?per_page=100"):
                self.base = "d" * 40
            return result
        with patch.object(self, "api", changed):
            with self.assertRaisesRegex(ValueError, "main advanced"):
                self.run_mode("stage")
        self.assertEqual(self.events, [])
        self.assertIsNone(self.release)

    def test_base_advance_after_draft_readback_prevents_publication(self):
        self.run_mode("stage")
        original = self.gh
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            if "Accept: application/octet-stream" in args:
                self.base = "d" * 40
            return result
        with patch.object(self, "gh", changed):
            with self.assertRaisesRegex(ValueError, "main advanced"):
                self.run_mode("publish")
        self.assertTrue(self.release["draft"])
        self.assertNotIn(("publish",), self.events)

    def test_all_assets_verified_twice_before_publish_and_again_publicly(self):
        self.assertEqual(self.run_mode("stage"), 0)
        self.assertTrue(self.release["draft"])
        self.assertNotIn(("publish",), self.events)
        self.assertEqual(self.run_mode("publish"), 0)
        self.assertTrue(self.release["immutable"])
        publish = self.events.index(("publish",))
        self.assertEqual(self.events[:publish].count(("draft-download",)), 2)
        self.assertEqual(self.events[publish + 1:], [("public-download",)])

    def test_retained_draft_tampering_prevents_publication(self):
        self.run_mode("stage")
        self.remote[self.name] = b"tampered remote bytes"
        with self.assertRaisesRegex(ValueError, "Downloaded bottle bytes differ"):
            self.run_mode("publish")
        self.assertTrue(self.release["draft"])

    def test_local_tampering_never_creates_a_release(self):
        (self.root / self.local).write_bytes(b"different")
        with self.assertRaisesRegex(ValueError, "Local bottle bytes"):
            self.run_mode("stage")
        self.assertIsNone(self.release)

    def test_paths_cannot_escape_retained_artifacts(self):
        self.row["bottle"]["tags"]["arm64_tahoe"]["local_filename"] = "../owned-file"
        self.save_row()
        with self.assertRaisesRegex(ValueError, "escapes"):
            m.bottles(self.root, self.formula)

    def test_symlink_bottle_is_rejected(self):
        file = self.root / self.local
        file.unlink()
        file.symlink_to(self.formula_file)
        with self.assertRaisesRegex(ValueError, "escapes"):
            m.bottles(self.root, self.formula)

    def test_new_base_stops_publication(self):
        self.run_mode("stage")
        self.base = "d" * 40
        with self.assertRaisesRegex(ValueError, "main advanced"):
            self.run_mode("publish")
        self.assertTrue(self.release["draft"])

    def test_failed_exact_head_check_prevents_draft_creation(self):
        self.checks[0]["conclusion"] = "failure"
        with self.assertRaisesRegex(ValueError, "incomplete or failed"):
            self.run_mode("stage")
        self.assertIsNone(self.release)

    def test_unpublished_or_mutable_upstream_prevents_draft_creation(self):
        self.upstream["immutable"] = False
        with self.assertRaisesRegex(ValueError, "source is not immutable"):
            self.run_mode("stage")
        self.assertIsNone(self.release)

    def test_unknown_extra_asset_prevents_publication(self):
        self.run_mode("stage")
        self.release["assets"].append({"name": "unexpected"})
        with self.assertRaisesRegex(ValueError, "unexpected"):
            self.run_mode("publish")
        self.assertTrue(self.release["draft"])

    def test_partial_draft_retry_verifies_without_overwrite(self):
        self.run_mode("stage")
        self.run_mode("stage")
        self.assertEqual(sum(e[0] == "create" for e in self.events), 1)
        self.assertEqual(sum(e[0] == "upload" for e in self.events), 1)

    def test_publication_retry_reuses_immutable_bytes_without_mutation(self):
        self.run_mode("stage")
        self.run_mode("publish")
        before = sum(e[0] in ["create", "upload", "publish"] for e in self.events)
        self.run_mode("publish")
        self.assertEqual(sum(e[0] in ["create", "upload", "publish"] for e in self.events), before)

    def test_incomplete_check_inventory_never_creates_a_release(self):
        original = self.api
        def incomplete(path, data=None, missing=False):
            value = original(path, data, missing)
            if "/check-runs?" in path:
                value["total_count"] = 101
            return value
        with patch.object(self, "api", incomplete):
            with self.assertRaisesRegex(ValueError, "inventory is incomplete"):
                self.run_mode("stage")
        self.assertIsNone(self.release)

    def test_changed_reviewed_head_never_creates_a_release(self):
        original = self.api
        def changed(path, data=None, missing=False):
            value = original(path, data, missing)
            if "/pulls/" in path:
                value["head"]["sha"] = "d" * 40
            return value
        with patch.object(self, "api", changed):
            with self.assertRaisesRegex(ValueError, "reviewed open head"):
                self.run_mode("stage")
        self.assertIsNone(self.release)

    def test_disabled_immutability_never_creates_a_release(self):
        original = self.api
        def disabled(path, data=None, missing=False):
            value = original(path, data, missing)
            return {"enabled": False} if path.endswith("/immutable-releases") else value
        with patch.object(self, "api", disabled):
            with self.assertRaisesRegex(ValueError, "not immutable"):
                self.run_mode("stage")
        self.assertIsNone(self.release)


class HandoffIntegrityTests(unittest.TestCase):
    setUp = BottlePublicationTests.setUp
    save_row = BottlePublicationTests.save_row
    api = BottlePublicationTests.api
    read = BottlePublicationTests.read
    # Retain real Git trees/bundle controls; GitHub/provenance responses remain isolated models.
    def make_handoff(self):
        self.tap = self.root / "private-tap"
        self.tap.mkdir()
        def git(*args):
            r = subprocess.run(["git", "-C", str(self.tap), *args], capture_output=True, check=True)
            return r.stdout.decode().strip()
        self.git = git
        git("init", "-b", "main")
        git("config", "user.name", "Owned fixture")
        git("config", "user.email", "owned-fixture@example.invalid")
        (self.tap / "Formula").mkdir()
        f = self.tap / "Formula/rightclick.rb"
        f.write_text((Path(__file__).parents[1] / "Formula/rightclick.rb").read_text())
        git("add", "Formula/rightclick.rb")
        git("commit", "-m", "owned prior public formula")
        self.base = git("rev-parse", "HEAD")
        f.write_text(self.original)
        git("add", "Formula/rightclick.rb")
        git("commit", "-m", "owned reviewed source formula")
        self.head = git("rev-parse", "HEAD")
        self.row["formula"]["tap_git_revision"] = self.head
        self.save_row()
        f.write_text(self.formula)
        git("add", "Formula/rightclick.rb")
        git("commit", "-m", "owned bottle-only formula")
        self.args = SimpleNamespace(mode="handoff", bottle_dir=self.root, formula=f, head_sha=self.head,
                                    pull_request=14, producer_base=self.base, tap_path=self.tap, run_id=123,
                                    run_attempt=1)
        m.produce_handoff(self.args, self.formula)
        return json.loads((self.root / "bottle-handoff.json").read_text())

    def run_api(self, path, data=None, missing=False):
        if "/actions/runs/" in path:
            return {"path": ".github/workflows/publish.yml", "event": "workflow_dispatch", "head_branch": "main",
                    "head_sha": self.base, "status": "completed", "conclusion": "success"}
        return self.api(path, data, missing)

    def attestation(self, *args, **kwargs):
        self.assertEqual(args[:2], ("attestation", "verify"))
        self.assertIn("--deny-self-hosted-runners", args)
        self.assertEqual(args[args.index("--source-digest") + 1], self.base)
        self.assertEqual(args[args.index("--signer-workflow") + 1], m.REPO + "/.github/workflows/publish.yml")
        return json.dumps([{"verificationResult": {"signature": {"certificate": {
            "runInvocationURI": f"https://github.com/{m.REPO}/actions/runs/123/attempts/1"}}}}]).encode()

    def test_real_handoff_survives_download_directory_relocation(self):
        record = self.make_handoff()
        moved = self.root / "downloaded"
        moved.mkdir()
        for name in [*record["payloads"], "bottle-handoff.json"]:
            (moved / name).write_bytes((self.root / name).read_bytes())
        self.args.bottle_dir = moved
        with patch.object(m, "api", self.run_api), patch.object(m, "gh", self.attestation):
            verified, formula = m.verify_handoff(self.args)
        self.assertEqual(verified, record)
        self.assertEqual(formula, self.formula)
        self.assertIn(record["producerCommit"], m.git(self.tap, "bundle", "verify", str(moved / "reviewed-bottle.bundle")))

    def test_changed_bundle_never_reaches_provenance_or_publication(self):
        self.make_handoff()
        (self.root / "reviewed-bottle.bundle").write_bytes(b"tampered bundle")
        with patch.object(m, "api", self.run_api), patch.object(m, "gh") as gh:
            with self.assertRaisesRegex(ValueError, "payload identity changed"):
                m.verify_handoff(self.args)
            gh.assert_not_called()

    def test_wrong_signed_run_is_rejected(self):
        self.make_handoff()
        def other(*args, **kwargs):
            return self.attestation(*args, **kwargs).replace(b"runs/123/", b"runs/124/")
        with patch.object(m, "api", self.run_api), patch.object(m, "gh", other):
            with self.assertRaisesRegex(ValueError, "selected producer run"):
                m.verify_handoff(self.args)

    def test_failed_producer_is_rejected_before_provenance(self):
        self.make_handoff()
        def failed(path, data=None, missing=False):
            row = self.run_api(path, data, missing)
            row["conclusion"] = "failure"
            return row
        with patch.object(m, "api", failed), patch.object(m, "gh") as gh:
            with self.assertRaisesRegex(ValueError, "successful exact-base"):
                m.verify_handoff(self.args)
            gh.assert_not_called()

    def test_non_formula_reviewed_changes_cannot_produce_handoff(self):
        self.make_handoff()
        (self.tap / "unexpected-source.txt").write_text("owned negative")
        self.git("add", "unexpected-source.txt")
        self.git("commit", "-m", "owned unexpected source")
        self.args.head_sha = self.git("rev-parse", "HEAD")
        self.git("commit", "--allow-empty", "-m", "owned empty final")
        with self.assertRaisesRegex(ValueError, "source PR changes files beyond"):
            m.produce_handoff(self.args, self.formula)

    def test_finalizer_uses_real_bundle_scope_before_model_publication_and_push(self):
        record = self.make_handoff()
        self.git("remote", "add", "origin", f"https://github.com/{m.REPO}.git")
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        real_git = m.git
        pushed = []
        def controlled_git(tap, *args):
            if args[:2] == ("fetch", "origin"):
                return ""  # All fixture objects are local; no network access in this test.
            if args[0] == "push":
                self.assertTrue(self.release["immutable"])
                self.assertIn(("public-download",), self.events)
                self.assertEqual(args, ("push", "origin", record["producerCommit"] + ":refs/heads/main"))
                pushed.append(args)
                return ""
            return real_git(tap, *args)
        def controlled_gh(*args, **kwargs):
            if args[0] == "attestation":
                return self.attestation(*args, **kwargs)
            return BottlePublicationTests.gh(self, *args, **kwargs)
        with patch.object(m, "api", self.run_api), patch.object(m, "gh", controlled_gh), \
             patch.object(m, "git", controlled_git), patch.object(m.distribution, "read_url", self.read):
            self.assertEqual(m.finalize(self.args), 0)
        self.assertEqual(len(pushed), 1)
        self.assertEqual(self.git("rev-parse", "HEAD"), record["producerCommit"])

    def test_public_main_change_stops_finalizer_before_release_creation(self):
        self.make_handoff()
        self.git("remote", "add", "origin", f"https://github.com/{m.REPO}.git")
        self.git("update-ref", "refs/remotes/origin/main", self.head)
        real_git = m.git
        def controlled_git(tap, *args):
            return "" if args[:2] == ("fetch", "origin") else real_git(tap, *args)
        with patch.object(m, "api", self.run_api), patch.object(m, "gh", self.attestation), patch.object(m, "git", controlled_git):
            with self.assertRaisesRegex(ValueError, "main advanced since producer"):
                m.finalize(self.args)
        self.assertIsNone(self.release)

    def test_extra_bottle_json_cannot_be_injected_after_handoff(self):
        self.make_handoff()
        (self.root / "unexpected.bottle.json").write_text(self.json_file.read_text())
        with patch.object(m, "api", self.run_api), patch.object(m, "gh") as gh:
            with self.assertRaises(ValueError):
                m.verify_handoff(self.args)
            gh.assert_not_called()


if __name__ == "__main__":
    unittest.main()
