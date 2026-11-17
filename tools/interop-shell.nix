# Independent QR tools for the interoperability tests.
{ pkgs ? import <nixpkgs> { } }:
pkgs.mkShell {
  packages = [
    pkgs.zbar
    pkgs.librsvg
  ];
}
