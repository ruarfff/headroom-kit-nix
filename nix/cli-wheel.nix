{ pkgs }:
let
  filename = "headroom_kit-0.1.7-py3-none-any.whl";
  release = pkgs.fetchurl {
    url = "https://github.com/ruarfff/headroom-kit/releases/download/v0.1.7/${filename}";
    sha256 = "5786bce80d9e05f60a555235f8b8f2e3712de8ab62ac3c006eb065d1f2fa109a";
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
