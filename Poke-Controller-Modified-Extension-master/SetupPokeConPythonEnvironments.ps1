[CmdletBinding()]
param(
    [ValidateSet("menu", "314", "314t", "312", "all")]
    [string]$Runtime = "menu",
    [switch]$Rebuild,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$rootDir = $PSScriptRoot

$specs = @{
    "312" = [pscustomobject]@{
        Id = "312"
        Label = "Python 3.12 PokeCon環境"
        Version = "3.12"
        Venv = Join-Path $rootDir ".venv312"
        Lock = Join-Path $rootDir "requirements-py312.lock.txt"
        FreeThreaded = $false
    }
    "314" = [pscustomobject]@{
        Id = "314"
        Label = "Python 3.14 Commands互換環境（推奨）"
        Version = "3.14"
        Venv = Join-Path $rootDir ".venv314"
        Lock = Join-Path $rootDir "requirements-py314.lock.txt"
        FreeThreaded = $false
    }
    "314t" = [pscustomobject]@{
        Id = "314t"
        Label = "Python 3.14t GILなし診断環境"
        Version = "3.14"
        Venv = Join-Path $rootDir ".venv314t"
        Lock = Join-Path $rootDir "requirements-py314t-core.lock.txt"
        FreeThreaded = $true
    }
}

function Get-PythonInfo([string]$PythonPath) {
    if (-not $PythonPath -or -not (Test-Path -LiteralPath $PythonPath)) {
        return $null
    }
    try {
        $code = @"
import json, sys, sysconfig
print(json.dumps({
    "version": "%d.%d.%d" % sys.version_info[:3],
    "major_minor": "%d.%d" % sys.version_info[:2],
    "free_threaded": bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
    "executable": sys.executable,
}))
"@ 
        # Windows PowerShell 5.1 removes quotes from a multi-line `python -c`
        # argument. Pass the source as a separate Base64 argument so Python
        # receives it byte-for-byte on every supported runtime.
        $payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code))
        $runner = "import base64,sys;exec(base64.b64decode(sys.argv[1]))"
        $lines = @(& $PythonPath -c $runner $payload 2>$null)
        if ($LASTEXITCODE -ne 0 -or -not $lines) {
            return $null
        }
        return ($lines[-1] | ConvertFrom-Json)
    }
    catch {
        return $null
    }
}

function Test-PythonMatches($Info, $Spec) {
    if ($null -eq $Info -or $Info.major_minor -ne $Spec.Version) {
        return $false
    }
    if ($Spec.FreeThreaded) {
        return [bool]$Info.free_threaded
    }
    return -not [bool]$Info.free_threaded
}

function Find-BasePython($Spec) {
    $executableName = if ($Spec.FreeThreaded) { "python3.14t.exe" } else { "python.exe" }
    $folderName = if ($Spec.Version -eq "3.12") { "Python312" } else { "Python314" }
    $candidates = New-Object System.Collections.Generic.List[string]
    if ($env:LOCALAPPDATA) {
        $candidates.Add((Join-Path $env:LOCALAPPDATA "Programs\Python\$folderName\$executableName"))
    }
    if (${env:ProgramFiles}) {
        $candidates.Add((Join-Path ${env:ProgramFiles} "$folderName\$executableName"))
    }
    if (${env:ProgramFiles(x86)}) {
        $candidates.Add((Join-Path ${env:ProgramFiles(x86)} "$folderName\$executableName"))
    }

    foreach ($candidate in $candidates) {
        $info = Get-PythonInfo $candidate
        if (Test-PythonMatches $info $Spec) {
            return [string]$info.executable
        }
    }

    $launcher = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if ($null -ne $launcher) {
        $selector = if ($Spec.FreeThreaded) { "-3.14t" } else { "-" + $Spec.Version }
        try {
            $resolved = @(& $launcher.Source $selector -c "import sys; print(sys.executable)" 2>$null)
            if ($LASTEXITCODE -eq 0 -and $resolved) {
                $candidate = [string]$resolved[-1]
                $info = Get-PythonInfo $candidate
                if (Test-PythonMatches $info $Spec) {
                    return [string]$info.executable
                }
            }
        }
        catch {
            # The caller prints a friendly missing-Python explanation.
        }
    }
    return $null
}

function Get-VenvPython($Spec) {
    return Join-Path $Spec.Venv "Scripts\python.exe"
}

function Get-EnvironmentStatus($Spec) {
    $basePython = Find-BasePython $Spec
    $venvPython = Get-VenvPython $Spec
    $venvInfo = Get-PythonInfo $venvPython
    return [pscustomobject]@{
        Spec = $Spec
        BasePython = $basePython
        VenvPython = $venvPython
        VenvInfo = $venvInfo
        BaseReady = [bool]$basePython
        LockReady = Test-Path -LiteralPath $Spec.Lock
        VenvReady = Test-PythonMatches $venvInfo $Spec
    }
}

function Show-SetupMenu {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing

    $form = New-Object System.Windows.Forms.Form
    $form.Text = "PokeCon Python環境の作成・修復"
    $form.StartPosition = "CenterScreen"
    $form.FormBorderStyle = "FixedDialog"
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.TopMost = $false
    $form.ClientSize = New-Object System.Drawing.Size(620, 330)
    $form.Font = New-Object System.Drawing.Font("Meiryo UI", 10)

    $title = New-Object System.Windows.Forms.Label
    $title.Location = New-Object System.Drawing.Point(20, 18)
    $title.Size = New-Object System.Drawing.Size(580, 32)
    $title.Font = New-Object System.Drawing.Font("Meiryo UI", 13, [System.Drawing.FontStyle]::Bold)
    $title.Text = "作成または修復するPython環境を選択してください"
    $form.Controls.Add($title)

    $help = New-Object System.Windows.Forms.Label
    $help.Location = New-Object System.Drawing.Point(22, 55)
    $help.Size = New-Object System.Drawing.Size(575, 52)
    $help.Text = "環境フォルダ自体はGitへコミットしません。BAT・固定requirementsだけで同じ環境を再作成できます。通常は既存環境を残したまま修復してください。"
    $form.Controls.Add($help)

    $choice = New-Object System.Windows.Forms.ComboBox
    $choice.Location = New-Object System.Drawing.Point(24, 118)
    $choice.Size = New-Object System.Drawing.Size(570, 32)
    $choice.DropDownStyle = "DropDownList"
    [void]$choice.Items.Add("Python 3.14 Commands互換環境（推奨）")
    [void]$choice.Items.Add("Python 3.12 PokeCon環境")
    [void]$choice.Items.Add("Python 3.14と3.12の両方")
    [void]$choice.Items.Add("Python 3.14t GILなし診断環境（任意）")
    $choice.SelectedIndex = 0
    $form.Controls.Add($choice)

    $rebuildBox = New-Object System.Windows.Forms.CheckBox
    $rebuildBox.Location = New-Object System.Drawing.Point(24, 168)
    $rebuildBox.Size = New-Object System.Drawing.Size(570, 28)
    $rebuildBox.Text = "既存環境を削除して最初から作り直す（通常はチェック不要）"
    $rebuildBox.Checked = $false
    $form.Controls.Add($rebuildBox)

    $warning = New-Object System.Windows.Forms.Label
    $warning.Location = New-Object System.Drawing.Point(44, 200)
    $warning.Size = New-Object System.Drawing.Size(550, 45)
    $warning.Text = "未チェック：不足ライブラリを追加・修復します。`r`nチェックあり：選択した.venvフォルダだけを削除して再作成します。"
    $form.Controls.Add($warning)

    $start = New-Object System.Windows.Forms.Button
    $start.Location = New-Object System.Drawing.Point(304, 268)
    $start.Size = New-Object System.Drawing.Size(180, 40)
    $start.Text = "作成・修復を開始"
    $start.Add_Click({
        $ids = @("314", "312", "all", "314t")
        $form.Tag = [pscustomobject]@{
            Runtime = $ids[$choice.SelectedIndex]
            Rebuild = [bool]$rebuildBox.Checked
        }
        $form.DialogResult = [System.Windows.Forms.DialogResult]::OK
        $form.Close()
    })
    $form.Controls.Add($start)

    $cancel = New-Object System.Windows.Forms.Button
    $cancel.Location = New-Object System.Drawing.Point(494, 268)
    $cancel.Size = New-Object System.Drawing.Size(100, 40)
    $cancel.Text = "キャンセル"
    $cancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
    $form.CancelButton = $cancel
    $form.Controls.Add($cancel)

    if ($form.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
        return $null
    }
    return $form.Tag
}

function Invoke-Checked([string]$Executable, [string[]]$Arguments, [string]$Description) {
    Write-Host ""
    Write-Host "[実行] $Description" -ForegroundColor Cyan
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Description に失敗しました（終了コード: $LASTEXITCODE）。"
    }
}

function Remove-EnvironmentSafely($Spec) {
    if (-not (Test-Path -LiteralPath $Spec.Venv)) {
        return
    }
    $resolvedRoot = [System.IO.Path]::GetFullPath($rootDir).TrimEnd('\')
    $resolvedTarget = [System.IO.Path]::GetFullPath($Spec.Venv).TrimEnd('\')
    $expectedTarget = [System.IO.Path]::GetFullPath((Join-Path $rootDir (".venv" + $Spec.Id))).TrimEnd('\')
    if ($resolvedTarget -ne $expectedTarget -or
        -not $resolvedTarget.StartsWith($resolvedRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "安全確認に失敗したため環境を削除しません: $resolvedTarget"
    }
    Write-Host "既存環境を削除します: $resolvedTarget" -ForegroundColor Yellow
    Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
}

function Install-Environment($Spec, [bool]$ForceRebuild) {
    Write-Host ""
    Write-Host ("=" * 72) -ForegroundColor DarkGray
    Write-Host $Spec.Label -ForegroundColor Green
    Write-Host ("=" * 72) -ForegroundColor DarkGray

    if (-not (Test-Path -LiteralPath $Spec.Lock)) {
        throw "固定requirementsが見つかりません: $($Spec.Lock)"
    }
    $basePython = Find-BasePython $Spec
    if (-not $basePython) {
        $kind = if ($Spec.FreeThreaded) { "free-threaded版 " } else { "" }
        throw "$kind Python $($Spec.Version) 本体が見つかりません。Python本体をインストールしてから、このBATをもう一度実行してください。"
    }
    Write-Host "Python本体: $basePython"
    Write-Host "環境フォルダ: $($Spec.Venv)"
    Write-Host "固定requirements: $($Spec.Lock)"

    if ($ForceRebuild) {
        Remove-EnvironmentSafely $Spec
    }

    $venvPython = Get-VenvPython $Spec
    $venvInfo = Get-PythonInfo $venvPython
    if (-not (Test-PythonMatches $venvInfo $Spec)) {
        if (Test-Path -LiteralPath $Spec.Venv) {
            throw "既存環境のPython種類が一致しません。GUIで「" +
                "既存環境を削除して最初から作り直す」をチェックしてください: $($Spec.Venv)"
        }
        Invoke-Checked $basePython @("-m", "venv", $Spec.Venv) "仮想環境の作成"
    }

    if (-not (Test-Path -LiteralPath $venvPython)) {
        throw "仮想環境のPythonを作成できませんでした: $venvPython"
    }
    Invoke-Checked $venvPython @("-m", "ensurepip", "--upgrade") "pipの準備"
    Invoke-Checked $venvPython @("-m", "pip", "install", "--disable-pip-version-check", "-r", $Spec.Lock) "固定ライブラリのインストール"
    Invoke-Checked $venvPython @("-m", "pip", "check") "依存関係の確認"

    $verified = Get-PythonInfo $venvPython
    if (-not (Test-PythonMatches $verified $Spec)) {
        throw "作成後のPython環境が選択内容と一致しません: $venvPython"
    }
    if ($Spec.FreeThreaded) {
        $statusScript = Join-Path $rootDir "PokeConFreeThreadedStatus.py"
        if (Test-Path -LiteralPath $statusScript) {
            Invoke-Checked $venvPython @($statusScript, "--check-only") "GILなし対応状況の確認"
        }
    }
    Write-Host "[完了] $($Spec.Label)" -ForegroundColor Green
}

try {
    if ($Runtime -eq "menu" -and -not $CheckOnly) {
        $selection = Show-SetupMenu
        if ($null -eq $selection) {
            Write-Host "キャンセルしました。"
            exit 0
        }
        $Runtime = [string]$selection.Runtime
        $Rebuild = [bool]$selection.Rebuild
    }
    elseif ($Runtime -eq "menu") {
        $Runtime = "all"
    }

    $targetIds = if ($Runtime -eq "all") { @("314", "312") } else { @($Runtime) }
    $targets = @($targetIds | ForEach-Object { $specs[$_] })

    if ($CheckOnly) {
        $failed = $false
        foreach ($spec in $targets) {
            $status = Get-EnvironmentStatus $spec
            $state = if ($status.VenvReady -and $status.LockReady) { "使用可能" } else { "要作成・修復" }
            Write-Host ("{0}: {1}" -f $spec.Label, $state)
            Write-Host ("  Python本体: {0}" -f $(if ($status.BasePython) { $status.BasePython } else { "未検出" }))
            Write-Host ("  仮想環境: {0}" -f $status.VenvPython)
            Write-Host ("  requirements: {0}" -f $(if ($status.LockReady) { "あり" } else { "なし" }))
            if ($state -ne "使用可能") { $failed = $true }
        }
        if ($failed) { exit 2 }
        exit 0
    }

    if ($Rebuild) {
        Write-Host "注意: 選択した仮想環境を削除してから再作成します。" -ForegroundColor Yellow
    }
    foreach ($spec in $targets) {
        Install-Environment $spec ([bool]$Rebuild)
    }

    Write-Host ""
    Write-Host "すべて完了しました。ExecutePokeConModified-Extension.batから起動できます。" -ForegroundColor Green
    exit 0
}
catch {
    Write-Host ""
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "仮想環境以外のPokeConソースやInputSetは変更していません。" -ForegroundColor Yellow
    exit 1
}
