#!/usr/bin/env python3
"""Bounded read-only MCP smoke test of an explicitly selected RIGHTCLICK binary.

No provider actions, credentials, configuration, installs, or releases are changed.
Normal RIGHTCLICK process startup may create its own log and discover providers.
This is an installed-process check, not an 11-substrate execution proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
from typing import Any

TOOLS = frozenset({"context_runtime", "context_inspect", "context_actions", "context_explain",
                   "context_run", "context_run_status", "context_providers"})
SENTINEL = "RIGHTCLICK package acceptance"
MAX_FRAME = 1_048_576


class AcceptanceError(RuntimeError):
    pass


def _object(value: Any, what: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AcceptanceError(f"{what}: expected an object")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise AcceptanceError("Duplicate JSON object key")
        obj[key] = value
    return obj


def _json(data: str | bytes) -> Any:
    try:
        return json.loads(data, object_pairs_hook=_unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(AcceptanceError("Non-finite JSON number")))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise AcceptanceError("Invalid JSON") from exc


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _tool_result(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("isError", False) is not False:
        raise AcceptanceError("MCP tool returned an error")
    content = result.get("content")
    if not isinstance(content, list) or len(content) != 1:
        raise AcceptanceError("Expected a single JSON text result")
    block = _object(content[0], "tool content")
    if block.get("type") != "text" or not isinstance(block.get("text"), str):
        raise AcceptanceError("Expected JSON text tool content")
    return _object(_json(block["text"]), "tool result")


def _tools(result: dict[str, Any]) -> list[str]:
    tools = result.get("tools")
    if result.get("nextCursor") is not None or not isinstance(tools, list):
        raise AcceptanceError("Unexpected paginated or missing tool list")
    names = [_object(tool, "tool").get("name") for tool in tools]
    if len(names) != 7 or any(not isinstance(n, str) for n in names) or set(names) != TOOLS:
        raise AcceptanceError("Tool surface is not exactly the seven RIGHTCLICK operations")
    return sorted(names)


def _schema_digest(result: dict[str, Any]) -> str:
    # Validate names before indexing. Canonical JSON ignores object/listing
    # ordering but retains every schema/description field and array value.
    _tools(result)
    declarations = sorted(result["tools"], key=lambda tool: tool["name"])
    try:
        canonical = json.dumps(declarations, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise AcceptanceError("Malformed operation declaration") from exc
    return hashlib.sha256(canonical).hexdigest()


def verify(binary: Path, expected_version: str, timeout: float = 30.0, *,
           expected_sha256: str | None = None) -> dict[str, Any]:
    if not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise AcceptanceError("Timeout must be positive and at most 120 seconds")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?", expected_version):
        raise AcceptanceError("An explicit semantic expected version is required")
    if expected_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise AcceptanceError("Expected executable SHA-256 must be exactly 64 lowercase hexadecimal characters")
    executable = binary.expanduser().resolve(strict=True)
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise AcceptanceError("Selected binary is not executable")
    before_hash = _digest(executable)
    if expected_sha256 is not None and before_hash != expected_sha256:
        raise AcceptanceError("Selected executable does not match the independently supplied SHA-256")
    frames: queue.Queue[bytes | Exception] = queue.Queue(maxsize=32)
    stopping = threading.Event()
    end = time.monotonic() + timeout
    process = subprocess.Popen([str(executable), "mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, bufsize=0)
    assert process.stdin is not None and process.stdout is not None

    def enqueue(value: bytes | Exception) -> None:
        while not stopping.is_set():
            try:
                frames.put(value, timeout=0.05)
                return
            except queue.Full:
                pass

    def read_frames() -> None:
        try:
            while not stopping.is_set():
                line = process.stdout.readline(MAX_FRAME + 1)
                if not line:
                    enqueue(AcceptanceError("MCP process closed stdout"))
                    return
                if len(line) > MAX_FRAME or not line.endswith(b"\n"):
                    enqueue(AcceptanceError("Oversized or incomplete MCP frame"))
                    return
                enqueue(line)
        except (OSError, ValueError):
            enqueue(AcceptanceError("MCP output read failed"))

    reader = threading.Thread(target=read_frames, daemon=True)
    reader.start()

    def send(message: dict[str, Any]) -> None:
        try:
            process.stdin.write(json.dumps(message, separators=(",", ":")).encode() + b"\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise AcceptanceError("MCP process closed stdin") from exc

    def request(ident: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
        send({"jsonrpc": "2.0", "id": ident, "method": method, "params": params})
        for _ in range(33):
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise AcceptanceError("MCP acceptance deadline exceeded")
            try:
                raw = frames.get(timeout=remaining)
            except queue.Empty as exc:
                raise AcceptanceError("MCP acceptance deadline exceeded") from exc
            if isinstance(raw, Exception):
                raise raw
            response = _object(_json(raw), "MCP frame")
            if response.get("jsonrpc") != "2.0":
                raise AcceptanceError("Invalid JSON-RPC version")
            if "id" not in response and isinstance(response.get("method"), str):
                continue  # bounded server notifications, never a tool execution
            if type(response.get("id")) is not int or response["id"] != ident:
                raise AcceptanceError("Unexpected JSON-RPC response ID")
            if "error" in response:
                raise AcceptanceError("MCP returned a JSON-RPC error")
            return _object(response.get("result"), "MCP result")
        raise AcceptanceError("Too many unsolicited MCP notifications")

    try:
        init = request(1, "initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                        "clientInfo": {"name": "rightclick-package-acceptance", "version": "1.0.0"}})
        # Server negotiates a supported version; this probe does not claim newest-protocol coverage.
        if not isinstance(init.get("protocolVersion"), str) or not init["protocolVersion"]:
            raise AcceptanceError("Missing negotiated protocol version")
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        first_listing = request(2, "tools/list", {})
        names = _tools(first_listing)
        schema_digest = _schema_digest(first_listing)
        runtime = _tool_result(request(3, "tools/call", {"name": "context_runtime", "arguments": {}}))
        if runtime.get("product") != "RIGHTCLICK" or runtime.get("version") != expected_version:
            raise AcceptanceError("Runtime product/version mismatch")
        if runtime.get("transport") != "stdio" or type(runtime.get("pid")) is not int or runtime["pid"] != process.pid:
            raise AcceptanceError("Runtime transport/process mismatch")
        reported_path = runtime.get("executableRealPath")
        if not isinstance(reported_path, str) or Path(reported_path).resolve() != executable:
            raise AcceptanceError("Runtime executable path mismatch")
        if runtime.get("executableSHA256") != before_hash:
            raise AcceptanceError("Runtime executable hash mismatch")
        inspected = _tool_result(request(4, "tools/call", {"name": "context_inspect", "arguments": {"item": SENTINEL}}))
        if (inspected.get("kind"), inspected.get("text"), inspected.get("typeIdentifier"), inspected.get("byteCount")) != (
                "text", SENTINEL, "public.plain-text", len(SENTINEL.encode())):
            raise AcceptanceError("Read-only inspection mismatch")
        final_listing = request(5, "tools/list", {})
        if names != _tools(final_listing) or schema_digest != _schema_digest(final_listing):
            raise AcceptanceError("Top-level operation surface changed")
        if _digest(executable) != before_hash:
            raise AcceptanceError("Executable changed during acceptance")
        return {"status": "PASS", "scope": "installed stdio process; runtime identity and read-only inspection",
                "version": expected_version, "binarySHA256": before_hash, "toolCount": 7,
                "artifactIdentity": "PINNED_SHA256_MATCH" if expected_sha256 is not None else "LOCAL_CONSISTENCY_ONLY",
                "operations": names, "toolSchemaSHA256": schema_digest, "providerActionsInvoked": 0,
                "elevenSubstrateProof": "NOT_RUN", "modernDiscoveryProtocol": "NOT_TESTED"}
    finally:
        stopping.set()
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=2)
        process.stdin.close()
        reader.join(timeout=1)
        process.stdout.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--expected-sha256", help="Independently trusted SHA-256 of the executable, not the source archive or bottle")
    parser.add_argument("--timeout", type=float, default=30)
    options = parser.parse_args()
    try:
        print(json.dumps(verify(options.binary, options.expected_version, options.timeout,
                               expected_sha256=options.expected_sha256), indent=2, sort_keys=True))
        return 0
    except (AcceptanceError, OSError, subprocess.SubprocessError) as exc:
        # Never echo arbitrary server output, environment, credentials, or payloads.
        print(json.dumps({"status": "FAIL", "reason": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
