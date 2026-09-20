{
  pkgs,
  lib,
  pyproject-nix,
  pyproject-build-systems,
  workspace,
}:
(pkgs.callPackage pyproject-nix.build.packages {
  python = pkgs.python3;
}).overrideScope (
  lib.composeManyExtensions [
    pyproject-build-systems.overlays.wheel
    (workspace.mkPyprojectOverlay { sourcePreference = "wheel"; })
  ]
)