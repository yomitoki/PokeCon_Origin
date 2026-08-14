[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ToolArguments
)

$ErrorActionPreference = 'Stop'
$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceRoot = Split-Path -Parent $toolRoot
$candidates = @(
    (Join-Path $sourceRoot '.venv312\Scripts\python.exe'),
    (Join-Path $sourceRoot '.venv314\Scripts\python.exe'),
    (Join-Path $sourceRoot '.venv314t\Scripts\python.exe')
)
$python = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $python) {
    $command = Get-Command py -ErrorAction SilentlyContinue
    if ($command) {
        & $command.Source -3 (Join-Path $toolRoot 'portable_package.py') @ToolArguments
        exit $LASTEXITCODE
    }
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) { $python = $command.Source }
}
if (-not $python) {
    throw 'Pythonが見つかりません。SetupPokeConPythonEnvironments.ps1を先に実行してください。'
}
& $python (Join-Path $toolRoot 'portable_package.py') @ToolArguments
exit $LASTEXITCODE
