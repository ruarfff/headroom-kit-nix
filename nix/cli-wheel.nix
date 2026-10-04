{ pkgs }:
let
  filename = "headroom_kit-0.1.3-py3-none-any.whl";
  release = pkgs.fetchurl {
    url = "https://github.com/ruarfff/headroom-kit/releases/download/v0.1.3/${filename}";
    sha256 = "4c55f6c0f27105227476028f9e11d9c92a69b021a4ff9f34242f410964755708";
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
