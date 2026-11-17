. "$PSScriptRoot\common.ps1"
Use-Node22
Push-Location (Join-Path $ProductRoot 'frontend')
try { Invoke-Checked -Executable npm.cmd -Arguments @('run','dev') } finally { Pop-Location }
