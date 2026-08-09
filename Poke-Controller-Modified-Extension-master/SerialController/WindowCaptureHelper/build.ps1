$ErrorActionPreference = "Stop"

$vsTools = "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.35.32215"
$sdk = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersion = "10.0.22621.0"
$compiler = Join-Path $vsTools "bin\Hostx64\x64\cl.exe"
$source = Join-Path $PSScriptRoot "WindowCaptureHelper.cpp"
$output = Join-Path $PSScriptRoot "PokeConWindowCapture.exe"

& $compiler /nologo /std:c++17 /EHsc /O2 /MT /utf-8 /DUNICODE /D_UNICODE `
  "/I$vsTools\include" `
  "/I$sdk\Include\$sdkVersion\ucrt" `
  "/I$sdk\Include\$sdkVersion\shared" `
  "/I$sdk\Include\$sdkVersion\um" `
  "/I$sdk\Include\$sdkVersion\winrt" `
  "/I$sdk\Include\$sdkVersion\cppwinrt" `
  $source "/Fo:$PSScriptRoot\WindowCaptureHelper.obj" /Fe:$output /link /SUBSYSTEM:WINDOWS `
  "/LIBPATH:$vsTools\lib\x64" `
  "/LIBPATH:$sdk\Lib\$sdkVersion\ucrt\x64" `
  "/LIBPATH:$sdk\Lib\$sdkVersion\um\x64" `
  d3d11.lib dxgi.lib windowsapp.lib user32.lib shell32.lib

if ($LASTEXITCODE -ne 0) { throw "WindowCaptureHelper build failed: $LASTEXITCODE" }
Remove-Item -LiteralPath (Join-Path $PSScriptRoot "WindowCaptureHelper.obj") -ErrorAction SilentlyContinue
Write-Host "Built $output"
