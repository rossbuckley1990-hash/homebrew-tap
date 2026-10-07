# RCIR companion release readiness — 2026-10-07

The probe implementation and 38 local tests pass. The existing installed 0.2.2 process passes identity, exact-seven-tools and read-only inspection. Schema review added four controls. All 21 probe fixtures and brew test-bot passed on exact source `79a05ff7c666d6df7d3b1d63113f6bf6aed0d412`. [PR 8](https://github.com/rossbuckley1990-hash/homebrew-tap/pull/8) merged normally as `ad42e817f27ab6eb2634b13759e2a2ea3a3ada3f`. Candidate package publication, fresh installation and reconnected-client RCIR execution are NOT_RUN.

This candidate does not modify the formula, release assets, version, source checksum, bottle checksum, platform support or tunnel resource. It preserves concurrent main's 0.2.2 bottle block. The source archive and binary bottle have different bytes and hashes; neither the formula text nor a version match proves those bytes were downloaded or used by a client.

Require the runtime's G2 public effect/observation proof, applicable native/portable checks, reviewed immutable candidate and actual publication first. After publication, independently download/check the assets, run distribution checks with `--require-bottle`, install outside a maintainer checkout/cache, run this probe against the resulting executable, reconnect the client and verify a real RCIR task. Retain failures/skips; do not equate fixture tests or source taxonomy with installed acceptance. See [execution ledger](EXECUTION-LEDGER.md) and [probe contract](RCIR-ACCEPTANCE.md).

## Next upstream version

The next unpublished numerical runtime candidate is 0.2.3. The accepted Stable formula remains 0.2.2 with source SHA256 `a3953eb8f1be2f9123d694b90202244c94ee21971171972f8ce1d3bacf807ca5` and arm64 Tahoe bottle SHA256 `147828d2ad81b0238c4d733ad757c5c584b7fe359a58db34552052641ea762fd`. GitHub reports the current upstream release as non-immutable; preserve existing tags and assets regardless.

Prepare the eventual formula update from the accepted new upstream source archive’s independently downloaded bytes. Publish a matching new bottle, verify both hashes and installed behavior, then reconnect the client and attest the new executable. Candidate source, connector-package metadata, published assets and installed runtime are separate identities. This documentation change does not alter formula pins or prove those pending release gates.
