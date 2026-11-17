. "$PSScriptRoot\common.ps1"
Push-Location $ProductRoot
try { Invoke-Checked -Executable $PythonExe -Arguments @('-m','screenshotlegal.cli.seed') } finally { Pop-Location }
