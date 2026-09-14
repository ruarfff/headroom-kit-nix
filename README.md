# Headroom Kit

[![Checks and releases](https://github.com/ruarfff/headroom-kit-nix/actions/workflows/tag.yml/badge.svg?branch=main)](https://github.com/ruarfff/headroom-kit-nix/actions/workflows/tag.yml)
[![Nix flake](https://img.shields.io/badge/Nix-flake-5277C3?logo=nixos&logoColor=white)](https://nixos.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Run your existing coding agents through a local
[Headroom](https://github.com/headroomlabs-ai/headroom) proxy using Nix.
Normal launches keep their settings. Kit installs no agents or background services.

```mermaid
flowchart LR
    Agent[Wrapped agent] --> Headroom[Headroom on localhost] --> Provider[Model provider]
```

## Quick start

You need **Nix with flakes** and an installed, signed-in coding agent.
Runtime checks cover Apple Silicon macOS; [Linux runtime is unverified](docs/validation.md).

Run the `v0.1.0` release:

```sh
nix run github:ruarfff/headroom-kit-nix/v0.1.0#codex-headroom
```

The first launch downloads Headroom 0.37.0 using your uv package-index settings.
See [versions and indexes](docs/configuration.md#versions-and-package-indexes) to
change them. Keep the terminal open while using Kit. For Copilot, follow the
[authorization steps](docs/usage.md#copilot-cli).

## Install in your Nix configuration

Pin the release in your flake:

```nix
inputs.headroom-kit.url = "github:ruarfff/headroom-kit-nix/v0.1.0";
```

In a Home Manager module that receives `inputs`:

```nix
{ inputs, ... }:
{
  imports = [ inputs.headroom-kit.homeManagerModules.default ];
  programs.headroom-kit.enable = true;
}
```

Build and activate through your usual workflow. This installs `headroom` and both
CLI wrappers. See [configuration](docs/configuration.md#nix-integration) to add
GUI wrappers, use NixOS/nix-darwin without Home Manager, or pass module arguments.

## Choose a command

After installation, run these from your project:

| Command | Setup |
| --- | --- |
| `codex-headroom` | Use your existing Codex sign-in |
| `copilot-headroom --model <model-id>` | [Authorize Headroom for Copilot](docs/usage.md#copilot-cli) first |
| `copilot-vscode-headroom .` | [Authorize Copilot](docs/usage.md#copilot-in-vs-code); opens an isolated VS Code Stable profile |
| `codex-app-headroom` | Quit the macOS Codex app first; [experimental routing](docs/usage.md#codex-macos-app) |
| `headroom` | Run the Headroom CLI directly |

CLI exit stops its owned proxy. Close wrapped GUI apps before stopping their
terminal. See [usage](docs/usage.md) for Insiders, shared proxies, and troubleshooting.

## Set up with an agent

Give your agent the [v0.1.0 setup skill](https://github.com/ruarfff/headroom-kit-nix/blob/v0.1.0/skills/install-headroom-kit/SKILL.md).

## Reference

| Read | For |
| --- | --- |
| [Configuration](docs/configuration.md) | Nix examples, ports, versions, and package indexes |
| [Usage](docs/usage.md) | Authentication, editor isolation, privacy, and fixes |
| [Development](docs/development.md) | Checks, runtime smoke test, and releases |
| [Validation](docs/validation.md) | Tested platforms and known limits |

[MIT](LICENSE). See [NOTICE](NOTICE.md) for dependency licenses and attribution.
