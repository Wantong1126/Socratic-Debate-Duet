param(
    [string]$SclangPath = "",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $projectRoot "recordings\eeg_organism_v2_beta_profiles"
}
if ([string]::IsNullOrWhiteSpace($SclangPath)) {
    $candidates = @(
        "D:\OpenBCI\supercollider\sclang.exe",
        "C:\Program Files\SuperCollider-3.14.1\sclang.exe",
        "C:\Program Files\SuperCollider\sclang.exe"
    )
    $SclangPath = $candidates |
        Where-Object { Test-Path -LiteralPath $_ } |
        Select-Object -First 1
}
if ([string]::IsNullOrWhiteSpace($SclangPath) -or
    -not (Test-Path -LiteralPath $SclangPath)) {
    throw "sclang was not found. Pass -SclangPath with the full path."
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$renderScript = Join-Path $projectRoot "sound\render_eeg_organism_v2_isolated.scd"
$profiles = @("original_24_36_48", "softened")
$levels = @("low", "high")
$archivePath = Join-Path $OutputDirectory "archive.sctxar"
if (Test-Path -LiteralPath $archivePath) {
    throw "Refusing to overwrite pre-existing temporary archive $archivePath."
}

try {
    $env:EEG_ORGANISM_V2_ARCHIVE_DIR = $OutputDirectory
    foreach ($profile in $profiles) {
        foreach ($level in $levels) {
            $outputPath = Join-Path $OutputDirectory "$($profile)_beta_$($level).wav"
            $env:EEG_ORGANISM_V2_BETA_PROFILE = $profile
            $env:EEG_ORGANISM_V2_FIELD = "beta"
            $env:EEG_ORGANISM_V2_LEVEL = $level
            $env:EEG_ORGANISM_V2_OUTPUT = $outputPath
            Write-Host "Rendering beta profile $profile $level -> $outputPath"
            & $SclangPath -D $renderScript
            if ($LASTEXITCODE -ne 0) {
                throw "SuperCollider render failed with exit code $LASTEXITCODE."
            }
            if (-not (Test-Path -LiteralPath $outputPath)) {
                throw "SuperCollider did not create $outputPath."
            }
        }
    }
}
finally {
    Remove-Item Env:EEG_ORGANISM_V2_ARCHIVE_DIR -ErrorAction SilentlyContinue
    Remove-Item Env:EEG_ORGANISM_V2_BETA_PROFILE -ErrorAction SilentlyContinue
    Remove-Item Env:EEG_ORGANISM_V2_FIELD -ErrorAction SilentlyContinue
    Remove-Item Env:EEG_ORGANISM_V2_LEVEL -ErrorAction SilentlyContinue
    Remove-Item Env:EEG_ORGANISM_V2_OUTPUT -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $archivePath) {
        Remove-Item -LiteralPath $archivePath -Force
    }
}

Write-Host "Rendered four matched organism v2 beta profile files."
