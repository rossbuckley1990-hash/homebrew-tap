# RCIR and seven-operation installed-product acceptance

This additive change does not change `Formula/rightclick.rb`, its v0.2.2 source URL/checksum, supported platform, tunnel resource or release tags. The candidate was reconciled onto tap commit `6dda63a486f5bfbaf1c9ec2246992b6493668984`, formula blob `0f20d401c5e3ed085a863c57ca43e474767447bb`. This preserves the concurrently published arm64 Tahoe bottle block as well as the source pins. Bottle download/fresh-install acceptance is separate from the read-only probe below.

The companion probe tests the real launched `rightclick mcp` process rather than assuming that a successful version command proves its agent-facing interface. With Python 3.11+:

```bash
python3 scripts/verify-seven-operations.py \
  --binary /opt/homebrew/bin/rightclick \
  --expected-version 0.2.2
```

Use the candidate's actual immutable formula version when validating a later release. This command performs no installation, token/configuration changes, or provider invocation. Normal RIGHTCLICK process startup may log and discover providers.

The probe requires exactly the seven RIGHTCLICK operations, twice, with canonical full-declaration schema fingerprints; rejects extra/duplicate/missing tools and unexpected pagination; compares the reported process ID, resolved binary path, executable SHA-256 and version with the launched process; and performs a literal, read-only context inspection. JSON responses, frame count/size and runtime are bounded. Duplicate JSON keys, malformed IDs and errors fail closed. Child cleanup is bounded. Arbitrary server output or credentials are not printed on failure.

It tests the legacy initialize/stdio compatibility path, not modern self-contained discovery. A matching hash is a consistency check, not independent proof that a malicious executable is trustworthy. It does not test actual task execution, provider credentials, RCIR integration, all eleven substrates or a fresh install.

The original 17 unit tests (unchanged) plus four schema controls use explicitly named fake MCP processes. They validate the probe and its rejection paths, not the installed Mac product. Run them with:

```bash
python3 -m unittest discover -s tests -p 'test_seven_operations*.py' -v
```

The added workflow runs those fixture tests with read-only repository permissions. It does not publish, install or update the formula. Existing distribution checks and publish/test workflows remain untouched.

Before advancing a release pin, require full candidate native CI, real CryptoKit checks, live RCIR dispatch/verification acceptance, a fresh install and this probe against its exact executable. Retain the project's existing immutable-release and bottle-alignment checks. Do not claim Windows/Linux product support just because the RCIR semantic source passes on Linux.
