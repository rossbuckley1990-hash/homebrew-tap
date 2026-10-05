# RIGHTCLICK Homebrew tap

[![tests](https://github.com/rossbuckley1990-hash/homebrew-tap/actions/workflows/tests.yml/badge.svg)](https://github.com/rossbuckley1990-hash/homebrew-tap/actions/workflows/tests.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Upstream](https://img.shields.io/github/v/release/rossbuckley1990-hash/rightclick?label=rightclick)](https://github.com/rossbuckley1990-hash/rightclick/releases/tag/v0.1.0)

## Install an app. Your AI learns what it can do.

```bash
brew install rossbuckley1990-hash/tap/rightclick
rightclick setup
```

Apple Silicon · macOS 14+ · bottle when available · source builds need Swift 6.2+ from free Apple Command Line Tools.

After install, Homebrew prints caveats for the Cursor MCP path. Enable RIGHTCLICK in Cursor, then ask what your Mac can do with a piece of text.

### What the formula guarantees

- Pins the immutable v0.1.0 source asset by SHA256
- Resolves only locked dependency revisions
- Builds inside Homebrew's sandbox (SwiftPM resolve permitted in fetch)
- `brew test` checks `version` and exact text classification
- Bottle publish uses reviewed `brew pr-pull` with build provenance attestation

### Uninstall

```bash
brew uninstall rightclick
```

Removes the package. Cursor MCP config and user logs/token remain; delete only RIGHTCLICK's entries if you want them gone.

### Links

- Product + evidence: [rossbuckley1990-hash/rightclick](https://github.com/rossbuckley1990-hash/rightclick)
- BBEdit proof: [docs/BBEDIT-PROOF.md](https://github.com/rossbuckley1990-hash/rightclick/blob/main/docs/BBEDIT-PROOF.md)
- Security: [SECURITY.md](https://github.com/rossbuckley1990-hash/rightclick/blob/main/SECURITY.md)
