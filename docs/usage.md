# Usage and troubleshooting

[Install Kit](../README.md#install-in-your-nix-configuration), or enter a shell
with all five commands:

```sh
nix shell github:ruarfff/headroom-kit-nix/v0.1.0#headroom-kit
```

Then choose your client below.

## Codex CLI

Sign in with `codex login`, then launch from your project:

```sh
codex-headroom
# or resume a session
codex-headroom resume --last
```

Kit keeps your sign-in, history, working directory, arguments, and terminal input.
Help and version requests skip Headroom startup. The wrapper supports Codex's
built-in OpenAI provider; use normal Codex for custom or local providers.
API-key routing remains [unverified](validation.md).

## Copilot CLI

1. Sign in with the normal `copilot` CLI, then exit it.
2. Authorize Headroom separately:

   ```sh
   headroom copilot-auth login
   ```

3. Choose a model available to your account:

   ```sh
   copilot-headroom --model <model-id>
   ```

An explicit model is required; automatic selection does not carry over to this
route. If a model fails, test it in normal Copilot and select a supported model.
Kit uses subscription authorization and the Responses API. Subscription routing
is experimental; custom enterprise domains and all model combinations are unverified.

## Copilot in VS Code

Complete [Headroom authorization](#copilot-cli), ensure the Copilot extension is
installed for your chosen channel, then run:

```sh
copilot-vscode-headroom .
# For Insiders:
HEADROOM_VSCODE_CHANNEL=insiders copilot-vscode-headroom .
```

Kit opens a separate profile after the proxy is ready. **Normal settings stay
unchanged and Settings Sync is off.** Sign in to GitHub in the new profile if
prompted, then use the editor's model picker.

| Default location | Stable | Insiders |
| --- | --- | --- |
| macOS user data | `~/Library/Application Support/Code Headroom` | `~/Library/Application Support/Code - Insiders Headroom` |
| Linux user data | `${XDG_CONFIG_HOME:-~/.config}/Code Headroom` | `${XDG_CONFIG_HOME:-~/.config}/Code - Insiders Headroom` |
| Existing extensions | `~/.vscode/extensions` | `~/.vscode-insiders/extensions` |

[Override these paths](configuration.md#options) only with a **dedicated Kit
profile**. Settings and `User` symlinks that escape it are rejected. Keep the paths
unchanged during startup; the checks cannot prevent concurrent symlink changes.
Kit cannot identify every custom normal profile, so choose a separate directory.

The launcher accepts one folder or file, not arbitrary editor flags. Remote
extension hosts, SSH, containers, and WSL are unverified. See
[Headroom's editor integration](https://docs.headroomlabs.ai/docs/vscode-copilot).

## Codex macOS app

Sign in through the app's normal workflow, use its built-in OpenAI provider,
then **quit the app** before running:

```sh
codex-app-headroom
```

An already-running app is refused. Keep the terminal open and close the app before
stopping the proxy. This route uses undocumented hooks and still needs live GUI
validation. A fresh Dock launch uses the app's normal settings.

## Proxy lifetime

The dashboard URL is printed in the terminal. Ports default to 8788 for Codex and
8787 for Copilot. To run Copilot CLI and the editor together:

```sh
HEADROOM_VSCODE_PORT=8789 copilot-vscode-headroom .
```

| Launch | What keeps its proxy running? |
| --- | --- |
| CLI with a new proxy | The CLI session; exit or interruption stops it |
| GUI with a new proxy | Its terminal; close the app before stopping the terminal |
| Codex reusing a proxy | The original owner; borrowed sessions do not stop it |

Only compatible Kit-owned Codex proxies can be shared. For app/CLI sharing, start
`codex-app-headroom` first. Copilot proxies are private to each launch. Kit does not
adopt foreign proxies or silently move occupied ports. Forced kills and power loss
can leave processes behind; inspect them before restarting.

## Troubleshooting

| Problem | Check |
| --- | --- |
| Agent not found | Run `command -v codex`, `copilot`, or `code`; set the [executable option](configuration.md#options) if needed |
| Runtime download fails | Check the version, uv index access, cache permissions, and CA certificates; use `UV_NATIVE_TLS=true` if needed |
| Proxy never becomes ready | Try `HEADROOM_VERSION=0.37.0` and a free port; increase `HEADROOM_STARTUP_TIMEOUT` for slow startup |
| Port occupied | Choose another port or stop the listener from its owner terminal; do not kill an unknown process |
| Copilot auth/model failure | Run `headroom copilot-auth status`; check your subscription and explicit model |
| Editor settings conflict | Repair JSONC or conflicting endpoint settings in the isolated profile, then restart its wrapper |

Readiness failures stop the launch; there is no direct-connection fallback.
Raw proxy and resolver diagnostics are suppressed because they can contain credentials.

## Migration and rollback

When replacing another proxy setup, back up affected settings and remove only its
endpoint overrides, including permanent shell exports. Preserve credentials and
other preferences. Stop old proxies from their owner terminals before launching Kit.

To stop using Kit, close wrapped clients and their owner terminals, then use normal
commands. Remove Kit from your package list and rebuild when ready. Keep or delete
the isolated profile separately; its settings still point at Headroom after exit.
To remove only the managed editor block:

```sh
headroom unwrap vscode --settings-file '/path/to/isolated/User/settings.json'
```

## Privacy and routing

Managed proxies bind to `127.0.0.1`. External beacons and message logging are off;
Kit creates no proxy log file. Authentication stays in memory or the client's
normal credential store, outside Nix and source control.

CLI-launched clients bypass forward proxies for loopback. Existing exclusions are
preserved; a wildcard bypass keeps all client traffic direct. Headroom retains the
caller's upstream proxy policy. Normal launches and the caller's environment are unchanged.

<details>
<summary>Routing and proxy policy details</summary>

- Codex receives per-process `model_provider="openai"` and a local
  `openai_base_url`. Kit groups all `-c` options before a literal `--` to preserve
  subcommand overrides in Codex 0.154.0. `CODEX_HOME` stays unchanged.
- The macOS app uses `open --env` with `CODEX_APP_SERVER_OPENAI_BASE_URL` and
  `CODEX_APP_SERVER_FORCE_CLI=1`. These hooks can change with app updates; shell
  proxy exclusions do not establish live GUI routing.
- Copilot receives subscription tokens, the local `/v1` endpoint, and `responses`
  wire API. Token exchange and refresh use HTTPS `*.githubcopilot.com` endpoints.
- CLI clients merge `NO_PROXY`/`no_proxy` and add `127.0.0.1`, `localhost`, and `::1`.
  A standalone `*` entry sets both spellings to `*` and removes uppercase/lowercase
  HTTP, HTTPS, and ALL proxy variables from the client copy only.
- Codex uses cache mode with lossless, stateless operation. Kompress/fallback,
  semantic cache, rate limiting, learning, wire debug, output shaping, effort
  routing, and verbosity autotuning are off. Copilot keeps standard compression
  and local dashboard stats, with stateless operation and no learning.
- `HEADROOM_TELEMETRY` controls local stats: off for Codex, on for Copilot.
  `DO_NOT_TRACK=1` is set. Arbitrary inherited `HEADROOM_*` tuning and upstream
  overrides are excluded. Direct `headroom` accepts upstream flags independently.
- Proxy reuse requires a live Kit owner, matching implementation policy, resolved
  exact version, readiness, and expected upstream. State is stored under
  `${XDG_STATE_HOME:-~/.local/state}/headroom-kit`.

See [Headroom proxy controls](https://docs.headroomlabs.ai/docs/proxy).

</details>

## Check routing and compression

Open the printed dashboard. A healthy proxy proves readiness, not routed traffic.
For live validation, compare request counters before and after an authorized model
request; a direct launch should not increment them. Measure compression separately
with a representative workload: token savings, failures, and answer correctness.
See [validation limits](validation.md).
