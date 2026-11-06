{ pkgs }:
let
  filename = "headroom_kit-0.1.8-py3-none-any.whl";
  release = pkgs.fetchurl {
    url = "https://github.com/ruarfff/headroom-kit/releases/download/v0.1.8/${filename}";
    sha256 = "e2b1b50da6036f7572d41305447c8842da6f0bdc734e0e57c4631559127e9a78";
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
