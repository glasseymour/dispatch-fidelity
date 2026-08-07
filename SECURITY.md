# Security

## Reporting

Open a private security advisory:
https://github.com/glasseymour/dispatch-fidelity/security/advisories/new

For anything that is not a vulnerability — including a way to make the scorer miss a real
fabrication or flag a faithful agent — open a normal issue. Those are the contributions
this project wants most, and they belong in the open where they become matrix rows.

## The threat model, stated plainly

This tool measures whether an agent's claims about tool calls match an out-of-band
execution log. Its guarantees stop in specific places, and knowing where matters more
than a promise that it is secure.

**Signer and runner are the same party.** If you instrument your own system and publish
your own artifacts, provenance is complete against accidental mixing and after-the-fact
modification, and **absent** against an actor fabricating at run time. The nonce
commitment proves a manifest and a log came from one execution; it does not prove the
execution was honest about itself. Resolving that needs an external countersignatory or a
transparency log.

**The proxy is in-process.** Anything with write access to the log file, the manifest, or
the process memory holding the plaintext nonce can defeat the measurement. The instrument
assumes an agent that may report untruthfully, not an operator who tampers with the
evidence. Treat `audit_runs/` as evidence: restrict writes, and prefer a recorder the
measured system cannot reach.

**There is a crash window.** The proxy logs after the tool returns, so a hard kill between
a tool's side effect and its log line leaves an executed call unrecorded. Known,
not yet closed; a pre-execution `CALL_STARTED` record is the fix and is planned.

**Not a correctness or safety audit.** A faithful agent can be perfectly wrong, and this
tool will call that run clean. Reasoning quality, output correctness, prompt injection and
data exfiltration are different measurements with different ground truth.

## What the tool executes

`dispatch-audit verify` runs the shell commands listed in your `ANCHOR.txt`, by design —
an anchor is a command whose output is the claim. Treat `ANCHOR.txt` as executable
content: review it as you would a script, and do not run `verify` in a checkout you do not
trust. `gate` runs whatever command you pass it. Nothing else in the package executes
user-supplied content.

The MCP stdio adapter spawns the server command you give it and relays bytes between it
and its client. It parses JSON-RPC to find `tools/call` and never modifies the stream.

## Dependencies

None at runtime. `pytest` for development only. This is deliberate: an audit instrument
that drags in a dependency tree is a bigger attack surface than the thing it measures.

## Releases

**v0.3.0, the current release.** Built locally, verified from the built wheel in a clean
environment, and published with SHA-256 checksums in the release notes. The tag is
annotated and **unsigned**. There is no build attestation and no SBOM. This is stated in
the past tense because it is what happened.

**From v0.3.1.** `.github/workflows/publish.yml` builds once from the tag, verifies the
wheel from itself, produces a CycloneDX SBOM of a runtime-only environment, attaches
Sigstore build-provenance and SBOM attestations, then creates the release and publishes to
PyPI from the same artifact. Tags will be signed. PyPI uses Trusted Publishing, so no
long-lived token exists in this repository.

**That workflow has never run.** It is a plan in version control, not a property of any
artifact you can download today. Do not treat provenance described there as covering
v0.3.0.

## Supported versions

The latest release. This project is young; there is no back-porting policy yet, and
claiming one would be a promise nobody has tested.
