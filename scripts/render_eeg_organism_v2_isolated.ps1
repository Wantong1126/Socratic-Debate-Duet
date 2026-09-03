param(
    [string]$SclangPath = "",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $projectRoot "recordings\eeg_organism_v2_isolated"
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
$fields = @("energy", "delta", "theta", "alpha", "beta")
$levels = @("low", "high")

try {
    foreach ($field in $fields) {
        foreach ($level in $levels) {
            $outputPath = Join-Path $OutputDirectory "$($field)_$($level).wav"
            $env:EEG_ORGANISM_V2_FIELD = $field
            $env:EEG_ORGANISM_V2_LEVEL = $level
            $env:EEG_ORGANISM_V2_OUTPUT = $outputPath
            Write-Host "Rendering v2 $field $level -> $outputPath"
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
    Remove-Item Env:EEG_ORGANISM_V2_FIELD -ErrorAction SilentlyContinue
    Remove-Item Env:EEG_ORGANISM_V2_LEVEL -ErrorAction SilentlyContinue
    Remove-Item Env:EEG_ORGANISM_V2_OUTPUT -ErrorAction SilentlyContinue
}

Write-Host "Rendered ten organism v2 isolated LOW/HIGH files."
