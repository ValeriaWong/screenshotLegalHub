param([switch]$SkipBrowser)
. "$PSScriptRoot\common.ps1"
Push-Location $ProductRoot
try {
    Use-Node22
    if ($env:NODE_TLS_REJECT_UNAUTHORIZED -eq '0') { Remove-Item Env:NODE_TLS_REJECT_UNAUTHORIZED }
    if (-not (Get-Command uv.exe -ErrorAction SilentlyContinue)) { throw 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/' }
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $ProductRoot '.tools\python'
    $env:UV_LINK_MODE = 'copy'
    if (-not (Test-Path -LiteralPath $PythonExe)) {
        Invoke-Checked -Executable uv.exe -Arguments @('python','install','3.12')
        Invoke-Checked -Executable uv.exe -Arguments @('venv','--python','3.12','backend/.venv')
    }
    if ((& $PythonExe --version) -notmatch '^Python 3\.12\.') { throw 'Python 3.12 required' }
    Invoke-Checked -Executable uv.exe -Arguments @('pip','sync','--python',$PythonExe,'backend/requirements.lock')
    Invoke-Checked -Executable uv.exe -Arguments @('pip','install','--python',$PythonExe,'--no-deps','-e','backend')
    Invoke-Checked -Executable $PythonExe -Arguments @('-m','alembic','-c','backend/alembic.ini','upgrade','head')
    Invoke-Checked -Executable $PythonExe -Arguments @('tools/export_openapi.py')
    Push-Location frontend
    try {
        Invoke-Checked -Executable npm.cmd -Arguments @('ci','--no-audit','--no-fund')
        Invoke-Checked -Executable npm.cmd -Arguments @('run','generate:api')
        if (-not $SkipBrowser) { Invoke-Checked -Executable npx.cmd -Arguments @('playwright','install','chromium') }
    } finally { Pop-Location }
    Invoke-Checked -Executable $PythonExe -Arguments @('-m','screenshotlegal.cli.seed')
} finally { Pop-Location }
