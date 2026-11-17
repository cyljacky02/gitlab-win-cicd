# CD-owned PS 5.1: verify this run's package and deliver the ZIP itself, never extract it.
[CmdletBinding()]
param(
    [string]$ArtifactDirectory,
    [string]$DestinationDirectory = 'D:\TestCICD',
    [string]$ExpectedCommitSha = $env:EXPECTED_COMMIT_SHA,
    [string]$ExpectedBuildId = $env:BUILD_BUILDID,
    [string]$ExpectedRepositoryUrl = $env:SOURCE_REPOSITORY_URL,
    [string]$ExpectedSourceRef = $env:SOURCE_REF
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Copy-GitLabSourcePackage {
    param(
        [string]$ArtifactDirectory, [string]$DestinationDirectory,
        [string]$ExpectedCommitSha, [string]$ExpectedBuildId,
        [string]$ExpectedRepositoryUrl, [string]$ExpectedSourceRef
    )
    if ($ExpectedCommitSha -cnotmatch '\A[0-9a-fA-F]{40}\z' -or $ExpectedCommitSha -eq ('0' * 40)) { throw 'Expected a nonzero full GitLab commit SHA.' }
    if ($ExpectedBuildId -cnotmatch '\A[1-9][0-9]*\z') { throw 'Expected the current ADO build ID.' }
    $sha = $ExpectedCommitSha.ToLowerInvariant()
    if (-not $ArtifactDirectory -or -not $DestinationDirectory) { throw 'Artifact and destination directories are required.' }
    $manifestFile = Join-Path $ArtifactDirectory 'source-package.json'
    $manifestInfo = Get-Item -LiteralPath $manifestFile -Force
    if ($manifestInfo.Length -gt 65536 -or ($manifestInfo.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Invalid package manifest.' }
    $manifest = [IO.File]::ReadAllText($manifestFile) | ConvertFrom-Json
    $zipName = "Rayin-$ExpectedBuildId-$sha.zip"
    if ($manifest.schema -ne 1 -or $manifest.purpose -cne 'GitLabSourceZipDeliveryOnly' -or
        $manifest.adoBuildId -cne $ExpectedBuildId -or $manifest.gitlabCommitSha -cne $sha -or
        $manifest.repositoryUrl -cne $ExpectedRepositoryUrl -or $manifest.sourceRef -cne $ExpectedSourceRef -or
        $manifest.zipFileName -cne $zipName -or $manifest.zipSha256 -cnotmatch '\A[0-9a-f]{64}\z' -or
        $manifest.applicationBuildExecuted -ne $false) { throw 'Package does not match the authorized repository/ref/SHA/ADO run.' }
    # Derive the file name locally; never use manifest-controlled paths for copying.
    $sourceZip = Join-Path $ArtifactDirectory $zipName
    $info = Get-Item -LiteralPath $sourceZip -Force
    if ($info.PSIsContainer -or ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        $info.Length -le 0 -or $info.Length -ne $manifest.zipLength -or
        (Get-FileHash -LiteralPath $sourceZip -Algorithm SHA256).Hash.ToLowerInvariant() -cne $manifest.zipSha256) { throw 'ZIP size/hash/type verification failed before delivery.' }

    # Only local absolute Windows paths below a drive root, no UNC/device/relative paths.
    if ($DestinationDirectory -notmatch '\A[A-Za-z]:\\' -or $DestinationDirectory -match '[\x00-\x1f"<>|?*]' -or
        $DestinationDirectory.Substring(2).Contains(':') -or
        @($DestinationDirectory.Substring(3).Split('\') | Where-Object { $_ -in @('.', '..') -or $_ -match '[. ]$' }).Count -gt 0) { throw 'Destination must be a normal absolute local Windows directory.' }
    $destination = [IO.Path]::GetFullPath($DestinationDirectory).TrimEnd('\')
    $driveRoot = [IO.Path]::GetPathRoot($destination)
    if ($destination -eq $driveRoot.TrimEnd('\') -or -not [IO.Directory]::Exists($driveRoot)) { throw 'Refusing drive-root delivery, or destination drive is absent.' }
    # Reject junctions/symlinks in every existing destination ancestor.
    $ancestor = $destination
    while ($ancestor) {
        if (Test-Path -LiteralPath $ancestor) {
            $item = Get-Item -LiteralPath $ancestor -Force
            if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Destination or ancestor is a file/reparse point.' }
        }
        $ancestor = Split-Path -Parent $ancestor
    }
    [IO.Directory]::CreateDirectory($destination) | Out-Null
    $target = Join-Path $destination $zipName
    if (Test-Path -LiteralPath $target) {
        $existing = Get-Item -LiteralPath $target -Force
        if (-not $existing.PSIsContainer -and -not ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint) -and
            $existing.Length -eq $manifest.zipLength -and
            (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $manifest.zipSha256) {
            Write-Host "Identical ZIP already delivered: $target (no overwrite)."
            return
        }
        throw 'Destination file already exists with different content/type; nothing overwritten.'
    }
    $temp = Join-Path $destination ('.Rayin-copy-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    try {
        [IO.File]::Copy($sourceZip, $temp, $false)
        if ((Get-FileHash -LiteralPath $temp -Algorithm SHA256).Hash.ToLowerInvariant() -cne $manifest.zipSha256) { throw 'Copied ZIP hash mismatch; no final ZIP delivered.' }
        # Same-directory move is atomic and never overwrites an existing final file.
        [IO.File]::Move($temp, $target)
        Write-Host "Delivered ZIP: $target"
        Write-Host "ZIP SHA-256: $($manifest.zipSha256). No extraction, build or service operation executed."
    } finally {
        if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Force }
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    Copy-GitLabSourcePackage -ArtifactDirectory $ArtifactDirectory -DestinationDirectory $DestinationDirectory -ExpectedCommitSha $ExpectedCommitSha -ExpectedBuildId $ExpectedBuildId -ExpectedRepositoryUrl $ExpectedRepositoryUrl -ExpectedSourceRef $ExpectedSourceRef
}
