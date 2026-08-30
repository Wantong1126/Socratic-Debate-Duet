param(
    [string]$Config = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($Config)) {
    $Config = Join-Path $projectRoot "config\sonification.toml"
}

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pythonCommand = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }

Push-Location $projectRoot
try {
    & $pythonCommand -m src.eeg_control_demo --mode stop-supercollider --config $Config
}
finally {
    Pop-Location
}
