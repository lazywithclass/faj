{ pkgs ? import <nixpkgs> {} }:

pkgs.python312Packages.buildPythonApplication {
  pname = "faj";
  version = "1.0";
  src = ./.;

  pyproject = true;
  nativeBuildInputs = with pkgs.python312Packages; [ setuptools wheel uv ];
  propagatedBuildInputs = with pkgs.python312Packages; [
    pandas pyarrow pyqt6 shiv
  ];

  # optional if tests would hit network
  doCheck = false;
}
