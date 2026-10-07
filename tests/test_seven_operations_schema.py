"""Additional probe controls. Original seventeen fixture tests are unchanged."""
from pathlib import Path
import tempfile
import unittest
from test_seven_operations import FAKE, probe

SCHEMA_FAKE = FAKE.replace(
    'result = {"tools":[{"name": n} for n in listing]}',
    '''result = {"tools":[{"name": n, "inputSchema":{"type":"object", "properties":{"item":{"type":
            "number" if MODE == "schema_drift" and req["id"] == 5 else "string"}}}} for n in listing]}
        if MODE == "reordered" and req["id"] == 5: result["tools"].reverse()
        if MODE == "bad_unicode": result["tools"][0]["inputSchema"]["description"] = "\\ud800"''')


class SevenOperationSchemaTests(unittest.TestCase):
    def run_probe(self, mode):
        with tempfile.TemporaryDirectory(prefix="rightclick-schema-fixture-") as work:
            binary = Path(work) / "explicit-fake-mcp-process"
            binary.write_text(SCHEMA_FAKE.replace("__MODE__", repr(mode)))
            binary.chmod(0o700)
            return probe.verify(binary, "0.2.2", timeout=3)

    def test_same_names_changed_schema_is_rejected(self):
        with self.assertRaises(probe.AcceptanceError):
            self.run_probe("schema_drift")

    def test_stable_schema_records_fingerprint(self):
        result = self.run_probe("pass")
        self.assertRegex(result["toolSchemaSHA256"], r"^[0-9a-f]{64}$")

    def test_listing_order_does_not_change_fingerprint(self):
        self.assertEqual(self.run_probe("pass")["toolSchemaSHA256"],
                         self.run_probe("reordered")["toolSchemaSHA256"])

    def test_invalid_unicode_schema_fails_closed(self):
        with self.assertRaises(probe.AcceptanceError):
            self.run_probe("bad_unicode")
