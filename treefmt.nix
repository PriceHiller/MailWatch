# treefmt.nix
{ pkgs, ... }:
{
  projectRootFile = "flake.nix";
  programs.black.enable = true;
  programs.ruff-format.enable = true;
  programs.taplo.enable = true;
}
