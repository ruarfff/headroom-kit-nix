# Configuration

The [quick setup](../README.md#quick-start) uses the defaults below.
Environment variables override Nix options for one launch.

## Nix integration

Add the [README input](../README.md#install-in-your-nix-configuration). Pass `inputs`
through `specialArgs` (NixOS/nix-darwin), `extraSpecialArgs` (standalone Home Manager),
or `home-manager.extraSpecialArgs` (Home Manager as a system module).

| Setup | Package option |
| --- | --- |
| NixOS or nix-darwin | `environment.systemPackages` |
| Home Manager | `home.packages` or the Kit module |

### Home Manager

The module includes `headroom`, `headroom-kit`, and the Codex/Copilot CLI wrappers.
Change `wrappers` to select clients; `headroom` and the control command stay included.

```nix
{ inputs, ... }:
{
  imports = [ inputs.headroom-kit.homeManagerModules.default ];
  programs.headroom-kit = {
    enable = true;
    wrappers = [ "codex-headroom" "pi-headroom" "opencode-headroom" "copilot-vscode-headroom" ];
    vscode.port = 8789;
    # vscode.channel = "insiders"; # Stable is the default
  };
}
```

### Without the Kit module

Select individual packages, or `kit.headroom-kit` for all eight commands:

```nix
{ inputs, pkgs, ... }:
let
  kit = inputs.headroom-kit.lib.mkHeadroomKit {
    inherit pkgs;
    vscodePort = 8789;
  };
in {
  environment.systemPackages = [ kit.headroom kit.headroom-kit-control kit.codex-headroom kit.copilot-vscode-headroom ];
}
```

Use `home.packages` with the same list in Home Manager.

## Versions and package indexes

Headroom defaults to **0.37.0**:

```sh
HEADROOM_VERSION=0.37.0 codex-headroom
HEADROOM_VERSION=latest codex-headroom
```

Exact versions fail without fallback. `latest` refreshes, skips prereleases, and
prints the resolved version. Kit tags pin launcher code; `HEADROOM_VERSION` selects
the runtime. Neither locks every Python dependency.

uv uses Nix Python in an isolated environment, keeping user/system indexes and
auth. It ignores project `uv.toml`/`pyproject.toml`, does not download Python or
load dotenv, and honours explicit uv environment variables. Keep credentials out
of Nix and source control. See [uv configuration](https://docs.astral.sh/uv/concepts/configuration-files/).

## Options

Home Manager paths are under `programs.headroom-kit`. The last column is
`lib.mkHeadroomKit`.

| Environment variable | Default | Home Manager | Package argument |
| --- | --- | --- | --- |
| `HEADROOM_VERSION` | `0.37.0` | `version` | `version` |
| `HEADROOM_STARTUP_TIMEOUT` | 180 seconds | `startupTimeout` | `startupTimeout` |
| `HEADROOM_CODEX_EXECUTABLE` | `codex` | `codex.executable` | `codexExecutable` |
| `HEADROOM_CODEX_PORT` | 8788 | `codex.port` | `codexPort` |
| `HEADROOM_CODEX_APP_PATH` | Find installed Codex app | `codex.appPath` | `codexAppPath` |
| `HEADROOM_COPILOT_EXECUTABLE` | `copilot` | `copilot.executable` | `copilotExecutable` |
| `HEADROOM_COPILOT_PORT` | 8787 | `copilot.port` | `copilotPort` |
| `HEADROOM_PI_EXECUTABLE` | `pi` | `pi.executable` | `piExecutable` |
| `HEADROOM_PI_PORT` | 8790 | `pi.port` | `piPort` |
| `HEADROOM_OPENCODE_EXECUTABLE` | `opencode` | `opencode.executable` | `opencodeExecutable` |
| `HEADROOM_OPENCODE_PORT` | 8791 | `opencode.port` | `opencodePort` |
| `HEADROOM_VSCODE_CHANNEL` | `stable`; also `insiders` | `vscode.channel` | `vscodeChannel` |
| `HEADROOM_VSCODE_EXECUTABLE` | `code` or `code-insiders` | `vscode.executable` | `vscodeExecutable` |
| `HEADROOM_VSCODE_PORT` | 8787 | `vscode.port` | `vscodePort` |
| `HEADROOM_VSCODE_USER_DATA_DIR` | [Isolated profile](usage.md#copilot-in-vs-code) | `vscode.userDataDir` | `vscodeUserDataDir` |
| `HEADROOM_VSCODE_EXTENSIONS_DIR` | Existing channel extensions | `vscode.extensionsDir` | `vscodeExtensionsDir` |

Ports are 1–65535. Codex, Pi, and OpenCode each need a separate port. Copilot CLI
and the editor can share one with the same Headroom OAuth credential.
The startup timeout begins after runtime resolution.

Executables are names on `PATH` or single paths, not shell commands. Quote paths
with spaces; the app path must be a macOS `.app` bundle. Unset a Kit variable to
use its default. Empty values are errors.

## Compression profiles

Managed wrappers default to Headroom's **`coding`** profile: protected file reads,
compression of new observations, and stable forwarded prefixes. Kit applies the
complete native profile before CLI parsing; explicit environment values win.
Headroom 0.37.0 also provides `balanced`, `general`, and `agent-90`.

```sh
HEADROOM_SAVINGS_PROFILE=balanced pi-headroom
HEADROOM_COMPRESSORS=log,search codex-headroom
```

`HEADROOM_COMPRESSORS` restricts the built-in compressors. Unset it to enable all.

**OpenAI stays lossless** because of Headroom 0.37.0's CCR retrieval gaps, including
OpenAI-wire Copilot. Aggressive profiles and `HEADROOM_LOSSLESS=0` do not bypass
this exception. Anthropic uses the selected profile.
See [validation](validation.md#openai-retrieval-exception).

Overrides cover profiles, targets, compressor selection, lossless/Kompress,
thresholds, read protection, tool search, deduplication, code-aware compression,
and CCR. See the [allowlist](../libexec/kit_proxy.py).
`HEADROOM_OUTPUT_SHAPER`, `HEADROOM_EFFORT_ROUTER`, and `HEADROOM_VERBOSITY_AUTOTUNE`
also pass through; the default profile does not enable them.

Routing, auth, privacy, process settings, semantic caching, and rate limiting stay
managed. Disabling CCR or read protection removes those safeguards.

### Downloads and restarts

The runtime includes Tree-sitter and Kompress dependencies. Headroom may download
`chopratejas/kompress-v2-base` from Hugging Face on first startup. Proxy readiness
does not mean the model is ready; compression may be reduced until it is.
Allow cache space and network access, or disable Kompress and its fallback.

Profile and compressor settings must match for reuse, including shared Copilot.
To change them, stop the proxy and relaunch:

```sh
headroom-kit stop 8787
HEADROOM_SAVINGS_PROFILE=balanced copilot-headroom
```

Stopping interrupts attached clients. All clients sharing a port must use matching
settings. To restore defaults, unset overrides and stop/relaunch again.

### Conservative compression

To restore the previous conservative compression switches:

```sh
headroom-kit stop 8788
HEADROOM_SAVINGS_PROFILE=coding \
HEADROOM_MODE=cache \
HEADROOM_LOSSLESS=1 \
HEADROOM_DISABLE_KOMPRESS=1 \
HEADROOM_DISABLE_KOMPRESS_FALLBACK=1 \
HEADROOM_OUTPUT_SHAPER=off \
HEADROOM_EFFORT_ROUTER=off \
HEADROOM_VERBOSITY_AUTOTUNE=off \
codex-headroom
```

Use the matching port and wrapper for other clients. Native read protection still
applies. Direct `headroom proxy` commands are unmanaged, without Kit's exception.

## Local metrics and storage

Managed proxies enable persistence and local telemetry by default. These native
Headroom settings pass through without Nix options:

| Environment variable | Managed proxy default |
| --- | --- |
| `HEADROOM_STATELESS` | Unset; persistence enabled. Set `1` to opt out. |
| `HEADROOM_TELEMETRY` | `on`; set `off` to disable local telemetry. |
| `HEADROOM_WORKSPACE_DIR` | `~/.headroom` |
| `HEADROOM_SAVINGS_PATH` | `<workspace>/headroom-kit/<port>/proxy_savings.json` |
| `HEADROOM_SAVINGS_EVENTS_PATH` | `<workspace>/savings_events.jsonl` |

Empty or whitespace-only storage paths use the defaults. Kit expands `~` and
resolves relative paths from the launch directory before detaching the proxy.

**Give concurrent proxies separate `HEADROOM_SAVINGS_PATH` files.** Headroom
rewrites each counter file, so sharing one can lose data. The event ledger supports
concurrent writers; `headroom savings` reads its shared default path. For a custom
workspace or ledger, use the same environment when running the report.

Storage, telemetry, and stateless settings affect proxy compatibility. After a
change, run `headroom-kit stop <port>` and relaunch; Kit will not replace an
incompatible proxy. See [metrics and retention](usage.md#metrics-and-retention)
for report scope and upgrade limits.
