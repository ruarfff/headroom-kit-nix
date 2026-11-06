{ pkgs }:
let
  filename = "headroom_kit-0.1.9-py3-none-any.whl";
  release = pkgs.fetchurl {
    url = "https://github.com/ruarfff/headroom-kit/releases/download/v0.1.9/${filename}";
    sha256 = "d061573e0640dcc789bbc872df76bcf88669fa09e87db0ca08c7b323730cfc71";
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
