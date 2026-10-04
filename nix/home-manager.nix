{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.programs.headroom-kit;
  inherit (lib) mkOption types;
  optionalString =
    description:
    mkOption {
      type = types.nullOr types.str;
      default = null;
      inherit description;
    };
  port =
    default:
    mkOption {
      type = types.port;
      inherit default;
    };
  packages = import ./packages.nix {
    inherit pkgs;
    inherit (cfg) version cliWheel startupTimeout;
    codexExecutable = cfg.codex.executable;
    codexPort = cfg.codex.port;
    codexAppPath = cfg.codex.appPath;
    copilotExecutable = cfg.copilot.executable;
    copilotPort = cfg.copilot.port;
    copilotAppPath = cfg.copilot.appPath;
    copilotAppDataDir = cfg.copilot.appDataDir;
    piExecutable = cfg.pi.executable;
    piPort = cfg.pi.port;
    opencodeExecutable = cfg.opencode.executable;
    opencodePort = cfg.opencode.port;
    vscodeChannel = cfg.vscode.channel;
    vscodeExecutable = cfg.vscode.executable;
    vscodePort = cfg.vscode.port;
    vscodeUserDataDir = cfg.vscode.userDataDir;
    vscodeExtensionsDir = cfg.vscode.extensionsDir;
  };
in
{
  options.programs.headroom-kit = {
    enable = lib.mkEnableOption "Headroom Kit launchers (no agent or service installation)";
    wrappers = mkOption {
      type = types.listOf (
        types.enum [
          "codex-headroom"
          "codex-app-headroom"
          "copilot-headroom"
          "copilot-app-headroom"
          "pi-headroom"
          "opencode-headroom"
          "copilot-vscode-headroom"
        ]
      );
      default = [
        "codex-headroom"
        "copilot-headroom"
      ];
      description = "Wrappers to install. The headroom and headroom-kit commands are always included.";
    };
    version = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Removed: delete this option and HEADROOM_VERSION. The CLI release pins Headroom.";
    };
    cliWheel = mkOption {
      type = types.nullOr types.path;
      default = null;
      description = "Development CLI wheel file with its original headroom_kit-*.whl filename; null uses the pinned release.";
    };
    startupTimeout = mkOption {
      type = types.ints.positive;
      default = 180;
    };
    codex = {
      executable = mkOption {
        type = types.str;
        default = "codex";
      };
      port = port 8788;
      appPath = optionalString "Installed macOS app path; null uses bundle ID com.openai.codex.";
    };
    copilot = {
      executable = mkOption {
        type = types.str;
        default = "copilot";
      };
      port = port 8787;
      appPath = optionalString "Installed GitHub Copilot macOS app path; null uses the CLI default.";
      appDataDir = optionalString "Dedicated Headroom Copilot app profile, never the normal app profile; null uses the CLI default.";
    };
    pi = {
      executable = mkOption {
        type = types.str;
        default = "pi";
      };
      port = port 8790;
    };
    opencode = {
      executable = mkOption {
        type = types.str;
        default = "opencode";
      };
      port = port 8791;
    };
    vscode = {
      channel = mkOption {
        type = types.enum [
          "stable"
          "insiders"
        ];
        default = "stable";
      };
      executable = optionalString "Editor executable; null selects code or code-insiders.";
      port = port 8787;
      userDataDir = optionalString "Dedicated Headroom editor data directory, never normal editor data.";
      extensionsDir = optionalString "Existing extension directory; null uses the channel default.";
    };
  };
  config = lib.mkIf cfg.enable {
    home.packages = [
      packages.headroom
      packages.headroom-kit-control
    ]
    ++ map (name: packages.${name}) (lib.unique cfg.wrappers);
  };
}
