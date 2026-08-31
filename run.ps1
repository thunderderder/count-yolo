# count_yolo launcher
# Looks for Python in this order:
#   1. COUNT_YOLO_PYTHON
#   2. project .venv
#   3. python on PATH
#
# Examples:
#   .\run.ps1 annotate --image output\frame_ref.jpg
#   .\run.ps1 8m --mode line --line L1_南直行 --device 0
#   .\run.ps1 ebike --mode line --line L1_南直行 --device 0 --max-seconds 120
#   .\run.ps1 compare --counts examples\counts_L1_south_through_yolov8m.json --level L1

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

function Import-DotEnv([string]$Path) {
    if (-not (Test-Path $Path)) { return }
    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
        if (-not [string]::IsNullOrWhiteSpace($key) -and -not (Test-Path "Env:$key")) {
            Set-Item -Path "Env:$key" -Value $val
        }
    }
}

Import-DotEnv (Join-Path $Root ".env")

function Resolve-ProjectPython {
    if ($env:COUNT_YOLO_PYTHON -and (Test-Path $env:COUNT_YOLO_PYTHON)) {
        return $env:COUNT_YOLO_PYTHON
    }
    $venvPy = Join-Path $Root ".venv\Scripts\python.exe"
    if (Test-Path $venvPy) {
        return $venvPy
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    Write-Host "Python not found. Create .venv or set COUNT_YOLO_PYTHON." -ForegroundColor Red
    exit 1
}

$Python = Resolve-ProjectPython
$Model8m = Join-Path $Root "models\yolov8m.pt"
$ModelEbike = if ($env:COUNT_YOLO_EBIKE_MODEL) {
    $env:COUNT_YOLO_EBIKE_MODEL
} else {
    Join-Path $Root "models\electri_bike_and_vehicle.pt"
}

function Get-PresetInfo([string]$Name) {
    switch ($Name) {
        "8m" {
            return @{
                Model = $Model8m
                Tag = "8m"
                Label = "yolov8m (COCO)"
            }
        }
        "ebike" {
            return @{
                Model = $ModelEbike
                Tag = "ebike"
                Label = "ebike custom weights"
            }
        }
        default { return $null }
    }
}

function Expand-ModelPreset([string]$Preset, [string[]]$ArgsList) {
    $info = Get-PresetInfo $Preset
    if ($null -eq $info) {
        throw "unknown model preset: $Preset (use 8m or ebike)"
    }
    if (-not (Test-Path $info.Model)) {
        if ($Preset -eq "8m") {
            Write-Host "yolov8m.pt missing locally; ultralytics may download it on first run." -ForegroundColor Yellow
        } else {
            throw "model file missing: $($info.Model) (set COUNT_YOLO_EBIKE_MODEL)"
        }
    }

    $hasModel = $false
    $hasOutput = $false
    $lineName = "L1"
    for ($i = 0; $i -lt $ArgsList.Count; $i++) {
        $a = [string]$ArgsList[$i]
        if ($a -eq "--model") { $hasModel = $true }
        if ($a -eq "--output") { $hasOutput = $true }
        if (($a -eq "--line") -and (($i + 1) -lt $ArgsList.Count)) {
            $lineName = [string]$ArgsList[$i + 1]
        }
    }

    $out = New-Object System.Collections.Generic.List[string]
    foreach ($a in $ArgsList) { [void]$out.Add([string]$a) }

    if (-not $hasModel -and (Test-Path $info.Model)) {
        [void]$out.Add("--model")
        [void]$out.Add([string]$info.Model)
    }
    if (-not $hasOutput) {
        $outName = "counts_{0}_{1}.json" -f $lineName, $info.Tag
        [void]$out.Add("--output")
        [void]$out.Add((Join-Path $Root ("output\" + $outName)))
    }

    Write-Host ("model preset: {0} -> {1}" -f $Preset, $info.Label) -ForegroundColor Cyan
    Write-Host ("model path:   {0}" -f $info.Model) -ForegroundColor DarkCyan
    return , $out.ToArray()
}

$all = @($args)
if ($all.Count -eq 0) {
    Write-Host "Usage: .\run.ps1 <annotate|count|compare|8m|ebike> [args...]" -ForegroundColor Yellow
    Write-Host "  8m     -> count with yolov8m.pt"
    Write-Host "  ebike  -> count with COUNT_YOLO_EBIKE_MODEL"
    Write-Host "Python: $Python"
    Write-Host "Examples:"
    Write-Host "  .\run.ps1 8m --mode line --line L1_南直行 --device 0"
    Write-Host "  .\run.ps1 ebike --mode line --line L1_南直行 --device 0 --max-seconds 120"
    exit 1
}

$Cmd = [string]$all[0]
$Rest = @()
if ($all.Count -gt 1) {
    $Rest = $all[1..($all.Count - 1)]
}

Push-Location $Root
try {
    switch ($Cmd) {
        "annotate" {
            & $Python "annotate_line.py" @Rest
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        "count" {
            & $Python "count_traffic.py" @Rest
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        "8m" {
            $expanded = Expand-ModelPreset -Preset "8m" -ArgsList $Rest
            & $Python "count_traffic.py" @expanded
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        "ebike" {
            $expanded = Expand-ModelPreset -Preset "ebike" -ArgsList $Rest
            & $Python "count_traffic.py" @expanded
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        "compare" {
            & $Python "compare_ground_truth.py" @Rest
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        default {
            Write-Host "unknown command: $Cmd" -ForegroundColor Red
            exit 1
        }
    }
}
finally {
    Pop-Location
}
