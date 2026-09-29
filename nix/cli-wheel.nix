{ pkgs }:
let
  filename = "headroom_kit-0.1.0-py3-none-any.whl";
  release = pkgs.fetchurl {
    url = "https://github.com/ruarfff/headroom-kit/releases/download/v0.1.0/${filename}";
    sha256 = "788549cde9bf833393a80ab7ef1c995b44daeb4beb6d454eea96e8e2b4c4c235";
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
