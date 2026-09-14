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
    inherit (cfg) version startupTimeout;
    codexExecutable = cfg.codex.executable;
    codexPort = cfg.codex.port;
    codexAppPath = cfg.codex.appPath;
    copilotExecutable = cfg.copilot.executable;
    copilotPort = cfg.copilot.port;
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
          "copilot-vscode-headroom"
        ]
      );
      default = [
        "codex-headroom"
        "copilot-headroom"
      ];
      description = "Wrappers to install. The headroom command is always included.";
    };
    version = mkOption {
      type = types.str;
      default = "0.37.0";
      description = "Exact stable release or latest; HEADROOM_VERSION takes precedence.";
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
    home.packages = [ packages.headroom ] ++ map (name: packages.${name}) (lib.unique cfg.wrappers);
  };
}
