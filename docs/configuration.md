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

All managed wrappers use Headroom's native **`coding`** profile. Kit applies the
selected release's complete profile before CLI parsing, without copying profile
values into Nix or the launchers. The coding profile protects file reads, compresses
new observations, and keeps already-forwarded prefixes stable.

```sh
HEADROOM_SAVINGS_PROFILE=coding codex-headroom
HEADROOM_SAVINGS_PROFILE=balanced pi-headroom
HEADROOM_SAVINGS_PROFILE=general opencode-headroom
```

`balanced`, `general`, and `agent-90` are explicit alternatives in 0.37.0. Their
names and behaviour belong to Headroom; advertised savings are not guarantees.

**OpenAI exception:** Headroom 0.37.0 has CCR retrieval gaps on Responses and direct
Chat Completions. Kit keeps the OpenAI pipeline lossless, including Copilot models
that use those protocols. Anthropic Messages uses the selected profile unchanged.
This exception also applies to aggressive profiles; `HEADROOM_LOSSLESS=0` does not
remove it. See the [reproducer and comparison](validation.md#native-compression-profiles).

Native compression settings pass through, including:

- `HEADROOM_SAVINGS_PROFILE`, `HEADROOM_SAVINGS_TARGET`, `HEADROOM_MODE`, and
  `HEADROOM_TARGET_RATIO`.
- `HEADROOM_LOSSLESS`, `HEADROOM_DISABLE_KOMPRESS`,
  `HEADROOM_DISABLE_KOMPRESS_FALLBACK`, and the other `HEADROOM_KOMPRESS_*`,
  `HEADROOM_DISABLE_KOMPRESS*`, and `HEADROOM_FORCE_KOMPRESS*` controls.
- Profile thresholds, read protection, tool search, deduplication, code-aware
  compression, and CCR controls. `libexec/kit_proxy.py` lists the allowed names.
- `HEADROOM_OUTPUT_SHAPER`, `HEADROOM_EFFORT_ROUTER`, and
  `HEADROOM_VERBOSITY_AUTOTUNE`. Kit no longer forces these off. The default coding
  profile disables effort routing and does not enable the other two.

Explicit native values take precedence over profile defaults. Routing,
credentials, process settings, privacy restrictions, semantic caching, and rate
limiting remain under the existing Kit policy. Disabling CCR or read protection
is an explicit user choice and can remove those safeguards.

### Downloads and restarts

Kit resolves `headroom-ai[proxy,code]`; the `code` extra supplies the Tree-sitter
AST dependencies. The proxy extra supplies Kompress's ONNX runtime and tokenizer.
Headroom can download `chopratejas/kompress-v2-base` from Hugging Face in the
background on first startup. Native model initialization is deferred until use;
a ready proxy does not prove that the model has finished downloading. Compression
can be reduced while the model is unavailable. Allow network access and space for
the model cache, or explicitly disable Kompress and its fallback.

Effective profile and compression settings are part of proxy compatibility,
including shared Copilot proxies. A different setting does not silently replace
or reuse an existing proxy. Stop it explicitly, then relaunch with the new values:

```sh
headroom-kit stop 8787
HEADROOM_SAVINGS_PROFILE=balanced copilot-headroom
```

Stopping interrupts attached clients. Pi, OpenCode, Copilot CLI, and VS Code must
use matching settings when they share the Copilot port. Unset overrides when you
want to return to profile defaults, then stop and relaunch again.

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

Use the appropriate port and wrapper for other clients. This restores the old
lossless/no-Kompress policy, not the old incomplete profile initialization. Native
coding defaults such as read protection still apply. Direct `headroom proxy`
commands remain unmanaged and do not receive Kit's OpenAI exception.

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
