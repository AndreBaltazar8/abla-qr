# Independent QR tools for the interoperability tests.
{ pkgs ? import <nixpkgs> { } }:
pkgs.mkShell {
  packages = [
    pkgs.zbar
    pkgs.qrencode
    pkgs.librsvg
    (pkgs.python3.withPackages (p: [ p.segno p.qrcode p.pillow p.numpy p.zxing-cpp ]))
  ];
}
