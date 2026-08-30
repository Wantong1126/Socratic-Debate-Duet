param(
    [ValidateSet("synthetic-supercollider", "isolated-supercollider", "family-supercollider", "supercollider-live")]
    [string]$Mode = "synthetic-supercollider",

    [ValidateSet("energy", "centroid", "mobility", "all")]
    [string]$Descriptor = "all",

    [ValidateSet("F3", "F4", "C3", "C4", "P3", "P4", "all")]
    [string]$Channel = "all",

    [double]$ControlHz = 0,
    [string]$Config = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($Config)) {
    $Config = Join-Path $projectRoot "config\sonification.toml"
}

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pythonCommand = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }
$arguments = @(
    "-m", "src.eeg_control_demo",
    "--mode", $Mode,
    "--config", $Config,
    "--sweep-descriptor", $Descriptor,
    "--sweep-channel", $Channel
)
if ($ControlHz -gt 0) {
    $arguments += @("--control-hz", $ControlHz.ToString([Globalization.CultureInfo]::InvariantCulture))
}

Write-Host "SuperCollider must already show 'EEG ORGANISM PHASE 1B READY on UDP 57120'."
if ($Mode -eq "isolated-supercollider" -and ($Descriptor -eq "all" -or $Channel -eq "all")) {
    throw "isolated-supercollider requires -Descriptor energy|centroid|mobility and -Channel F3|F4|C3|C4|P3|P4"
}
Write-Host "Starting $Mode; press Ctrl+C to stop Python. The SC watchdog will then fade output."
Push-Location $projectRoot
try {
    & $pythonCommand @arguments
}
finally {
    Pop-Location
}
