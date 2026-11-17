$ErrorActionPreference = 'Stop'
$ProductRoot = Split-Path -Parent $PSScriptRoot
$BasePython = Join-Path $ProductRoot '.conda/screenshotlegal-v1/python.exe'
$ParserRoot = Join-Path $ProductRoot '.tools/mineru-env'
& $BasePython -m venv $ParserRoot
if ($LASTEXITCODE -ne 0) { throw 'Cannot create parser environment' }
& (Join-Path $ParserRoot 'Scripts/python.exe') -m pip install -r (Join-Path $PSScriptRoot 'documents-requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Cannot install parser dependencies' }
