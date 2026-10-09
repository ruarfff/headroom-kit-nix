{ pkgs }:
let
  filename = "headroom_kit-0.1.6-py3-none-any.whl";
  release = pkgs.fetchurl {
    url = "https://github.com/ruarfff/headroom-kit/releases/download/v0.1.6/${filename}";
    sha256 = "35e87a5c08a49f3271073e2776528a4ca1010bd72226e48a2d3377d779af3fdc";
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
