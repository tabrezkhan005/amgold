# Build a release APK with production API_BASE_URL (HTTPS).
# Usage:
#   .\scripts\build_release_apk.ps1 -ApiBaseUrl "https://your-service.up.railway.app"
param(
    [Parameter(Mandatory = $true)]
    [string]$ApiBaseUrl
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ApiBaseUrl)) {
    Write-Error "ApiBaseUrl is required (e.g. https://your-service.up.railway.app)"
}

if ($ApiBaseUrl -notmatch '^https://') {
    Write-Error "ApiBaseUrl must be HTTPS (got: $ApiBaseUrl)"
}

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Building AmGold release APK"
Write-Host "API_BASE_URL=$ApiBaseUrl"

flutter pub get
flutter build apk --release --dart-define=API_BASE_URL=$ApiBaseUrl

$apk = Join-Path $root "build\app\outputs\flutter-apk\app-release.apk"
if (Test-Path $apk) {
    Write-Host ""
    Write-Host "APK ready:"
    Write-Host $apk
} else {
    Write-Error "Build finished but APK not found at $apk"
}
