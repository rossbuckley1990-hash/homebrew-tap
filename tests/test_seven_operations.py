import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("probe", ROOT / "scripts/verify-seven-operations.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

FAKE = r'''#!/usr/bin/env python3
import hashlib, json, os, pathlib, sys, time
MODE = __MODE__
names = ["context_runtime", "context_inspect", "context_actions", "context_explain", "context_run", "context_run_status", "context_providers"]
for line in sys.stdin:
    req = json.loads(line)
    if "id" not in req: continue
    if MODE == "timeout": time.sleep(10)
    if MODE == "oversized": print("x" * 1048577, flush=True); continue
    if MODE == "duplicate_json": print('{"jsonrpc":"2.0","jsonrpc":"2.0","id":1,"result":{}}', flush=True); continue
    if MODE == "notification_flood":
        for i in range(35): print(json.dumps({"jsonrpc":"2.0", "method":"notifications/progress"}), flush=True)
        continue
    method = req["method"]
    if method == "initialize": result = {"protocolVersion":"2025-03-26"}
    elif method == "tools/list":
        listing = list(names)
        if MODE == "missing": listing.pop()
        if MODE == "extra": listing.append("provider_specific_tool")
        if MODE == "duplicate": listing[-1] = listing[0]
        result = {"tools":[{"name": n} for n in listing]}
        if MODE == "pagination": result["nextCursor"] = "more"
    elif method == "tools/call":
        call = req["params"]["name"]
        if call == "context_runtime":
            path = str(pathlib.Path(__file__).resolve())
            value = {"product":"RIGHTCLICK", "version":"0.2.2", "transport":"stdio", "pid":os.getpid(),
                     "executableRealPath":path, "executableSHA256":hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()}
            if MODE == "wrong_hash": value["executableSHA256"] = "0" * 64
            if MODE == "wrong_version": value["version"] = "0.0.0"
            if MODE == "wrong_pid": value["pid"] += 1
            if MODE == "wrong_path": value["executableRealPath"] = "/not/this/process"
        elif call == "context_inspect":
            text = req["params"]["arguments"]["item"]
            value = {"kind":"text", "text":text, "typeIdentifier":"public.plain-text", "byteCount":len(text.encode())}
            if MODE == "wrong_inspection": value["text"] = "different"
        else: raise RuntimeError("A provider action or unexpected operation was invoked!")
        result = {"content":[{"type":"text", "text":json.dumps(value)}], "isError": MODE == "tool_error"}
    else: raise RuntimeError("Unexpected protocol method")
    ident = req["id"] + (1 if MODE == "wrong_id" else 0)
    print(json.dumps({"jsonrpc":"2.0", "id":ident, "result":result}), flush=True)
'''

class SevenOperationTests(unittest.TestCase):
    def run_probe(self, mode, timeout=3):
        with tempfile.TemporaryDirectory(prefix="rightclick-mcp-fixture-") as work:
            path = Path(work) / "fake-rightclick"
            path.write_text(FAKE.replace("__MODE__", repr(mode)))
            path.chmod(0o700)
            return probe.verify(path, "0.2.2", timeout=timeout)

    def test_explicit_fixture_passes_and_invokes_no_provider_action(self):
        result = self.run_probe("pass")
        self.assertEqual(result["toolCount"], 7)
        self.assertEqual(result["providerActionsInvoked"], 0)
        self.assertEqual(result["elevenSubstrateProof"], "NOT_RUN")

    def test_missing_tool(self):
        with self.assertRaises(probe.AcceptanceError): self.run_probe("missing")
    def test_extra_tool(self):
        with self.assertRaises(probe.AcceptanceError): self.run_probe("extra")
    def test_duplicate_tool(self):
        with self.assertRaises(probe.AcceptanceError): self.run_probe("duplicate")
    def test_pagination(self):
        with self.assertRaises(probe.AcceptanceError): self.run_probe("pagination")
    def test_wrong_hash(self):
        with self.assertRaises(probe.AcceptanceError): self.run_probe("wrong_hash")
    def test_wrong_version(self):
        with self.assertRaises(probe.AcceptanceError): self.run_probe("wrong_version")
    def test_wrong_pid(self):
        with self.assertRaises(probe.AcceptanceError): self.run_probe("wrong_pid")
    def test_wrong_path(self):
        with self.assertRaises(probe.AcceptanceError): self.run_probe("wrong_path")
    def test_wrong_inspection(self):
        with self.assertRaises(probe.AcceptanceError): self.run_probe("wrong_inspection")
    def test_tool_error(self):
        with self.assertRaises(probe.AcceptanceError): self.run_probe("tool_error")
    def test_wrong_id(self):
        with self.assertRaises(probe.AcceptanceError): self.run_probe("wrong_id")
    def test_duplicate_json(self):
        with self.assertRaises(probe.AcceptanceError): self.run_probe("duplicate_json")
    def test_notification_flood(self):
        with self.assertRaises(probe.AcceptanceError): self.run_probe("notification_flood")
    def test_timeout(self):
        with self.assertRaises(probe.AcceptanceError): self.run_probe("timeout", timeout=0.2)
    def test_oversized_frame(self):
        with self.assertRaises(probe.AcceptanceError): self.run_probe("oversized")
    def test_invalid_timeout(self):
        with self.assertRaises(probe.AcceptanceError): probe.verify(Path("/nonexistent"), "0.2.2", float("nan"))

if __name__ == "__main__": unittest.main()
