param(
    [string]$SclangPath = "",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $projectRoot "recordings\eeg_organism_v2_voicing"
}
if ([string]::IsNullOrWhiteSpace($SclangPath)) {
    $SclangPath = @(
        "D:\OpenBCI\supercollider\sclang.exe",
        "C:\Program Files\SuperCollider-3.14.1\sclang.exe",
        "C:\Program Files\SuperCollider\sclang.exe"
    ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if ([string]::IsNullOrWhiteSpace($SclangPath) -or
    -not (Test-Path -LiteralPath $SclangPath)) {
    throw "sclang was not found. Pass -SclangPath with the full path."
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$renderScript = Join-Path $projectRoot "sound\render_eeg_organism_v2_voicing_transition.scd"
$outputPath = Join-Path $OutputDirectory "g_lydian_transition.wav"
$archivePath = Join-Path $OutputDirectory "archive.sctxar"
if (Test-Path -LiteralPath $archivePath) {
    throw "Refusing to overwrite pre-existing temporary archive $archivePath."
}
try {
    $env:EEG_ORGANISM_V2_OUTPUT = $outputPath
    $env:EEG_ORGANISM_V2_ARCHIVE_DIR = $OutputDirectory
    $renderLog = & $SclangPath -D $renderScript 2>&1
    $renderLog | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "SuperCollider render failed with exit code $LASTEXITCODE."
    }
    $renderText = $renderLog -join [Environment]::NewLine
    if ($renderText -match "ERROR:|FAILURE IN SERVER|exception in GraphDef_Recv") {
        throw "SuperCollider reported a synthesis/render error."
    }
    if (-not (Test-Path -LiteralPath $outputPath)) {
        throw "SuperCollider did not create $outputPath."
    }
}
finally {
    Remove-Item Env:EEG_ORGANISM_V2_OUTPUT -ErrorAction SilentlyContinue
    Remove-Item Env:EEG_ORGANISM_V2_ARCHIVE_DIR -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $archivePath) {
        Remove-Item -LiteralPath $archivePath -Force
    }
}
Write-Host "Rendered persistent voice-bank transition -> $outputPath"
