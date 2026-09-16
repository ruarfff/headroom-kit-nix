{
  description = "Community-maintained Headroom launchers for existing coding agents";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "aarch64-darwin"
        "aarch64-linux"
        "x86_64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      lib.mkHeadroomKit = import ./nix/packages.nix;
      packages = forAllSystems (
        system: self.lib.mkHeadroomKit { pkgs = nixpkgs.legacyPackages.${system}; }
      );
      homeManagerModules.default = import ./nix/home-manager.nix;
      formatter = forAllSystems (system: nixpkgs.legacyPackages.${system}.nixfmt);
      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = pkgs.mkShell {
            packages = with pkgs; [
              python313
              nodejs
              uv
              curl
              ruff
              nixfmt
              pre-commit
              actionlint
              shellcheck
            ];
          };
        }
      );
      checks = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          packages = self.packages.${system}.headroom-kit;
          home-manager-module = import ./nix/module-check.nix { inherit pkgs; };
          tests =
            pkgs.runCommand "headroom-kit-tests"
              {
                nativeBuildInputs = [
                  pkgs.python313
                  pkgs.nodejs
                  pkgs.uv
                  pkgs.curl
                  pkgs.ruff
                  pkgs.nixfmt
                  pkgs.pre-commit
                  pkgs.actionlint
                  pkgs.shellcheck
                ];
              }
              ''
                cp -r ${./libexec} libexec
                cp -r ${./tests} tests
                cp -r ${./.github} .github
                cp ${./.pre-commit-config.yaml} .pre-commit-config.yaml
                cp ${./pyproject.toml} pyproject.toml
                cp ${./flake.nix} flake.nix
                cp -r ${./nix} nix
                export HOME="$TMPDIR/home"
                mkdir -p "$HOME"
                python -m unittest discover -s tests -v
                node --test tests/test_client_adapters.mjs
                ruff check libexec tests .github/scripts
                ruff format --check libexec tests .github/scripts
                nixfmt --check flake.nix nix/*.nix
                pre-commit validate-config
                actionlint .github/workflows/*.yml
                touch "$out"
              '';
        }
      );
    };
}
