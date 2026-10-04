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
      forAllSystems = lib.genAttrs lib.systems.flakeExposed;

      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

      pythonSets = forAllSystems (
        system:
        import ./ext/nix/python-set.nix {
          pkgs = nixpkgs.legacyPackages.${system};
          inherit
            lib
            pyproject-nix
            pyproject-build-systems
            workspace
            ;
        }
      );

      mkPackage =
        system:
        import ./ext/nix/package.nix {
          pythonSet = pythonSets.${system};
          deps = workspace.deps.default;
        };
    in
    {
      packages = forAllSystems (
        system:
        let
          package = mkPackage system;
        in
        {
          default = package;
          mailwatch = package;
        }
      );

      apps = forAllSystems (
        system:
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

      devShells = forAllSystems (system: {
        default = import ./ext/nix/dev-shell.nix {
          pkgs = nixpkgs.legacyPackages.${system};
          pythonSet = pythonSets.${system}.overrideScope (
            workspace.mkEditablePyprojectOverlay { root = "$REPO_ROOT"; }
          );
          deps = workspace.deps.all;
        };
      });

      nixosModules = {
        default = import ./ext/nix/module.nix { defaultPackage = self.packages; };
        mailwatch = self.nixosModules.default;
      };

      checks = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          package = mkPackage system;
          tests = import ./ext/nix/tests/mailwatch.nix {
            inherit pkgs;
            mailwatchModule = self.nixosModules.default;
            mailwatchPackage = package;
          };
        in
        {
          mailwatch = package;
        }
        // lib.optionalAttrs (system == "x86_64-linux") {
          mailwatch-vm = pkgs.testers.runNixOSTest tests.settings;
          mailwatch-vm-environment-file = pkgs.testers.runNixOSTest tests.environmentFile;
        }
      );
    };
}
