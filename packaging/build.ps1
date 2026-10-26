# Build the Windows bundle and self-test it. Run from the repository root in PowerShell:
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$version = python -c "import creapy; print(creapy.__version__)"
Write-Host "Building creapy.io $version with $(python --version)"
if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
pyinstaller --noconfirm --clean packaging\creapy_io.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Write-Host "Self-test ..."
$env:QT_QPA_PLATFORM = "offscreen"
& "dist\creapy.io\creapy.io.exe" --selftest
if ($LASTEXITCODE -ne 0) { throw "Self-test failed" }
Remove-Item Env:QT_QPA_PLATFORM

$zip = "dist\creapy.io-$version-Windows.zip"
Compress-Archive -Path "dist\creapy.io" -DestinationPath $zip -Force
Write-Host "Done: $zip"
