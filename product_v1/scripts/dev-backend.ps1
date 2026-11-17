. "$PSScriptRoot\common.ps1"
Push-Location $ProductRoot
try {
    $BackendArguments = @('-m','uvicorn','screenshotlegal.api.main:app','--host','0.0.0.0','--port','18430')
    $NetworkEnv = Join-Path $ProductRoot '.env.network'
    if (Test-Path -LiteralPath $NetworkEnv) { $BackendArguments += @('--env-file',$NetworkEnv) }
    Invoke-Checked -Executable $PythonExe -Arguments $BackendArguments
} finally { Pop-Location }
