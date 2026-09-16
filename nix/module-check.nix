{ pkgs }:
let
  evaluate =
    settings:
    (pkgs.lib.evalModules {
      specialArgs = { inherit pkgs; };
      modules = [
        ./home-manager.nix
        {
          options.home.packages = pkgs.lib.mkOption {
            type = pkgs.lib.types.listOf pkgs.lib.types.package;
            default = [ ];
          };
        }
        { programs.headroom-kit = settings; }
      ];
    }).config.home.packages;
  enabled = evaluate {
    enable = true;
    version = "latest";
    wrappers = [
      "codex-headroom"
      "copilot-vscode-headroom"
      "pi-headroom"
      "opencode-headroom"
      "codex-headroom"
    ];
    codex.port = 18788;
    pi.port = 18790;
    opencode.port = 18791;
    vscode = {
      channel = "stable";
      port = 18787;
      executable = "/custom editor/code";
    };
  };
in
assert evaluate { enable = false; } == [ ];
assert
  builtins.map (p: p.name) enabled == [
    "headroom"
    "headroom-kit"
    "codex-headroom"
    "copilot-vscode-headroom"
    "pi-headroom"
    "opencode-headroom"
  ];
pkgs.symlinkJoin {
  name = "headroom-kit-module-check";
  paths = enabled;
}
