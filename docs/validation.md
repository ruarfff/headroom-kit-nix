# Validation and limitations

A successful Nix build does not prove runtime or authenticated client support.

## Platforms

| System | Nix evaluation | Runtime |
| --- | --- | --- |
| `aarch64-darwin` | Pass | Headroom 0.37.0 proxy and writer smoke pass |
| `aarch64-linux` | Pass | Unverified |
| `x86_64-linux` | Pass | Unverified |

The Codex app wrapper requires macOS. No other platform outputs are declared.

## Checked

On `aarch64-darwin`, all 48 tests, native Nix checks, formatting/lint, anti-slop,
and the aggregate build pass. Coverage includes versions, uv index policy,
arguments, environment isolation, proxy lifecycle, editor guards, and release tags.

The runtime smoke passes with a real Headroom 0.37.0 proxy and stand-in client.
Two writer tests cover ordinary profiles, escaping symlinks, and changes during
startup. Local Codex 0.154.0 tests confirmed ordinary and wildcard proxy routing
using fake endpoints; they do not establish authenticated model responses.
See [development](development.md) for commands.

## Still unverified

- Linux runtime, fresh Codex app routing, and isolated editor chat. The app uses
  undocumented hooks; remote editor hosts also need validation.
- Codex API-key routing, custom Copilot enterprise domains, and all model combinations.
- Compression quality and savings on representative workloads.
- Remote CI, tag/release permissions, and generated release notes until the workflow runs.

Exact Headroom versions do not lock every Python dependency or optional download.
Editor path guards cannot prevent concurrent symlink changes. Keep isolated paths
unchanged during startup, and build your consumer configuration before activation.
