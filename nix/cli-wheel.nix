{ pkgs }:
let
  filename = "headroom_kit-0.1.1-py3-none-any.whl";
  release = pkgs.fetchurl {
    url = "https://github.com/ruarfff/headroom-kit/releases/download/v0.1.1/${filename}";
    sha256 = "6dd7b82d8945ff474c3c9484e127d570c7cdea98c357f64d334b59b7ac9b8e69";
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
