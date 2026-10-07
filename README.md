<div align="center">

# RIGHTCLICK · Homebrew

### Install the runtime. Let your AI discover the capabilities.

The official Homebrew distribution path for [RIGHTCLICK](https://github.com/rossbuckley1990-hash/rightclick):<br>
**one fixed MCP interface for supported local software, APIs and other runtimes.**

[![Stable source](https://img.shields.io/github/v/release/rossbuckley1990-hash/rightclick?label=stable%20source&color=9b87f5)](https://github.com/rossbuckley1990-hash/rightclick/releases/latest)
[![Distribution checks](https://github.com/rossbuckley1990-hash/homebrew-tap/actions/workflows/distribution-guard.yml/badge.svg)](https://github.com/rossbuckley1990-hash/homebrew-tap/actions/workflows/distribution-guard.yml)
[![Homebrew tests](https://github.com/rossbuckley1990-hash/homebrew-tap/actions/workflows/tests.yml/badge.svg)](https://github.com/rossbuckley1990-hash/homebrew-tap/actions/workflows/tests.yml)

[Install](#install) · [Connect your AI](#connect-your-ai) · [Upgrade](#upgrade-and-check) · [Capabilities](#what-you-are-installing) · [Release integrity](#source-releases-and-binary-bottles)

<img src="docs/media/rightclick-hero-architecture.gif" alt="Supplied RIGHTCLICK 0.2.2 architecture illustration showing three service substrates behind one generic interface" width="960">

<sub>Architecture illustration, not a raw execution transcript. [Explore the evidence](https://github.com/rossbuckley1990-hash/rightclick#see-the-evidence).</sub>

</div>

## Install

```bash
brew install rossbuckley1990-hash/tap/rightclick
rightclick version
rightclick doctor
```

**Apple Silicon, macOS 14+ target.** A source build requires **Swift 6.2+** from the free Apple Command Line Tools. Update the tools through Software Update when needed. No paid Apple Developer account is required.

A matching precompiled bottle is used only when its platform and checksum are published in [Formula/rightclick.rb](Formula/rightclick.rb). Otherwise Homebrew builds the pinned source with locked dependency revisions inside its build sandbox. Do not mistake the existence of a source tarball for a ready-to-pour binary bottle.

## Connect your AI

Preview the detected supported local clients, then apply:

```bash
rightclick setup --all --dry-run --json
rightclick setup --all --yes
```

Select a single client with `--client cursor`, `--client claude` (Claude Code), or `--client codex`. For another compatible MCP client, configure the installed `rightclick` executable with the argument `mcp` for stdio transport. [Generic client configuration and agent guide](https://github.com/rossbuckley1990-hash/rightclick#for-agents-and-mcp-builders).

The persistent ChatGPT bridge has a separate preview and setup path:

```bash
rightclick setup chatgpt --dry-run --json
rightclick setup chatgpt --yes
```

The formula includes RIGHTCLICK's pinned tunnel-client compatibility resource and its required licence, notice and dependency materials. Ordinary local MCP use does not require pairing the ChatGPT bridge.

**First prompt:**

```text
Use RIGHTCLICK to inspect this item and discover what my software can do with it.
Explain the applicable capabilities and their current schemas before acting.
Ask before modifying files or sending data. Verify the result after any approved action.
```

## What you are installing

The stable **0.2.2** capability families include macOS Services, sharing, supported OpenAPI, GraphQL and gRPC reflection, capability-artifact resolution, ARD acquisition and configured MCP federation. Origin-bound authority and explicit verification keep discovery, permission, provider acceptance and observable success separate.

The AI sees the same seven operations: `context_runtime`, `context_inspect`, `context_providers`, `context_actions`, `context_explain`, `context_run` and `context_run_status`.

**Important limits:** Finder Action extensions are discovery-only. Schemas and gRPC operations have supported subsets. OAuth/OIDC foundations are not universal automatic login. The full stable runtime targets macOS; Linux ARD component evidence is not a Windows/Linux full-runtime release. Untagged `main`, feature branches and roadmap items are not installed automatically.

The source repository contains reproducible evidence of [BBEdit adding five capabilities without provider-specific code](https://github.com/rossbuckley1990-hash/rightclick/blob/main/docs/BBEDIT-PROOF.md), [multi-application image processing](https://github.com/rossbuckley1990-hash/rightclick/blob/main/evidence/v0.1-scalability-blind/composition-png-jpeg-optim/REPORT.md), [CSV-to-chart composition](https://github.com/rossbuckley1990-hash/rightclick/blob/main/evidence/v0.1-scalability-blind/cross-domain-csv-chart/REPORT.md) and [reflected GitHub self-hosting](https://github.com/rossbuckley1990-hash/rightclick/blob/main/evidence/self-hosting-2026-10-07/README.md). Each experiment states its original date and version; they are not all claimed as freshly repeated on 0.2.2.

[Full capability matrix](https://github.com/rossbuckley1990-hash/rightclick#what-it-can-do) · [Security boundaries](https://github.com/rossbuckley1990-hash/rightclick/blob/main/SECURITY.md)

## Upgrade and check

```bash
brew update
brew upgrade rightclick
rightclick version
rightclick doctor
brew test rossbuckley1990-hash/tap/rightclick
```

For an existing ChatGPT bridge, also inspect `rightclick setup chatgpt --dry-run --json` and confirm that the connected `context_runtime` reports the upgraded executable and hash. A changed package or setup file alone does not establish that the live connection uses it. Do not delete pairing state merely to upgrade.

## Source releases and binary bottles

[Formula/rightclick.rb](Formula/rightclick.rb) is the installation pin. It references a versioned [upstream source release](https://github.com/rossbuckley1990-hash/rightclick/releases/latest), exact source SHA256 and pinned compatibility resources.

A **bottle** is a separate precompiled Homebrew package. A complete binary publication requires a matching `bottle do` block, platform checksum and downloadable asset in [tap releases](https://github.com/rossbuckley1990-hash/homebrew-tap/releases). An older tap release, a merged formula PR or successful source tests is not evidence that the current binary bottle exists.

Use these live sources instead of relying on duplicated “latest” version labels. The distribution guard keeps source alignment and actual binary availability separate and reports missing bottles rather than making them appear green.

## Runtime portability and the stable package

Homebrew is a distribution adapter for RIGHTCLICK, not a requirement of the capability runtime. The [upstream portable-runtime candidate](https://github.com/rossbuckley1990-hash/rightclick/pull/49) converges one engine and seven-operation MCP contract across macOS, Linux and Windows, with native discovery behind platform host boundaries. Its portability matrix and release gates remain candidate evidence until the implementation is reviewed, tested and merged.

The next unpublished upstream runtime candidate is **0.2.3**, under review in PR49. This tap continues to install accepted **0.2.2** source and its matching bottle until the new candidate passes its release gates and independently verified immutable assets exist. A candidate version bump does not update installed bytes.

RIGHTCLICK Stable and Edge connector packages have their own version numbers. Use the runtime’s `context_runtime` attestation to identify the serving executable; connector metadata does not establish a runtime release or capability acceptance.

This tap still pins the published macOS release by content checksum. GitHub currently reports v0.2.2 as non-immutable; a checksum pin does not change that release setting. Its Apple Silicon/macOS restriction and bundled Darwin tunnel-client match the published bytes. Removing those restrictions before updating the accepted source release would produce a broken Linux installation.

Before distributing a portable release, require upstream macOS, Linux and Windows integrated build/test and real-provider MCP acceptance on the exact release source. Publish and independently verify a new immutable source asset before moving this formula's URL/checksum. Preserve the reviewed bottle workflow and run the distribution guard against the installed package. Add Linux eligibility only when that pinned source and its formula build pass on Linux; platform-specific tunnel resources must be conditional. Windows uses the same upstream runtime source and separate installation packaging, without depending on this tap.

## Maintainer release gates

Source and resource pins come from upstream `packaging/tap/Formula/rightclick.rb` at the release tag. Preserve Homebrew style corrections and required third-party notices. Never force-move a release tag or reuse old bottle checksums.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check-distribution.py
```

The read-only check compares the stable upstream release, formula source/resource pins and published checksum file, and independently downloads and hashes the source bytes. It does not install software or modify either repository.

Formula PRs use Apple Silicon `brew test-bot`. After the relevant exact head and distribution guard pass, use **brew pr-pull** with the reviewed PR number and head SHA. Independently verify the resulting formula, release, bottle bytes and installed behaviour. Avoid concurrent release jobs; re-read the current refs immediately before publication.

The manual `brew pr-pull` workflow produces an attested handoff. It applies only the reviewed formula PR with `--clean --no-upload`, merges bottle pins locally with `brew bottle --merge --write --no-commit`, audits the formula and commits only its bottle metadata. CI attests the bottle bytes, JSON, formula, commit bundle and closed handoff manifest. It does not publish releases or push public formula pins, and requires no administration secret.

After the producer succeeds, download its `bottle-publication-<reviewed-head>` artifact into an otherwise empty directory. Use a clean private clone of this tap and the existing authorized GitHub CLI account to finalize it:

```bash
python3 scripts/stage-bottle-release.py finalize \
  --bottle-dir /absolute/path/to/downloaded-artifact \
  --tap-path /absolute/path/to/private-tap-clone \
  --head-sha <reviewed-formula-PR-head> --pull-request <formula-PR-number> \
  --producer-base <producer-workflow-main-SHA> --run-id <producer-run-ID> --run-attempt 1
```

The finalizer requires a successful exact workflow run and cryptographically verified provenance for every retained payload, including the certificate's selected run/attempt, workflow, main ref and source commit. It verifies the bundle's source tree against the reviewed PR and its final formula-only commit. It then requires complete passing exact-head PR checks, accepted immutable upstream source and future tap-release immutability. The account needs the repository's administration-read permission for that immutability check; it is kept out of the CI token and no new secret is installed. Enable immutability only for future releases; existing tags and assets stay unchanged.

Every new bottle is uploaded to a draft and independently downloaded and hashed before publication. The finalizer rechecks the draft, publishes and confirms the immutable release, verifies public bottle downloads and the tag target, then pushes the verified commits with an ordinary fast-forward. Tampering, failed checks, changed public `main` or mismatched asset identities stop publication; retries verify existing immutable bytes without replacing them. A published bottle still requires fresh installed-runtime acceptance.

Then require:

```bash
python3 scripts/check-distribution.py --require-bottle
```

This additionally validates the matching binary release, bottle root URL, Apple Silicon platform pins and downloaded checksums. Scheduled, release and manual guard runs require this check. A missing current bottle remains a visible failure, not a substitute source-only pass.

## Uninstall

```bash
brew uninstall rightclick
```

Client registrations, pairing state and user logs are separate from the package. Remove only RIGHTCLICK-owned entries when intentionally disconnecting; uninstalling a formula is not permission to delete unrelated client configuration.

---

<div align="center">

**The capability graph changes. The AI-facing interface does not.**

[RIGHTCLICK source](https://github.com/rossbuckley1990-hash/rightclick) · [Report an installation issue](https://github.com/rossbuckley1990-hash/homebrew-tap/issues) · [Source release procedure](https://github.com/rossbuckley1990-hash/rightclick/blob/main/docs/RELEASE.md)

</div>
