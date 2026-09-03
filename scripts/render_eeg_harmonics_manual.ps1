param(
    [string]$SclangPath = "",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $projectRoot "recordings\eeg_harmonics_manual"
}

if ([string]::IsNullOrWhiteSpace($SclangPath)) {
    $command = Get-Command "sclang" -ErrorAction SilentlyContinue
    if ($command) {
        $SclangPath = $command.Source
    }
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
$renderScript = Join-Path $projectRoot "sound\render_eeg_harmonics_manual.scd"
$tests = [ordered]@{
    master_energy  = "01_master_energy_loudness_only.wav"
    redistribution = "02_warm_to_bright_constant_loudness.wav"
    group1         = "03_group_1_foundation.wav"
    group2         = "04_group_2_body.wav"
    group3         = "05_group_3_presence.wav"
    group4         = "06_group_4_air.wav"
}

try {
    foreach ($test in $tests.GetEnumerator()) {
        $outputPath = Join-Path $OutputDirectory $test.Value
        $env:EEG_HARMONICS_TEST = $test.Key
        $env:EEG_HARMONICS_OUTPUT = $outputPath
        Write-Host "Rendering $($test.Key) -> $outputPath"
        & $SclangPath -D $renderScript
        if ($LASTEXITCODE -ne 0) {
            throw "SuperCollider render failed for $($test.Key) with exit code $LASTEXITCODE."
        }
        if (-not (Test-Path -LiteralPath $outputPath)) {
            throw "SuperCollider reported success but did not create $outputPath."
        }
    }
}
finally {
    Remove-Item Env:EEG_HARMONICS_TEST -ErrorAction SilentlyContinue
    Remove-Item Env:EEG_HARMONICS_OUTPUT -ErrorAction SilentlyContinue
}

Write-Host "Rendered all six disconnected manual-audition recordings."
