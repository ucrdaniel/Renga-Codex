# Security policy

This local MCP server can read BIM projects and mutate files inside its approved
write directory. It is a desktop integration, not a sandbox for hostile code or
a network-facing service. Only register a source checkout and Python environment
you trust. No independent AI API key is required by the bridge.

The supported baseline is the latest published bridge release with the Windows,
Python, Renga and SDK versions named in its tested-capabilities report. Older or
unverified combinations are not covered by a support promise.

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/ucrdaniel/Renga-Codex/security/advisories/new)
when the repository enables it. If it is unavailable, open a minimal public
issue requesting a private contact without exploit details or private data.
There is currently no dedicated security email or guaranteed response time.

Include affected versions, a synthetic reproduction, expected boundary and
actual behavior. Never attach project/customer data, credentials, Codex
configuration, activation files, SDK binaries or unsanitized logs.

## Boundaries and operational precautions

- MCP mutation tools are limited to their configured write root. Do not point
  that root at a folder containing production BIM files.
- Existing-file edits need a verified backup; new-file operations refuse to
  overwrite files. A backup is useful only if its hash matches the source.
- The adapter owns a separate Renga process and uses serialized COM work.
  Concurrent editors outside this bridge are beyond its file-lock guarantee.
- Save-close-reopen checks verify selected identities and values. They do not
  constitute a complete architectural or regulatory review.
- A timeout or crash leaves an uncertain result. Inspect the audit log, saved
  project and backup before retrying. Do not delete an active lock or kill an
  unrelated Renga process to force progress.
- Installation backs up Codex configuration before registration. These local
  backups may contain secrets; keep `runtime/` private and never upload it.
- Public CI must not execute real COM scenarios or use project files supplied
  by an untrusted pull request.

The implementation's exact tested safeguards and remaining limits are recorded
in `docs/CAPABILITIES.md`; absence of a feature is not evidence of protection.
