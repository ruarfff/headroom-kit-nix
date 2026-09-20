# Development

## Run from a checkout

```sh
nix build "path:$PWD#headroom-kit"
./result/bin/codex-headroom
```

Prefix other Kit commands with `./result/bin/` to use this build.

## Checks

Run from the repository root:

```sh
nix develop
nix flake check --no-write-lock-file
nix flake check --no-build --all-systems --no-write-lock-file
nix build .#headroom-kit --no-write-lock-file
pre-commit run anti-slop-python --all-files
```

The native flake check runs the unit suite, Ruff, Nix formatting, pre-commit config
validation, and workflow lint. The pinned anti-slop hook runs separately because
its first run downloads an environment. Keep any existing hook manager in place.

For a checkout with untracked files, use `"path:$PWD"` instead of `.` as the flake
source, including `nix develop "path:$PWD"`. Include new Python files explicitly:

```sh
pre-commit run anti-slop-python --files libexec/*.py tests/*.py .github/scripts/*.py
```

For faster feedback inside the development shell:

```sh
python -m unittest discover -s tests -v
node --test tests/test_client_adapters.mjs
ruff check libexec tests .github/scripts
ruff format --check libexec tests .github/scripts
nixfmt --check flake.nix nix/*.nix
```

## Runtime smoke test

After building the aggregate package:

```sh
python tests/runtime_smoke.py "$(readlink result)"
```

This downloads Headroom 0.37.0 and checks real proxy readiness, routing arguments,
output, settings preservation, shared lifetime, explicit stop, and the real JSONC
writer. It also checks Copilot account pinning and refresh against a local token endpoint. It uses temporary
state and a stand-in client, with fake credentials, no model requests, and no GUI
launches. Add `--cache-dir /path/to/test-cache` to reuse a dedicated download cache.

The smoke test is separate from Nix checks: downloaded native wheels must also
work at runtime. See [validation status](validation.md).

With Pi and OpenCode v2 installed, check their real HTTP clients on macOS:

```sh
python tests/agent_routing_smoke.py
```

This uses temporary homes, fake API keys, and local endpoints. A macOS sandbox
blocks external connections. It checks both providers, conflicting endpoint
settings, ordinary/wildcard forward proxies, and configuration preservation.
Local error responses establish routing, not authenticated model support.

With Codex, Pi, and OpenCode installed, check shared concurrent client traffic:

```sh
python tests/shared_agent_smoke.py
```

This uses the real launchers and a managed fake proxy with instance IDs and request
counters. Each pair of real clients sends a distinct prompt. The macOS sandbox
blocks external connections; responses are local test errors. OpenCode's isolated
first-use setup runs before the concurrent pair. No authenticated model support
or compression quality is established.

To check live reuse with real providers, install the Codex, Copilot, Pi, and
OpenCode v2 CLIs first. Missing tools fail before any proxy starts. This check
does not launch VS Code or the Codex app.

```sh
python tests/qa_share.py
```

The script uses this checkout's `libexec`, throwaway ports, and a short prompt per
CLI. The second launch must print `Reusing Headroom`. Copilot's second launch also
changes model, reasoning effort, and client env. A failed agent is reported and the
rest still run. Provider quota after a shared proxy is not a Kit failure.
This talks to real providers and uses your existing sign-in.
Interruptions can leave a proxy; the script stops its ports on the way out.

## Code and test boundaries

```text
libexec/
├── launch.py        isolated entry point
├── kit_runtime.py   version resolution and foreground processes
├── kit_proxy.py     shared owner, status/stop, compatibility, and auth
├── kit_session.py   client routing and editor isolation
├── pi-extension.mjs temporary Pi endpoint overrides
└── opencode-plugin/ OpenCode v2 request routing
```

Tests use explicit stand-ins and temporary homes. They need loopback access plus
uv and curl from the development shell. The uv regression
uses a cold cache and local package index; curl checks local direct/proxy routing.
No real credentials or external endpoints are used. Release tests write no tags.

## Releases

The [workflow](../.github/workflows/tag.yml) checks Linux and Apple Silicon macOS.
Only a successful push to `main` can publish a release; pull requests run checks
only. The release job alone has write permission.

The first tag is `v0.1.0`; later tags increment the highest stable tag's patch.
Releases follow changes to `flake.nix`, `flake.lock`, `libexec/`, `nix/`, `skills/`,
`LICENSE`, or `NOTICE.md`. The comparison uses the last reachable stable release,
so changes from a failed push remain eligible. Documentation, test, or CI-only
changes do not create a new tag after the first release.

Each tag gets a GitHub Release with generated notes. Rerunning the same commit
reuses its stable tag and can finish a failed release publication. Existing
releases are left alone; runs skip publication if `main` has advanced.

An authorized manual minor/major tag becomes the base for later patch tags.
Prereleases and malformed tags are ignored. Kit tags do not change the Headroom
runtime pin. Before enabling releases, verify Actions and permissions to push
`v*` tags and create releases. The workflow installs or activates no profiles.
