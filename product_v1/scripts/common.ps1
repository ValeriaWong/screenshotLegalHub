$ErrorActionPreference = 'Stop'
$ProductRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProductRoot 'backend\.venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Executable failed with exit code $LASTEXITCODE" }
}

function Use-Node22 {
    $candidatePaths = @()
    if ($env:NVM_HOME) {
        $candidatePaths += @(Get-ChildItem -LiteralPath $env:NVM_HOME -Directory -Filter 'v22.*' | Sort-Object Name -Descending | ForEach-Object { Join-Path $_.FullName 'node.exe' })
    }
    $nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($nodeCommand) { $candidatePaths += $nodeCommand.Source }
    foreach ($candidatePath in $candidatePaths) {
        if ((Test-Path -LiteralPath $candidatePath) -and ((& $candidatePath --version) -match '^v22\.')) {
            $env:PATH = (Split-Path -Parent $candidatePath) + ';' + $env:PATH
            return
        }
    }
    throw 'Node 22 LTS is required. Install Node 22 or add its directory to PATH.'
}
