{
  pkgs,
  version ? "0.37.0",
  startupTimeout ? 180,
  codexExecutable ? "codex",
  codexPort ? 8788,
  codexAppPath ? null,
  copilotExecutable ? "copilot",
  copilotPort ? 8787,
  piExecutable ? "pi",
  piPort ? 8790,
  opencodeExecutable ? "opencode",
  opencodePort ? 8791,
  vscodeChannel ? "stable",
  vscodeExecutable ? null,
  vscodePort ? 8787,
  vscodeUserDataDir ? null,
  vscodeExtensionsDir ? null,
}:
let
  inherit (pkgs) lib;
  validPort = port: builtins.isInt port && port >= 1 && port <= 65535;
  defaults = pkgs.writeText "headroom-kit-defaults.json" (
    builtins.toJSON {
      inherit
        version
        startupTimeout
        codexExecutable
        codexPort
        codexAppPath
        copilotExecutable
        copilotPort
        piExecutable
        piPort
        opencodeExecutable
        opencodePort
        vscodeChannel
        vscodeExecutable
        vscodePort
        vscodeUserDataDir
        vscodeExtensionsDir
        ;
      python = "${pkgs.python313}/bin/python3.13";
      uv = "${pkgs.uv}/bin/uvx";
    }
  );
  runtime = pkgs.runCommand "headroom-kit-runtime" { } ''
    mkdir -p "$out/libexec"
    cp ${../libexec}/*.py ${../libexec}/*.mjs "$out/libexec/"
    cp -r ${../libexec}/opencode-plugin "$out/libexec/"
  '';
  commands = [
    "headroom"
    "headroom-kit"
    "codex-headroom"
    "codex-app-headroom"
    "copilot-headroom"
    "pi-headroom"
    "opencode-headroom"
    "copilot-vscode-headroom"
  ];
  packages = lib.genAttrs commands (
    name:
    (pkgs.writeShellScriptBin name ''
      exec ${pkgs.python313}/bin/python3.13 -I ${runtime}/libexec/launch.py ${defaults} ${name} "$@"
    '').overrideAttrs
      (old: {
        meta = (old.meta or { }) // {
          license = lib.licenses.mit;
          description = "Launch ${name} with the selected Headroom runtime";
          homepage = "https://github.com/ruarfff/headroom-kit-nix";
          mainProgram = name;
        };
      })
  );
  aggregate = pkgs.symlinkJoin {
    name = "headroom-kit";
    paths = builtins.attrValues packages;
    meta.description = "Headroom and launch-only routing for existing coding agents";
    meta.license = lib.licenses.mit;
    meta.homepage = "https://github.com/ruarfff/headroom-kit-nix";
    meta.mainProgram = "headroom-kit";
  };
in
assert lib.assertMsg (
  version == "latest" || builtins.match "[0-9]+\\.[0-9]+\\.[0-9]+" version != null
) "Headroom version must be an exact stable X.Y.Z release or latest";
assert lib.assertMsg (builtins.all validPort [
  codexPort
  copilotPort
  vscodePort
  piPort
  opencodePort
]) "Invalid Headroom port";
assert lib.assertMsg (
  codexPort != copilotPort && codexPort != vscodePort
) "Codex and Copilot require separate ports";
assert lib.assertMsg (
  piPort != opencodePort
  && builtins.all (port: port != piPort && port != opencodePort) [
    codexPort
    copilotPort
    vscodePort
  ]
) "Pi and OpenCode require separate ports from other wrappers";
assert lib.assertMsg (builtins.elem vscodeChannel [
  "stable"
  "insiders"
]) "Invalid VS Code channel";
assert lib.assertMsg (
  builtins.isInt startupTimeout && startupTimeout > 0
) "Invalid startup timeout";
packages
// {
  headroom-kit-control = packages.headroom-kit;
  headroom-kit = aggregate;
  default = aggregate;
}
