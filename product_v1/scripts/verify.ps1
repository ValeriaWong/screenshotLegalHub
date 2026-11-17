. "$PSScriptRoot\common.ps1"
& "$PSScriptRoot\test.ps1"
Use-Node22
Push-Location (Join-Path $ProductRoot 'frontend')
try { Invoke-Checked -Executable npm.cmd -Arguments @('run','e2e') } finally { Pop-Location }
Write-Host 'Backend, frontend, build, architecture guards, browser E2E and accessibility smoke passed.'
