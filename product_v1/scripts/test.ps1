. "$PSScriptRoot\common.ps1"
Use-Node22
Push-Location (Join-Path $ProductRoot 'backend')
try { Invoke-Checked -Executable $PythonExe -Arguments @('-m','pytest','-q') } finally { Pop-Location }
Push-Location (Join-Path $ProductRoot 'frontend')
try {
    Invoke-Checked -Executable npm.cmd -Arguments @('run','typecheck')
    Invoke-Checked -Executable npm.cmd -Arguments @('run','lint')
    Invoke-Checked -Executable npm.cmd -Arguments @('run','test')
    Invoke-Checked -Executable npm.cmd -Arguments @('run','build')
} finally { Pop-Location }
