# Process audio capture helper

`ApplicationLoopback.exe` captures audio rendered by the selected Windows
process and its child processes. It is based on Microsoft's Application
Loopback API sample:

https://github.com/microsoft/Windows-classic-samples/tree/main/Samples/ApplicationLoopback

PokeCon starts the helper with the selected game window's process ID. This
build waits for a newline on standard input instead of stopping after ten
seconds, allowing PokeCon to finalize the WAV file when recording stops.

The API requires Windows 10 build 20348 or later.
