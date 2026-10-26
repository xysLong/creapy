# Building the creapy.io desktop app

Non-programmers get a **double-click application**, never a Python installation. One bundle per platform, built with
PyInstaller from this folder's spec.

| Platform | Build on | Result | Hand out as |
|---|---|---|---|
| macOS (Apple silicon) | any Apple-silicon Mac (this laptop) | `dist/creapy.io.app` | `creapy.io-<version>-macOS.zip` |
| macOS (Intel) | an Intel Mac, or GitHub Actions `macos-13` | `dist/creapy.io.app` | `creapy.io-<version>-macOS-intel.zip` |
| Windows 10/11 | a Windows machine (office PC) or GitHub Actions | `dist/creapy.io/creapy.io.exe` + folder | `creapy.io-<version>-Windows.zip` |

A bundle only runs on the platform it was built on. Expect 300–500 MB unpacked (Qt, matplotlib, scipy, sklearn).

## Build steps

```bash
# once, in a clean environment with the app's dependencies
pip install -e ".[gui]" pyinstaller

# macOS / Linux
bash packaging/build.sh            # -> dist/creapy.io.app, zipped next to it
# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

Both scripts end with the **self-test**: the built app starts offscreen, opens the example dataset and renders
every view (`creapy.io --selftest`). Do not hand out a bundle whose self-test did not print `SELFTEST OK`.

## Why the warnings users will see, and the fix

The bundles are **not code-signed** (no Apple Developer ID, no Windows certificate). Consequences, which the
install guide (`docs/INSTALL_APP.md`) explains with screenshots-in-words:

- **macOS:** first double-click says *"creapy.io cannot be opened because the developer cannot be verified"* or
  *"is damaged"*. Fix: right-click the app → **Open** → **Open** (once). If macOS still refuses (Sequoia and later
  for apps downloaded from the internet), the user runs in Terminal once:
  `xattr -dr com.apple.quarantine ~/Downloads/creapy.io.app`, or the zip is passed on via a USB stick /
  AirDrop, which does not set the quarantine flag.
- **Windows:** SmartScreen shows *"Windows protected your PC"*. Fix: **More info** → **Run anyway** (once).

Signing would remove both dialogs: an Apple Developer ID (99 €/year, then `codesign` + `notarytool`) and a
Windows code-signing certificate. Worth it for a 1.0 release, not before.

## GitHub Actions

`.github/workflows/build-apps.yml` builds all three bundles on every tag `v*` (and on manual dispatch) and attaches
them to a GitHub release. The repository is public, so Actions minutes are free. **Untested until the first tag**: run it once, download
the Windows zip, and self-test it on a Windows laptop before handing it out.

## Updating

Bump `version` in `pyproject.toml` and `creapy/__init__.py`, rebuild, re-run the self-test, replace the zip. The app
has no auto-update; users download the new zip and replace the old app.
