[CmdletBinding()]
param(
    [string]$PackageRoot = $PSScriptRoot,
    [Parameter(Mandatory = $true)]
    [string]$TargetRoot,
    [ValidateSet('Backup', 'Fail', 'Skip', 'Replace')]
    [string]$Overwrite = 'Backup',
    [switch]$VerifyOnly
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem

if ([string]::IsNullOrWhiteSpace($PackageRoot)) {
    $PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$packagePath = [System.IO.Path]::GetFullPath($PackageRoot)
$manifestPath = Join-Path $packagePath 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "manifest.jsonが見つかりません: $manifestPath"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.format -ne 'pokecon-portable-package' -or [int]$manifest.format_version -ne 1) {
    throw '未対応のパッケージ形式です。'
}

$targetPath = [System.IO.Path]::GetFullPath($TargetRoot)
$targetPrefix = $targetPath
if (-not $targetPrefix.EndsWith([string][System.IO.Path]::DirectorySeparatorChar)) {
    $targetPrefix += [System.IO.Path]::DirectorySeparatorChar
}
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$logPath = Join-Path $targetPath ".pokecon-package-restore-$stamp.log"
$events = [System.Collections.Generic.List[string]]::new()

function Write-Event([string]$Message) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
    $events.Add($line)
    Write-Host $line
}

function Get-SafeTarget([string]$RelativePath) {
    if ([string]::IsNullOrWhiteSpace($RelativePath) -or
            [System.IO.Path]::IsPathRooted($RelativePath)) {
        throw "不正な相対パスです: $RelativePath"
    }
    $normalized = $RelativePath.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
    $full = [System.IO.Path]::GetFullPath((Join-Path $targetPath $normalized))
    if (-not $full.StartsWith($targetPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "復元先の外へ出るパスを拒否しました: $RelativePath"
    }
    return $full
}

function ConvertTo-LongPath([string]$Path) {
    if ($Path.StartsWith('\\?\')) {
        return $Path
    }
    if ($Path.StartsWith('\\')) {
        return '\\?\UNC\' + $Path.Substring(2)
    }
    return '\\?\' + $Path
}

function Assert-Hash([string]$Path, [string]$Expected, [string]$Label) {
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $Expected.ToLowerInvariant()) {
        throw "SHA-256不一致: $Label`n期待値: $Expected`n実際値: $actual"
    }
}

function Install-TemporaryFile([string]$Temporary, [string]$Destination, [string]$ModifiedUtc) {
    $longTemporary = ConvertTo-LongPath $Temporary
    $longDestination = ConvertTo-LongPath $Destination
    if ([System.IO.File]::Exists($longDestination)) {
        if ([System.IO.Directory]::Exists($longDestination)) {
            throw "ファイル復元先に同名フォルダがあります: $Destination"
        }
        switch ($Overwrite) {
            'Fail' { throw "既存ファイルがあります: $Destination" }
            'Skip' {
                [System.IO.File]::Delete($longTemporary)
                return 'Skipped'
            }
            'Backup' {
                $backup = "$Destination.pre_restore_$stamp"
                $serial = 0
                while ([System.IO.File]::Exists((ConvertTo-LongPath $backup))) {
                    $serial++
                    $backup = "$Destination.pre_restore_${stamp}_$serial"
                }
                [System.IO.File]::Move($longDestination, (ConvertTo-LongPath $backup))
            }
            'Replace' { [System.IO.File]::Delete($longDestination) }
        }
    }
    [System.IO.File]::Move($longTemporary, $longDestination)
    if ($ModifiedUtc) {
        [System.IO.File]::SetLastWriteTimeUtc(
            $longDestination, [datetime]::Parse($ModifiedUtc).ToUniversalTime())
    }
    return 'Installed'
}

Write-Event "パッケージ検証開始: $packagePath"
$seenVolumes = @{}
foreach ($volume in @($manifest.volumes)) {
    $volumePath = Join-Path $packagePath ([string]$volume.name)
    if ($seenVolumes.ContainsKey($volumePath)) { continue }
    $seenVolumes[$volumePath] = $true
    if (-not (Test-Path -LiteralPath $volumePath -PathType Leaf)) {
        throw "分割ファイルが見つかりません: $volumePath"
    }
    if ([int64](Get-Item -LiteralPath $volumePath).Length -ne [int64]$volume.size) {
        throw "サイズ不一致: $($volume.name)"
    }
    Assert-Hash $volumePath ([string]$volume.sha256) ([string]$volume.name)
}
Write-Event "分割ファイル検証完了: $($seenVolumes.Count)個"

if ($VerifyOnly) {
    Write-Event '検証のみ完了しました。復元先は変更していません。'
    exit 0
}

[System.IO.Directory]::CreateDirectory($targetPath) | Out-Null
$restoreTempRoot = Join-Path $targetPath '.pokecon_restore_temp'
[System.IO.Directory]::CreateDirectory($restoreTempRoot) | Out-Null
$installed = 0
$skipped = 0

$zipFiles = @($manifest.files | Where-Object { $_.storage.kind -eq 'zip' })
foreach ($group in @($zipFiles | Group-Object { $_.storage.volume })) {
    $volumePath = Join-Path $packagePath $group.Name
    $archive = [System.IO.Compression.ZipFile]::OpenRead($volumePath)
    try {
        $entryTable = @{}
        foreach ($entry in $archive.Entries) { $entryTable[$entry.FullName] = $entry }
        foreach ($record in $group.Group) {
            $entryName = [string]$record.storage.entry
            if (-not $entryTable.ContainsKey($entryName)) {
                throw "ZIP内エントリが見つかりません: $($group.Name) / $entryName"
            }
            $destination = Get-SafeTarget ([string]$record.relative_path)
            $parent = Split-Path -Parent $destination
            [System.IO.Directory]::CreateDirectory((ConvertTo-LongPath $parent)) | Out-Null
            $temporary = Join-Path $restoreTempRoot ([guid]::NewGuid().ToString('N') + '.tmp')
            try {
                $input = $entryTable[$entryName].Open()
                $output = [System.IO.File]::Open($temporary, [System.IO.FileMode]::CreateNew)
                try { $input.CopyTo($output) } finally { $output.Dispose(); $input.Dispose() }
                if ([int64](Get-Item -LiteralPath $temporary).Length -ne [int64]$record.size) {
                    throw "復元サイズ不一致: $($record.relative_path)"
                }
                Assert-Hash $temporary ([string]$record.sha256) ([string]$record.relative_path)
                $result = Install-TemporaryFile $temporary $destination ([string]$record.mtime_utc)
                if ($result -eq 'Skipped') { $skipped++ } else { $installed++ }
            } finally {
                if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
            }
        }
    } finally {
        $archive.Dispose()
    }
}

$chunkFiles = @($manifest.files | Where-Object { $_.storage.kind -eq 'gzip_chunks' })
foreach ($record in $chunkFiles) {
    $destination = Get-SafeTarget ([string]$record.relative_path)
    $parent = Split-Path -Parent $destination
    [System.IO.Directory]::CreateDirectory((ConvertTo-LongPath $parent)) | Out-Null
    $temporary = Join-Path $restoreTempRoot ([guid]::NewGuid().ToString('N') + '.tmp')
    try {
        $output = [System.IO.File]::Open($temporary, [System.IO.FileMode]::CreateNew)
        try {
            foreach ($chunk in @($record.storage.chunks)) {
                $chunkPath = Join-Path $packagePath ([string]$chunk.name)
                $input = [System.IO.File]::OpenRead($chunkPath)
                $gzip = [System.IO.Compression.GZipStream]::new(
                    $input, [System.IO.Compression.CompressionMode]::Decompress)
                try { $gzip.CopyTo($output) } finally { $gzip.Dispose(); $input.Dispose() }
            }
        } finally {
            $output.Dispose()
        }
        if ([int64](Get-Item -LiteralPath $temporary).Length -ne [int64]$record.size) {
            throw "復元サイズ不一致: $($record.relative_path)"
        }
        Assert-Hash $temporary ([string]$record.sha256) ([string]$record.relative_path)
        $result = Install-TemporaryFile $temporary $destination ([string]$record.mtime_utc)
        if ($result -eq 'Skipped') { $skipped++ } else { $installed++ }
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
    }
}

Remove-Item -LiteralPath $restoreTempRoot -Force
Write-Event "復元完了: 反映 $installed ファイル / スキップ $skipped ファイル"
$events | Set-Content -LiteralPath $logPath -Encoding UTF8
Write-Host "ログ: $logPath"
