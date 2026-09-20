{
  pkgs,
  pythonSet,
  deps,
}:
let
  virtualenv = pythonSet.mkVirtualEnv "mailwatch-dev-env" deps;
in
pkgs.mkShell {
  packages = [
    virtualenv
    pkgs.uv
  ];

  env = {
    UV_NO_SYNC = "1";
    UV_PYTHON = pythonSet.python.interpreter;
    UV_PYTHON_DOWNLOADS = "never";
  };

  shellHook = ''
    unset PYTHONPATH
    export REPO_ROOT=$(git rev-parse --show-toplevel)
  '';
}