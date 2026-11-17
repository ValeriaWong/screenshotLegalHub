param([string]$TexBin = 'D:\texlive\2023\bin\windows')
$ErrorActionPreference = 'Stop'
$PaperRoot = $PSScriptRoot
$RepoRoot = Split-Path -Parent $PaperRoot
$PaperBuild = Join-Path $RepoRoot 'tmp\paper\build'
$PaperOutput = Join-Path $RepoRoot 'output\pdf'
New-Item -ItemType Directory -Path $PaperBuild,$PaperOutput -Force | Out-Null
$LatexExe = Join-Path $TexBin 'pdflatex.exe'
$BibExe = Join-Path $TexBin 'bibtex.exe'
if (!(Test-Path -LiteralPath $LatexExe) -or !(Test-Path -LiteralPath $BibExe)) {
    throw 'pdflatex/bibtex unavailable; specify -TexBin.'
}
$OldBibInputs = $env:BIBINPUTS
$OldBstInputs = $env:BSTINPUTS
Push-Location $PaperRoot
try {
    & $LatexExe -interaction=nonstopmode -halt-on-error -no-shell-escape "-output-directory=$PaperBuild" main.tex
    if ($LASTEXITCODE -ne 0) { throw 'First LaTeX pass failed.' }
    $env:BIBINPUTS = "$PaperRoot;"
    $env:BSTINPUTS = "$(Join-Path $PaperRoot 'vendor');$PaperRoot;"
    Push-Location $PaperBuild
    try {
        & $BibExe main
        if ($LASTEXITCODE -ne 0) { throw 'BibTeX failed.' }
    } finally { Pop-Location }
    1..3 | ForEach-Object {
        & $LatexExe -interaction=nonstopmode -halt-on-error -no-shell-escape "-output-directory=$PaperBuild" main.tex
        if ($LASTEXITCODE -ne 0) { throw 'LaTeX pass failed.' }
    }
    Copy-Item -LiteralPath (Join-Path $PaperBuild 'main.pdf') -Destination (Join-Path $PaperOutput 'screenshotlegalbench_working_draft.pdf') -Force
} finally {
    Pop-Location
    $env:BIBINPUTS = $OldBibInputs
    $env:BSTINPUTS = $OldBstInputs
}
