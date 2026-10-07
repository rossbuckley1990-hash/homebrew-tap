import copy
import hashlib
import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts/check-distribution.py"
spec = importlib.util.spec_from_file_location("distribution", path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.source = b"release source fixture"
        self.sha = hashlib.sha256(self.source).hexdigest()
        self.url = f"{m.ROOT}/v0.2.2/rightclick-0.2.2-source.tar.gz"
        self.sums_url = f"{m.ROOT}/v0.2.2/SHA256SUMS-source"
        self.formula = (f'class Rightclick < Formula\n  url "{self.url}"\n'
                        f'  sha256 "{self.sha}"\n'
                        '  resource "openai-tunnel-client" do\n'
                        '    url "https://example.test/tunnel.zip"\n'
                        f'    sha256 "{"a" * 64}"\n  end\nend\n')
        self.files = {self.url: self.source, self.sums_url:
                      f"{self.sha}  rightclick-0.2.2-source.tar.gz\n".encode()}
        self.release = {"tag_name": "v0.2.2", "draft": False, "prerelease": False,
                        "assets": [self.asset(self.url, self.sha), self.asset(self.sums_url)]}

    @staticmethod
    def asset(url, sha=None):
        return {"name": url.rsplit("/", 1)[1], "state": "uploaded",
                "browser_download_url": url, "digest": f"sha256:{sha}" if sha else None}

    def verify(self, formula=None, generated=None):
        return m.verify_source(formula or self.formula, self.release,
                               generated or self.formula, self.files.__getitem__)

    def test_aligned_release(self):
        self.assertTrue(self.verify()["source_aligned"])

    def test_missing_metadata_digest_still_hashes_download(self):
        self.release["assets"][0].pop("digest")
        self.assertTrue(self.verify()["source_aligned"])
        self.files[self.url] = b"tampered"
        with self.assertRaisesRegex(ValueError, "Downloaded source"):
            self.verify()

    def test_bad_release_states_and_version(self):
        for key, value in [("tag_name", "v0.2.3"), ("draft", True), ("prerelease", True)]:
            with self.subTest(key=key):
                before = copy.deepcopy(self.release)
                self.release[key] = value
                with self.assertRaises(ValueError):
                    self.verify()
                self.release = before

    def test_source_asset_failures(self):
        for key, value in [("state", "new"), ("digest", "sha256:" + "b" * 64),
                           ("browser_download_url", "https://untrusted.test/archive")]:
            with self.subTest(key=key):
                before = copy.deepcopy(self.release)
                self.release["assets"][0][key] = value
                with self.assertRaises(ValueError):
                    self.verify()
                self.release = before

    def test_duplicate_or_missing_source_asset(self):
        for assets in [self.release["assets"][1:], self.release["assets"] + [self.release["assets"][0]]]:
            before = self.release["assets"]
            self.release["assets"] = assets
            with self.assertRaises(ValueError):
                self.verify()
            self.release["assets"] = before

    def test_checksum_file_cannot_be_missing_wrong_or_duplicated(self):
        valid = self.files[self.sums_url]
        for body in [b"", valid.replace(self.sha.encode(), b"b" * 64), valid + valid]:
            self.files[self.sums_url] = body
            with self.assertRaises(ValueError):
                self.verify()

    def test_source_pin_cannot_be_inherited_from_resource(self):
        broken = self.formula.replace(f'  sha256 "{self.sha}"\n', "")
        with self.assertRaises(ValueError):
            self.verify(broken)

    def test_url_version_must_match_asset_name(self):
        with self.assertRaises(ValueError):
            self.verify(self.formula.replace("download/v0.2.2/", "download/v0.2.3/"))

    def test_upstream_source_pin_must_match(self):
        with self.assertRaisesRegex(ValueError, "upstream generated"):
            self.verify(generated=self.formula.replace(self.sha, "b" * 64))

    def test_tunnel_resource_cannot_drift_or_disappear(self):
        for value in [self.formula.replace("a" * 64, "b" * 64),
                      self.formula.replace("openai-tunnel-client", "different-resource"),
                      self.formula.replace("https://example.test/tunnel.zip", "https://other.test/a")]:
            with self.assertRaises(ValueError):
                self.verify(value)

    def bottle(self, rebuild=0, revision=0):
        data = b"built binary fixture"
        sha = hashlib.sha256(data).hexdigest()
        root = f"https://github.com/{m.TAP}/releases/download/rightclick-0.2.2"
        package = "0.2.2" + (f"_{revision}" if revision else "")
        name = f"rightclick-{package}.arm64_tahoe.bottle" + (f".{rebuild}" if rebuild else "") + ".tar.gz"
        url = f"{root}/{name}"
        extra = f"    rebuild {rebuild}\n" if rebuild else ""
        block = f'  bottle do\n    root_url "{root}"\n{extra}    sha256 cellar: :any_skip_relocation, arm64_tahoe: "{sha}"\n  end\n'
        formula = self.formula + block + (f"  revision {revision}\n" if revision else "")
        release = {"tag_name": "rightclick-0.2.2", "draft": False, "prerelease": False,
                   "assets": [self.asset(url, sha)]}
        self.files[url] = data
        return formula, release, url

    def test_bottle_bytes_and_generated_pin(self):
        formula, release, url = self.bottle()
        self.assertEqual(m.verify_bottle(formula, release, self.files.__getitem__), [url.rsplit("/", 1)[1]])
        self.files[url] = b"corrupt binary"
        with self.assertRaisesRegex(ValueError, "Downloaded bottle"):
            m.verify_bottle(formula, release, self.files.__getitem__)

    def test_bottle_rebuild_and_formula_revision(self):
        formula, release, _ = self.bottle(rebuild=2, revision=1)
        self.assertEqual(len(m.verify_bottle(formula, release, self.files.__getitem__)), 1)

    def test_old_bottle_release_is_not_source_alignment(self):
        formula, release, _ = self.bottle()
        release["tag_name"] = "rightclick-0.1.1"
        with self.assertRaises(ValueError):
            m.verify_bottle(formula, release, self.files.__getitem__)

    def test_missing_bottle_block_or_wrong_platform(self):
        formula, release, _ = self.bottle()
        for changed in [self.formula, formula.replace("arm64_tahoe", "ventura")]:
            with self.assertRaises(ValueError):
                m.verify_bottle(changed, release, self.files.__getitem__)

    def test_stale_bottle_root_or_missing_asset(self):
        formula, release, _ = self.bottle()
        with self.assertRaises(ValueError):
            m.verify_bottle(formula.replace("download/rightclick-0.2.2", "download/rightclick-0.1.1"), release, self.files.__getitem__)
        release["assets"] = []
        with self.assertRaises(ValueError):
            m.verify_bottle(formula, release, self.files.__getitem__)

    def test_network_errors_propagate(self):
        def failed(_):
            raise OSError("offline")
        with self.assertRaises(OSError):
            m.verify_source(self.formula, self.release, self.formula, failed)

    def test_redirects_drop_credentials_and_refuse_http(self):
        request = m.urllib.request.Request("https://api.github.com/example", headers={"Authorization": "secret"})
        redirect = m.SafeRedirect()
        result = redirect.redirect_request(request, None, 302, "", {}, "https://downloads.test/a")
        self.assertIsNone(result.get_header("Authorization"))
        with self.assertRaises(ValueError):
            redirect.redirect_request(request, None, 302, "", {}, "http://downloads.test/a")


if __name__ == "__main__":
    unittest.main()
