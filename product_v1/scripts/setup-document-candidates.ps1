param(
    [ValidateSet("docling","paddle")][string]$Engine = "docling",
    [string]$Python = "$PSScriptRoot\..\.conda\screenshotlegal-v1\python.exe"
)
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$environmentRoot = Join-Path $projectRoot ".tools\$Engine-env"
if (!(Test-Path "$environmentRoot\Scripts\python.exe")) {
    & $Python -m venv $environmentRoot
    if ($LASTEXITCODE -ne 0) { throw "Unable to create isolated environment" }
}
$parserPython = "$environmentRoot\Scripts\python.exe"
if ($Engine -eq "docling") {
    & $parserPython -m pip install "docling-slim[format-office,format-pdf-pypdfium2]==2.143.1"
} else {
    & $parserPython -m pip install "paddleocr[doc-parser]==3.7.0" "paddlex[ocr]==3.7.2" "paddlepaddle==3.3.1" "pypdfium2==5.14.0"
}
if ($LASTEXITCODE -ne 0) { throw "Parser installation failed; existing default remains available" }
Write-Host "Installed isolated $Engine packages."
Write-Host "Run scripts/compare_document_parsers.py to verify native Office against MinerU."
Write-Host "Paddle remains a candidate until local models and original-coordinate smoke are verified."
