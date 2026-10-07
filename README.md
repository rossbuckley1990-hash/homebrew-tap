# RIGHTCLICK Homebrew tap

**The capability graph changes. The AI-facing interface does not.**

RIGHTCLICK discovers supported capability contracts from local software and services, applies authority and safety checks, and invokes them through seven generic MCP operations. This tap distributes its published stable release; unreleased branches and untagged `main` changes are not shipped automatically.

## Install and connect

```bash
brew install rossbuckley1990-hash/tap/rightclick
rightclick version
rightclick setup
```

Apple Silicon, macOS 14+. Source builds require Swift 6.2+ from the free Apple Command Line Tools. Update Command Line Tools through Software Update when needed. No paid Apple Developer account is required.

For detected supported local clients, preview before applying:

```bash
rightclick setup --all --dry-run --json
rightclick setup --all --yes
```

An individual client can be selected with `--client cursor`, `--client claude` (Claude Code), or `--client codex`. For any other compatible MCP client, launch `rightclick mcp` over stdio. See the [upstream client setup guide](https://github.com/rossbuckley1990-hash/rightclick#give-the-same-capability-runtime-to-your-ai).

For the persistent ChatGPT bridge:

```bash
rightclick setup chatgpt --dry-run --json
rightclick setup chatgpt --yes
```

The formula includes RIGHTCLICK's pinned tunnel-client compatibility resource and its required licence/notice files. Ordinary local MCP use does not require pairing the ChatGPT bridge.

## Upgrade and check

```bash
brew update
brew upgrade rightclick
rightclick version
rightclick doctor
brew test rossbuckley1990-hash/tap/rightclick
```

For an existing ChatGPT bridge, also inspect `rightclick setup chatgpt --dry-run --json` and confirm the connected `context_runtime` reports the upgraded executable. A changed package or setup file alone does not prove a live connection. Do not delete pairing state merely to upgrade.

## Source release versus binary bottle

[Formula/rightclick.rb](Formula/rightclick.rb) is the installation pin. It names a versioned [upstream source release](https://github.com/rossbuckley1990-hash/rightclick/releases/latest) and its SHA256. Homebrew resolves the locked Swift dependency revisions and compiles that source inside its build sandbox when no matching bottle is configured.

A **bottle** is a separate precompiled Homebrew package. It is used only when a matching `bottle do` block and platform checksum have been published in the formula. A source tarball, green unit tests, or an older tap release does not establish that a current binary bottle exists. Check the formula and [tap releases](https://github.com/rossbuckley1990-hash/homebrew-tap/releases) rather than a duplicated version claim in this README.

## Runtime portability and the stable package

Homebrew is a distribution adapter for RIGHTCLICK, not a requirement of the capability runtime. The [upstream portable-runtime candidate](https://github.com/rossbuckley1990-hash/rightclick/pull/49) converges one engine and seven-operation MCP contract across macOS, Linux and Windows, with native discovery behind platform host boundaries. Its portability matrix and release gates remain candidate evidence until the implementation is reviewed, tested and merged.

This tap still pins the published macOS release by content checksum. GitHub currently reports v0.2.2 as non-immutable; a checksum pin does not change that release setting. Its Apple Silicon/macOS restriction and bundled Darwin tunnel-client match the published bytes. Removing those restrictions before updating the accepted source release would produce a broken Linux installation.

Before distributing a portable release, require upstream macOS, Linux and Windows integrated build/test and real-provider MCP acceptance on the exact release source. Publish and independently verify a new immutable source asset before moving this formula's URL/checksum. Preserve the reviewed bottle workflow and run the distribution guard against the installed package. Add Linux eligibility only when that pinned source and its formula build pass on Linux; platform-specific tunnel resources must be conditional. Windows uses the same upstream runtime source and separate installation packaging, without depending on this tap.

## Maintainer alignment gates

The source and resource pins come from upstream `packaging/tap/Formula/rightclick.rb` at the release tag. Preserve Homebrew style corrections and add bottle metadata only through the reviewed bottle workflow. Never force-move an upstream release tag or reuse old bottle checksums.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check-distribution.py
```

The read-only check compares the latest stable upstream release, formula source pin and upstream generated resource pins, downloads and hashes the source asset, and verifies `SHA256SUMS-source`. It does not install software or modify either repository.

Formula pull requests use the existing Apple Silicon `brew test-bot` build/test path. After its latest exact head and the distribution guard are green, use the existing **brew pr-pull** workflow with that pull request number and reviewed head SHA to publish its bottle and formula metadata. Do not merge a formula-only change and assume a bottle was published.

Then require:

```bash
python3 scripts/check-distribution.py --require-bottle
```

This additionally checks the matching tap release, bottle root URL, Apple Silicon platform pins and downloaded bottle checksums. Scheduled, release and manual guard runs require this full check; a missing current bottle remains a visible failure, not a false green. Publication itself remains an explicit reviewed action.

`brew uninstall rightclick` removes the package. Client registrations, pairing state and user logs are separate; remove only RIGHTCLICK-owned entries when intentionally disconnecting. See the [main repository](https://github.com/rossbuckley1990-hash/rightclick) for capability limits and security guidance. Provider acceptance is not independently verified success.
