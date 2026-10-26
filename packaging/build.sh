#!/usr/bin/env bash
# Build the macOS (or Linux) bundle and self-test it. Run from the repository root:  bash packaging/build.sh
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=$(python -c "import creapy; print(creapy.__version__)")
echo "Building creapy.io $VERSION with $(python --version) on $(uname -s) $(uname -m)"
rm -rf build dist
pyinstaller --noconfirm --clean packaging/creapy_io.spec

if [[ "$(uname -s)" == "Darwin" ]]; then
  APP="dist/creapy.io.app"
  echo "Self-test ..."
  QT_QPA_PLATFORM=offscreen "$APP/Contents/MacOS/creapy.io" --selftest
  ARCH=$(uname -m); [[ "$ARCH" == "arm64" ]] && TAG="macOS" || TAG="macOS-intel"
  ZIP="dist/creapy.io-$VERSION-$TAG.zip"
  (cd dist && ditto -c -k --sequesterRsrc --keepParent "creapy.io.app" "creapy.io-$VERSION-$TAG.zip")
  echo "Done: $ZIP ($(du -sh "$ZIP" | cut -f1))"
else
  echo "Self-test ..."
  QT_QPA_PLATFORM=offscreen "dist/creapy.io/creapy.io" --selftest
  (cd dist && zip -qr "creapy.io-$VERSION-Linux.zip" creapy.io)
  echo "Done: dist/creapy.io-$VERSION-Linux.zip"
fi
