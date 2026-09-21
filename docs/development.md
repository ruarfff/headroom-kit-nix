# Development

## Run from a checkout

```sh
nix build "path:$PWD#headroom-kit"
./result/bin/codex-headroom
```

All wrappers are under `./result/bin/`.

## Checks

From the repository root:

```sh
nix develop
nix flake check --no-write-lock-file
nix flake check --no-build --all-systems --no-write-lock-file
pre-commit run anti-slop-python --all-files
```

The flake runs unit tests, Ruff, nixfmt, pre-commit config validation, and actionlint.
Anti-slop runs separately and downloads its environment on first use. Leave the
existing hook manager in place.

Use `"path:$PWD"` as the flake source to include untracked files, including with
`nix develop`. For new Python files, pass an explicit list:

```sh
pre-commit run anti-slop-python --files libexec/*.py tests/*.py .github/scripts/*.py
```

For a faster loop inside the dev shell:

```sh
python -m unittest discover -s tests -v
node --test tests/test_client_adapters.mjs
ruff check libexec tests .github/scripts
ruff format --check libexec tests .github/scripts
nixfmt --check flake.nix nix/*.nix
```

## Runtime smoke test

After building the package:

```sh
python tests/runtime_smoke.py "$(readlink result)"
```

Downloads Headroom 0.37.0 and checks proxy startup/reuse/stop, routing arguments,
settings preservation, local token refresh, custom-CA TLS negotiation, and metrics
persistence. The TLS check uses OpenSSL from the dev shell to create a temporary
local certificate. It uses fake
credentials and temporary storage: no model calls or GUI. `--cache-dir` reuses a
download cache. This runs outside Nix checks because native wheels need runtime
validation.

### Copilot TLS compatibility

Headroom 0.37.0 gives urllib a context that advertises HTTP/2, but urllib sends
HTTP/1.1. Kit replaces only `build_urlopen_context` in memory, using Headroom's
existing trust builder with HTTP/1.1 ALPN. The httpx builder, CA settings,
certificate checks, and urllib proxy policy stay unchanged. This applies to
subscription discovery, managed token refresh, and the Kit `headroom` launcher;
the installed package cache is not edited.

During subscription discovery, Kit records transport and service failures before
Headroom turns them into a missing resolution. Error text and response bodies
are not passed to upstream logging. A later successful candidate still wins.
HTTP 401/403 retain the subscription/login diagnostic; connection failures and
other HTTP failures get separate network/service guidance.

Run the credential-free regression on its own inside `nix develop`:

```sh
uvx --isolated --no-env-file --from 'headroom-ai[proxy]==0.37.0' python -I tests/smoke_tls.py
```

It reproduces the h2 disconnect against local HTTPS, then checks HTTP/1.1,
replacement and additive CA roots, hostname verification, proxy policy, and
redacted auth diagnostics. Keep this adapter until a fixed Headroom release
passes these checks without it, including managed refresh.

### Local client routing

Requires macOS and the selected clients. Temporary homes, fake credentials, and a
loopback-only sandbox prevent external model calls:

```sh
python tests/agent_routing_smoke.py
python tests/agent_routing_smoke.py --agent pi
python tests/agent_routing_smoke.py --agent opencode
```

The checks require the requested model and placeholder token at the Copilot
endpoint, no model traffic at conflicting endpoints, and unchanged config and
credentials. OpenAI/Anthropic routing is also covered.

OpenCode uses active fake credentials in its real database; fresh v2 databases
do not import `auth.json`. Its offline Claude fixture supplies the native Messages
package normally selected by account catalog discovery. Discovery itself uses a
local rejecting endpoint. See [results and coverage](validation.md#real-clients).

### Shared clients

Requires Codex, Pi, OpenCode, and macOS. Two clients send distinct prompts through
one managed fake proxy. OpenCode's first-use setup runs before concurrent launches:

```sh
python tests/shared_agent_smoke.py
```

### Live reuse

Uses existing sign-ins and real provider calls, which can incur charges. Requires
Codex, Copilot, Pi, and OpenCode v2; no GUI clients:

```sh
python tests/qa_share.py
```

Uses this checkout's `libexec` and temporary ports, then stops them on exit. Second
launches must print `Reusing Headroom`; Copilot also changes model, reasoning
level, and client environment. Pi/OpenCode Copilot cases reuse that proxy.
OpenCode Copilot is skipped if `opencode models` lists no `github-copilot/` entries.

This checks reuse, not successful model routing: quota errors after reuse do not
fail it. Other failures are reported while the remaining clients continue.

## Live Copilot model routing

Requires Headroom's Copilot login and a Copilot CLI with `COPILOT_API_URL` support
(tested with **1.0.87-0**). Each model makes a real, billable request:

```sh
nix build "path:$PWD#headroom-kit"
python tests/copilot_models_smoke.py ./result gemini-3.8-flash gpt-5.4 claude-sonnet-5 auto
```

Use IDs available to your account. The check disables built-in tools, injects
conflicting BYOK settings, and requires an `ok` reply, increased Headroom request
count, and proxy reuse. Rejections, timeouts, and quota errors fail the check.
It stops the temporary proxy on exit and does not print raw client diagnostics.

## Code and test boundaries

```text
libexec/
├── launch.py        isolated entry point
├── kit_runtime.py   version resolution and foreground processes
├── kit_proxy.py     shared owner, status/stop, and compatibility
├── kit_copilot.py   subscription auth, refresh policy, and urllib TLS
├── kit_session.py   client routing and editor isolation
├── pi-extension.mjs temporary Pi endpoint overrides
└── opencode-plugin/ OpenCode v2 request routing
```

Unit tests use stand-ins and temporary homes. They need loopback, uv, and curl
from the dev shell, but no real credentials or external endpoints. The uv check
uses a cold cache and local package index. Release tests write no tags.

## Releases

The [workflow](../.github/workflows/tag.yml) checks Linux and Apple Silicon macOS.
PRs run checks only. Successful pushes to `main` can publish; only the release job
has write permission.

The first tag is `v0.1.0`. Later tags bump the highest stable patch when `flake.nix`,
`flake.lock`, `libexec/`, or `nix/` changed since the last reachable stable release.
Docs, skills, tests, license, and CI changes do not cut a tag.

Each tag gets a GitHub Release with generated notes. Rerun the same commit to
finish a failed publish; publishing skips it if `main` has moved on. Manual
minor/major tags become the next patch base. Prereleases and malformed tags are
ignored. Kit tags do not change the Headroom runtime pin.
