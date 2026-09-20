# Development

## Run from a checkout

```sh
nix build "path:$PWD#headroom-kit"
./result/bin/codex-headroom
```

Other commands are under `./result/bin/`.

## Checks

From the repository root:

```sh
nix develop
nix flake check --no-write-lock-file
nix flake check --no-build --all-systems --no-write-lock-file
nix build .#headroom-kit --no-write-lock-file
pre-commit run anti-slop-python --all-files
```

`nix flake check` runs unit tests, Ruff, nixfmt, pre-commit config validation, and
actionlint. The anti-slop hook is separate because the first run downloads an
environment. Leave any existing hook manager in place.

Untracked files: use `"path:$PWD"` as the flake source, including
`nix develop "path:$PWD"`. New Python files need an explicit `--files` list:

```sh
pre-commit run anti-slop-python --files libexec/*.py tests/*.py .github/scripts/*.py
```

Faster loop inside the dev shell:

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

Downloads Headroom 0.37.0 and checks real proxy start/reuse/stop, routing args,
settings preservation, and Copilot token refresh against a local endpoint. Fake
credentials, no model requests, no GUI. `--cache-dir` reuses a download cache.
This is separate from Nix checks because native wheels have to work at runtime.
See [validation](validation.md).

Needs Pi and OpenCode v2; temporary homes, fake keys, local endpoints. The macOS
sandbox blocks the network. Proves routing, not authenticated models:

```sh
python tests/agent_routing_smoke.py
# Pi only; no OpenCode installation needed:
python tests/agent_routing_smoke.py --agent pi
```

Pi includes 18 Copilot cases: Claude, Gemini, and GPT with saved OAuth, a saved
API key, or no Pi login, under ordinary and wildcard proxy settings. Each request
must reach the Copilot endpoint with the requested model and a placeholder token,
not the cache proxy, conflicting endpoint, or forward proxy. Config and fake
credential files must remain unchanged. OpenAI/Anthropic cases run as before.

Needs Codex, Pi, and OpenCode. Real launchers against a managed fake proxy; each
pair sends a distinct prompt. OpenCode first-use setup runs first:

```sh
python tests/shared_agent_smoke.py
```

Live reuse against real providers with your existing sign-in. Needs the Codex,
Copilot, Pi, and OpenCode v2 CLIs. Does not launch VS Code or the Codex app:

```sh
python tests/qa_share.py
```

Uses this checkout's `libexec`, throwaway ports, and a short prompt per CLI. The
second launch must print `Reusing Headroom`. Copilot's second launch also changes
model, reasoning effort, and client env. Pi and OpenCode `github-copilot` cases run
after Copilot so they reuse that proxy. OpenCode Copilot is skipped if
`opencode models` has no `github-copilot/` entries. A failed agent is reported and the rest
continue. Quota after a shared proxy is not a Kit failure. The script stops its
ports on the way out.

## Live Copilot model routing

Build the checkout, then pass model IDs available to your signed-in Copilot account:

```sh
nix build "path:$PWD#headroom-kit"
python tests/copilot_models_smoke.py ./result gemini-3.8-flash gpt-5.4 claude-sonnet-5 auto
```

Requires Copilot CLI with `COPILOT_API_URL` support (tested with 1.0.87-0) and
Headroom's Copilot login. Each supplied model makes a real, billable request.
The check uses a temporary directory and port, disables built-in tools, injects
conflicting BYOK settings, and requires both an `ok` reply and a Headroom request
counter increase. Later launches must reuse the proxy. It stops the test proxy
on exit and does not print raw client diagnostics. A model rejection, timeout,
or quota error fails the check; none counts as routing success.

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

Tests use stand-ins and temporary homes. They need loopback, plus uv and curl from
the dev shell. The uv regression uses a cold cache and a local package index; curl
checks local direct/proxy routing. No real credentials or external endpoints.
Release tests write no tags.

## Releases

The [workflow](../.github/workflows/tag.yml) checks Linux and Apple Silicon macOS.
PRs run checks only. A successful push to `main` can publish; only the release job
has write permission.

First tag is `v0.1.0`; later tags bump the highest stable patch. A tag is created
when `flake.nix`, `flake.lock`, `libexec/`, or `nix/` changed since the last
reachable stable release. Docs, skills, license, tests, and CI do not cut a tag.

Each tag gets a GitHub Release with generated notes. Rerun the same commit to
finish a failed publish; skip if `main` has moved on. A manual minor/major tag
becomes the next patch base. Prereleases and malformed tags are ignored. Kit tags
do not change the Headroom runtime pin.
