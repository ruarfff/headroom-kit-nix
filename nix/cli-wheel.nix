{ pkgs }:
let
  filename = "headroom_kit-0.1.2-py3-none-any.whl";
  release = pkgs.fetchurl {
    url = "https://github.com/ruarfff/headroom-kit/releases/download/v0.1.2/${filename}";
    sha256 = "970fc44fb2c40d84dabe14efda4c9738595428c97fd9a25e5af5df1fb92d3605";
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
