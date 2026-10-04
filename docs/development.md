# Development

This repository owns the Nix packages, Home Manager options, and the small uv
launcher. [Headroom Kit](https://github.com/ruarfff/headroom-kit) owns the CLI,
proxy lifecycle, authentication, routing, and client resources.

## Build and check

From the repository root:

```sh
nix build "path:$PWD#headroom-kit"
nix flake check "path:$PWD" --no-write-lock-file
nix flake check "path:$PWD" --no-build --all-systems --no-write-lock-file
nix develop "path:$PWD" --command pre-commit run anti-slop-python --all-files
./result/bin/headroom-kit --version
```

The version command installs the CLI environment on first use. It reports
Headroom Kit 0.1.2 and Headroom 0.39.1 without starting a proxy. Transitive
dependencies and native wheels are downloaded through uv, outside Nix's sandbox.
Nix verifies the CLI wheel during the package build.

Use a `path:` source while editing so Nix includes untracked files without staging
them. Keep the existing repository hook manager.

The flake checks:

- Build every wrapper and evaluate the Home Manager selection.
- Run the released wheel with a synthetic Headroom dependency from a local index.
- Check CLI version/help, config and environment precedence, wrapper arguments,
  working directory, exit codes, client resources, and the removed version option.
- Check that uv uses user indexes, ignores project indexes, and suppresses resolver
  diagnostics that could contain credentials.
- Check offline warm launches with no installer, concurrent first setup, failed
  and interrupted setup recovery, missing dependencies, and a removed uv cache.
- Run release-planner tests, Ruff, nixfmt, pre-commit config validation, and actionlint.

The local dependency fixture does not test real Headroom imports, native libraries,
proxy startup, or model routing. Use the upstream
[runtime checks](https://github.com/ruarfff/headroom-kit/blob/v0.1.2/docs/development.md)
for that coverage. Live provider requests need explicit authorization.

## Update the CLI

For local development, build the wheel in the upstream CLI checkout and pass its
path as `cliWheel` to `lib.mkHeadroomKit` or the Home Manager module. Keep its
original `headroom_kit-*.whl` filename. This tests the Nix launcher against the
unreleased CLI without editing `nix/cli-wheel.nix`. See
[development wheel configuration](configuration.md#development-cli-wheel).

`copilot-app-headroom` translates to `headroom-kit run copilot-app --`. The CLI
owns the isolated app profile and provider configuration. Nix tests cover command
translation, wheel selection, optional configuration fields, and the released
CLI's help without starting an app or proxy. Test profile isolation and model
routing in the upstream CLI before using a development wheel with the real app.

Change the release URL and SHA-256 in `nix/cli-wheel.nix`. Check the new release's
configuration keys, agent names, Python requirement, and Headroom dependency.
Update the package tests and migration documentation, then run the checks above.
The bootstrap in `libexec/launch.py` owns installation and local cache validation,
then translates the existing command names to the public CLI. It does not resolve
dependencies on a warm launch. Keep setup diagnostics free of index URLs and
credentials, and keep complete older generations available to existing proxies.

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
ignored. Nix flake tags and upstream CLI versions are separate.
