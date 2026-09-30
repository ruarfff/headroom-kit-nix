# Headroom Kit

[![Checks and releases](https://github.com/ruarfff/headroom-kit-nix/actions/workflows/tag.yml/badge.svg?branch=main)](https://github.com/ruarfff/headroom-kit-nix/actions/workflows/tag.yml)
[![Nix flake](https://img.shields.io/badge/Nix-flake-5277C3?logo=nixos&logoColor=white)](https://nixos.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Run your existing coding agents through a local
[Headroom](https://github.com/headroomlabs-ai/headroom) proxy using Nix.
This flake uses the released [Headroom Kit CLI v0.1.1](https://github.com/ruarfff/headroom-kit/releases/tag/v0.1.1).
Normal launches keep their settings. Kit does not install agents or system services.

```mermaid
flowchart LR
    Agent[Wrapped agent] --> Headroom[Headroom on localhost] --> Provider[Model provider]
```

## Quick start

You need **Nix with flakes** and an installed, configured coding agent.
The flake targets Apple Silicon macOS and Linux. See [validation limits](docs/validation.md).

```sh
nix run github:ruarfff/headroom-kit-nix#codex-headroom
```

Nix fetches and verifies the CLI wheel. The first launch installs it and Headroom
0.39.1 into an installed environment using your package-index settings. Later
launches use that environment directly, without uv resolution or index access.
[Version and index policy](docs/configuration.md#versions-and-package-indexes).
For Copilot, [authorize Headroom](docs/usage.md#copilot-cli) first.

## Install in your Nix configuration

Add the input and keep its generated lock entry:

```nix
inputs.headroom-kit.url = "github:ruarfff/headroom-kit-nix";
```

In a Home Manager module that receives `inputs`:

```nix
{ inputs, ... }:
{
  imports = [ inputs.headroom-kit.homeManagerModules.default ];
  programs.headroom-kit.enable = true;
}
```

That installs `headroom`, `headroom-kit`, `codex-headroom`, and `copilot-headroom`.
[Configuration](docs/configuration.md#nix-integration) covers Pi, OpenCode, GUI wrappers,
and NixOS/nix-darwin without Home Manager.

## Choose a command

| Command | Setup |
| --- | --- |
| `codex-headroom` | Existing Codex sign-in |
| `copilot-headroom [--model <model-id>]` | [Headroom Copilot login](docs/usage.md#copilot-cli); supports native selection and `auto` |
| `pi-headroom --provider <provider> --model <model-id>` | [Pi setup](docs/usage.md#pi) |
| `opencode-headroom` | [OpenCode v2 setup](docs/usage.md#opencode-v2) |
| `copilot-vscode-headroom .` | [Copilot setup](docs/usage.md#copilot-in-vs-code); isolated VS Code profile |
| `codex-app-headroom` | Quit the app first; [experimental routing](docs/usage.md#codex-macos-app) |
| `headroom` | Headroom CLI |
| `headroom-kit` | Released CLI: `run`, `copilot-auth`, `status`, `stop`, and `--version` |

Shared proxies stay up after clients exit. **Stopping one interrupts every client
on its port.** See [proxy lifetime](docs/usage.md#proxy-lifetime) and
[migration to the released CLI](docs/usage.md#migration-and-rollback).

## Set up with an agent

Give your agent the [Nix setup skill](skills/install-headroom-kit/SKILL.md).

## Reference

| Read | For |
| --- | --- |
| [Configuration](docs/configuration.md) | Nix examples, ports, versions, and package indexes |
| [Usage](docs/usage.md) | Authentication, editor isolation, privacy, and fixes |
| [Development](docs/development.md) | Checks, runtime smoke test, and releases |
| [Validation](docs/validation.md) | Tested platforms and known limits |

[MIT](LICENSE). See [NOTICE](NOTICE.md) for dependency licenses and attribution.
