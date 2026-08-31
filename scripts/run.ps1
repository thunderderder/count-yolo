# Thin wrapper so `scripts/` is a stable entry. Real launcher lives at repo root.
$here = Split-Path -Parent $PSScriptRoot
& (Join-Path $here "run.ps1") @args
