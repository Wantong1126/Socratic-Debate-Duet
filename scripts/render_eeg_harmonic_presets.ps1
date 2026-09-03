param(
    [string]$SclangPath = "",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $projectRoot "recordings\eeg_harmonic_presets"
}

if ([string]::IsNullOrWhiteSpace($SclangPath)) {
    $command = Get-Command "sclang" -ErrorAction SilentlyContinue
    if ($command) { $SclangPath = $command.Source }
}
if ([string]::IsNullOrWhiteSpace($SclangPath)) {
    $candidates = @(
        "D:\OpenBCI\supercollider\sclang.exe",
        "C:\Program Files\SuperCollider-3.14.1\sclang.exe",
        "C:\Program Files\SuperCollider-3.14.0\sclang.exe",
        "C:\Program Files\SuperCollider-3.13.0\sclang.exe",
        "C:\Program Files\SuperCollider\sclang.exe"
    )
    $SclangPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if ([string]::IsNullOrWhiteSpace($SclangPath) -or -not (Test-Path -LiteralPath $SclangPath)) {
    throw "sclang was not found. Pass -SclangPath with the full path to sclang.exe."
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$renderScript = Join-Path $projectRoot "sound\render_eeg_harmonic_presets.scd"
$presets = [ordered]@{
    warm_organic = "01_warm_organic.wav"
    air_glass = "02_air_glass.wav"
    dark_mineral = "03_dark_mineral.wav"
}

try {
    foreach ($item in $presets.GetEnumerator()) {
        $outputPath = Join-Path $OutputDirectory $item.Value
        $env:EEG_HARMONIC_PRESET = $item.Key
        $env:EEG_HARMONIC_PRESET_OUTPUT = $outputPath
        Write-Host "Rendering preset $($item.Key) -> $outputPath"
        & $SclangPath -D $renderScript
        if ($LASTEXITCODE -ne 0) {
            throw "SuperCollider render failed for $($item.Key) with exit code $LASTEXITCODE."
        }
        if (-not (Test-Path -LiteralPath $outputPath)) {
            throw "SuperCollider did not create $outputPath."
        }
    }
}
finally {
    Remove-Item Env:EEG_HARMONIC_PRESET -ErrorAction SilentlyContinue
    Remove-Item Env:EEG_HARMONIC_PRESET_OUTPUT -ErrorAction SilentlyContinue
}

Write-Host "Rendered all three comparable harmonic preset auditions."
