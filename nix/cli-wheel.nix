{ pkgs }:
let
  filename = "headroom_kit-0.1.5-py3-none-any.whl";
  release = pkgs.fetchurl {
    url = "https://github.com/ruarfff/headroom-kit/releases/download/v0.1.5/${filename}";
    sha256 = "3a43f1f90916553029894b9568e086088f068410ab50a6b6dce2bb9549f3bcca";
  };
  # uv requires a wheel filename without the Nix store hash prefix.
  directory = pkgs.linkFarm "headroom-kit-wheel" [
    {
      name = filename;
      path = release;
    }
  ];
in
"${directory}/${filename}"
