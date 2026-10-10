{
  description = "MailWatch: watch a mailbox and act on incoming messages";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    treefmt-nix.url = "github:numtide/treefmt-nix";
  };

  outputs =
    inputs@{
      self,
      nixpkgs,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
      ...
    }:
    let
      inherit (nixpkgs) lib;
      forAllSystems =
        let
          _forAllSystems = lib.genAttrs lib.systems.flakeExposed;
        in
        f:
        _forAllSystems (
          system:
          let
            pkgs = nixpkgs.legacyPackages.${system};
            lib = pkgs.lib;
            # arg = rec {
            #   system = system;
            # };
          in
          (f {
            inherit pkgs;
            inherit lib;
            inherit system;

          })
        );

      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

      pythonSets = forAllSystems (
        { pkgs, ... }:
        import ./ext/nix/python-set.nix {
          inherit
            pkgs
            lib
            pyproject-nix
            pyproject-build-systems
            workspace
            ;
        }
      );

      treefmtEval = forAllSystems ({ pkgs, ... }: inputs.treefmt-nix.lib.evalModule pkgs ./treefmt.nix);

      mkPackage =
        system:
        import ./ext/nix/package.nix {
          pythonSet = pythonSets.${system};
          deps = workspace.deps.default;
        };
    in
    {
      packages = forAllSystems (
        { system, ... }:
        let
          package = mkPackage system;
        in
        {
          default = package;
          mailwatch = package;
        }
      );

      apps = forAllSystems (
        { system, ... }:
        let
          package = mkPackage system;
        in
        {
          default = {
            type = "app";
            program = "${package}/bin/mailwatch";
          };
        }
      );

      devShells = forAllSystems (
        { system, pkgs, ... }: {
          default = import ./ext/nix/dev-shell.nix {
            inherit pkgs;
            pythonSet = pythonSets.${system}.overrideScope (
              workspace.mkEditablePyprojectOverlay { root = "$REPO_ROOT"; }
            );
            deps = workspace.deps.all;
          };
        }
      );

      nixosModules = {
        default = import ./ext/nix/module.nix { defaultPackage = self.packages; };
        mailwatch = self.nixosModules.default;
      };

      formatter = forAllSystems ({ system, ... }: treefmtEval.${system}.config.build.wrapper);

      checks = forAllSystems (
        { pkgs, system, ... }:
        let
          package = mkPackage system;
          tests = import ./ext/nix/tests/mailwatch.nix {
            inherit pkgs;
            mailwatchModule = self.nixosModules.default;
            mailwatchPackage = package;
          };
        in
        {
          mailwatch = package;
          formatting = treefmtEval.${system}.config.build.check self;
        }
        // lib.optionalAttrs (system == "x86_64-linux") {
          mailwatch-vm = pkgs.testers.runNixOSTest tests.settings;
          mailwatch-vm-environment-file = pkgs.testers.runNixOSTest tests.environmentFile;
        }
      );
    };
}
