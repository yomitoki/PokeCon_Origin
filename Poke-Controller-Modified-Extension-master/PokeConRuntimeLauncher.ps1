param(
    [ValidateSet("menu", "314", "314t", "312", "37", "last")]
    [string]$Runtime = "menu",
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$rootDir = $PSScriptRoot
$statePath = Join-Path $rootDir ".pokecon-python-version"
$python314 = Join-Path $rootDir ".venv314\Scripts\python.exe"
$python314t = Join-Path $rootDir ".venv314t\Scripts\python.exe"
$python312 = Join-Path $rootDir ".venv312\Scripts\python.exe"
$uiPath = Join-Path $rootDir "PokeConRuntimeLauncher.ja.json"
$ui = [pscustomobject]@{
    window_title = "PokeCon Python runtime selection"
    heading = "Select Python before starting PokeCon"
    help = "Use Python 3.14 compatibility for the full PokeCon. The 3.14t button shows GIL-free readiness."
    button_314 = "Python 3.14 (Commands compatibility / GIL on) - {0}"
    button_314t = "Python 3.14t (GIL off readiness) - {0}"
    button_312 = "Python 3.12 (Recommended) - {0}"
    button_37 = "Python 3.7 (Compatibility) - {0}"
    button_last = "Use previous selection: {0}"
    cancel = "Cancel"
    note = "The selection is saved and can be changed at every startup."
    error_title = "PokeCon startup error"
    missing_runtime = "{0} was not found. Select another runtime or prepare the missing environment."
    startup_failed = "PokeCon could not be started.`r`n`r`n{0}"
}
if (Test-Path -LiteralPath $uiPath) {
    try {
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        $ui = [System.IO.File]::ReadAllText($uiPath, $utf8) | ConvertFrom-Json
    }
    catch {
        Write-Warning "The Japanese UI resource could not be loaded. English labels will be used."
    }
}

function Find-Python37 {
    $projectPython = Join-Path $rootDir ".venv37\Scripts\python.exe"
    if (Test-Path -LiteralPath $projectPython) {
        return $projectPython
    }

    $knownPython = "C:\Program Files\Python37\python.exe"
    if (Test-Path -LiteralPath $knownPython) {
        return $knownPython
    }

    $launcher = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if ($null -ne $launcher) {
        try {
            $resolved = & $launcher.Source -3.7 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $resolved -and (Test-Path -LiteralPath $resolved[-1])) {
                return $resolved[-1]
            }
        }
        catch {
            # The GUI below reports that Python 3.7 is unavailable.
        }
    }

    return $null
}

function Get-SavedRuntime {
    if (-not (Test-Path -LiteralPath $statePath)) {
        return "314"
    }

    $saved = (Get-Content -LiteralPath $statePath -TotalCount 1).Trim()
    if ($saved -in @("314", "314t", "312", "37")) {
        return $saved
    }
    return "314"
}

function Get-PythonDescription([string]$PythonPath) {
    if (-not $PythonPath -or -not (Test-Path -LiteralPath $PythonPath)) {
        return "Not installed"
    }
    try {
        $versionCommand = "import platform; print(platform.python_version())"
        $version = & $PythonPath -c $versionCommand 2>$null
        if ($LASTEXITCODE -eq 0 -and $version) {
            $versionText = @($version)[-1]
            return "Python $versionText"
        }
    }
    catch {
        return "Installed but could not be started"
    }
    return "Installed but could not be started"
}

function Show-ErrorDialog([string]$Message) {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(
        $Message,
        $ui.error_title,
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
}

function Show-RuntimeMenu([string]$Python37Path, [string]$SavedRuntime) {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing

    $form = New-Object System.Windows.Forms.Form
    $form.Text = $ui.window_title
    $form.StartPosition = "CenterScreen"
    $form.FormBorderStyle = "FixedDialog"
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.TopMost = $false
    $form.ClientSize = New-Object System.Drawing.Size(560, 420)
    $form.Font = New-Object System.Drawing.Font("Meiryo UI", 10)

    $title = New-Object System.Windows.Forms.Label
    $title.Location = New-Object System.Drawing.Point(20, 18)
    $title.Size = New-Object System.Drawing.Size(520, 32)
    $title.Font = New-Object System.Drawing.Font("Meiryo UI", 13, [System.Drawing.FontStyle]::Bold)
    $title.Text = $ui.heading
    $form.Controls.Add($title)

    $help = New-Object System.Windows.Forms.Label
    $help.Location = New-Object System.Drawing.Point(22, 55)
    $help.Size = New-Object System.Drawing.Size(515, 48)
    $help.Text = $ui.help
    $form.Controls.Add($help)

    $button314 = New-Object System.Windows.Forms.Button
    $button314.Location = New-Object System.Drawing.Point(22, 105)
    $button314.Size = New-Object System.Drawing.Size(516, 48)
    $button314.Text = $ui.button_314 -f (Get-PythonDescription $python314)
    $button314.Enabled = Test-Path -LiteralPath $python314
    $button314.Add_Click({ $form.Tag = "314"; $form.DialogResult = "OK"; $form.Close() })
    $form.Controls.Add($button314)

    $button314t = New-Object System.Windows.Forms.Button
    $button314t.Location = New-Object System.Drawing.Point(22, 159)
    $button314t.Size = New-Object System.Drawing.Size(516, 48)
    $button314t.Text = $ui.button_314t -f (Get-PythonDescription $python314t)
    $button314t.Enabled = Test-Path -LiteralPath $python314t
    $button314t.Add_Click({ $form.Tag = "314t"; $form.DialogResult = "OK"; $form.Close() })
    $form.Controls.Add($button314t)

    $button312 = New-Object System.Windows.Forms.Button
    $button312.Location = New-Object System.Drawing.Point(22, 213)
    $button312.Size = New-Object System.Drawing.Size(516, 48)
    $button312.Text = $ui.button_312 -f (Get-PythonDescription $python312)
    $button312.Enabled = Test-Path -LiteralPath $python312
    $button312.Add_Click({ $form.Tag = "312"; $form.DialogResult = "OK"; $form.Close() })
    $form.Controls.Add($button312)

    $button37 = New-Object System.Windows.Forms.Button
    $button37.Location = New-Object System.Drawing.Point(22, 267)
    $button37.Size = New-Object System.Drawing.Size(516, 48)
    $button37.Text = $ui.button_37 -f (Get-PythonDescription $Python37Path)
    $button37.Enabled = [bool]$Python37Path
    $button37.Add_Click({ $form.Tag = "37"; $form.DialogResult = "OK"; $form.Close() })
    $form.Controls.Add($button37)

    if ($SavedRuntime -eq "314t") {
        $savedText = "Python 3.14t GIL off readiness"
    }
    elseif ($SavedRuntime -eq "314") {
        $savedText = "Python 3.14 compatibility"
    }
    elseif ($SavedRuntime -eq "37") {
        $savedText = "Python 3.7"
    }
    else {
        $savedText = "Python 3.12"
    }
    $buttonLast = New-Object System.Windows.Forms.Button
    $buttonLast.Location = New-Object System.Drawing.Point(22, 327)
    $buttonLast.Size = New-Object System.Drawing.Size(360, 38)
    $buttonLast.Text = $ui.button_last -f $savedText
    $buttonLast.Enabled = (($SavedRuntime -eq "314" -and (Test-Path -LiteralPath $python314)) -or
        ($SavedRuntime -eq "314t" -and (Test-Path -LiteralPath $python314t)) -or
        ($SavedRuntime -eq "312" -and (Test-Path -LiteralPath $python312)) -or
        ($SavedRuntime -eq "37" -and [bool]$Python37Path))
    $buttonLast.Add_Click({ $form.Tag = $SavedRuntime; $form.DialogResult = "OK"; $form.Close() })
    $form.Controls.Add($buttonLast)

    $cancel = New-Object System.Windows.Forms.Button
    $cancel.Location = New-Object System.Drawing.Point(398, 327)
    $cancel.Size = New-Object System.Drawing.Size(140, 38)
    $cancel.Text = $ui.cancel
    $cancel.DialogResult = "Cancel"
    $form.CancelButton = $cancel
    $form.Controls.Add($cancel)

    $note = New-Object System.Windows.Forms.Label
    $note.Location = New-Object System.Drawing.Point(22, 375)
    $note.Size = New-Object System.Drawing.Size(515, 35)
    $note.Text = $ui.note
    $form.Controls.Add($note)

    $result = $form.ShowDialog()
    if ($result -ne [System.Windows.Forms.DialogResult]::OK) {
        return $null
    }
    return [string]$form.Tag
}

$python37 = Find-Python37
$savedRuntime = Get-SavedRuntime
$selectedRuntime = $Runtime

if ($selectedRuntime -eq "menu") {
    $selectedRuntime = Show-RuntimeMenu $python37 $savedRuntime
    if (-not $selectedRuntime) {
        exit 0
    }
}
elseif ($selectedRuntime -eq "last") {
    $selectedRuntime = $savedRuntime
}

$pythonPath = if ($selectedRuntime -eq "314") {
    $python314
}
elseif ($selectedRuntime -eq "314t") {
    $python314t
}
elseif ($selectedRuntime -eq "37") {
    $python37
}
else {
    $python312
}
if (-not $pythonPath -or -not (Test-Path -LiteralPath $pythonPath)) {
    $label = if ($selectedRuntime -eq "314") {
        "Python 3.14 compatibility environment (.venv314)"
    }
    elseif ($selectedRuntime -eq "314t") {
        "Python 3.14 free-threaded environment (.venv314t)"
    }
    elseif ($selectedRuntime -eq "37") {
        "Python 3.7"
    }
    else {
        "Python 3.12 PokeCon environment (.venv312)"
    }
    Show-ErrorDialog ($ui.missing_runtime -f $label)
    exit 3
}

Set-Content -LiteralPath $statePath -Value $selectedRuntime -Encoding Ascii
$description = Get-PythonDescription $pythonPath
Write-Host "PokeCon runtime: $description"
Write-Host "Python executable: $pythonPath"

if ($CheckOnly) {
    if ($selectedRuntime -eq "314t") {
        $env:PYTHON_GIL = "0"
        & $pythonPath (Join-Path $rootDir "PokeConFreeThreadedStatus.py") --check-only
        exit $LASTEXITCODE
    }
    exit 0
}

if ($selectedRuntime -eq "314t") {
    $env:PYTHON_GIL = "0"
    $env:POKECON_PYTHON_MODE = "314t-status"
    & $pythonPath (Join-Path $rootDir "PokeConFreeThreadedStatus.py")
    exit $LASTEXITCODE
}

if ($selectedRuntime -eq "314") {
    $env:POKECON_PYTHON_MODE = "314-compat"
    $env:POKECON_RUNTIME_LABEL = "Python 3.14 compatibility / GIL on"
}
elseif ($selectedRuntime -eq "312") {
    $env:POKECON_PYTHON_MODE = "312"
    $env:POKECON_RUNTIME_LABEL = "Python 3.12"
}
else {
    $env:POKECON_PYTHON_MODE = "37"
    $env:POKECON_RUNTIME_LABEL = "Python 3.7 compatibility"
}

$updateChecker = Join-Path $rootDir "SerialController\PokeConUpdateChecker.py"
$controllerDir = Join-Path $rootDir "SerialController"
$windowScript = Join-Path $controllerDir "Window.py"

try {
    & $pythonPath $updateChecker
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "The update checker exited with code $LASTEXITCODE. PokeCon startup will continue."
    }

    Push-Location $controllerDir
    try {
        & $pythonPath $windowScript
        $windowExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}
catch {
    Show-ErrorDialog ($ui.startup_failed -f $_.Exception.Message)
    exit 4
}

if ($null -eq $windowExitCode) {
    $windowExitCode = 0
}
exit $windowExitCode
