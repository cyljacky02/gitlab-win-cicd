# CD-owned PS 5.1: ZIP tracked checkout files only; never execute application code.
[CmdletBinding()]
param(
    [string]$SourceDirectory,
    [string]$ProvenanceDirectory,
    [string]$PackageDirectory,
    [string]$ExpectedCommitSha = $env:EXPECTED_COMMIT_SHA,
    [string]$ExpectedBuildId = $env:BUILD_BUILDID,
    [string]$ExpectedRepositoryUrl = $env:SOURCE_REPOSITORY_URL,
    [string]$ExpectedSourceRef = $env:SOURCE_REF
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function New-GitLabSourcePackage {
    param(
        [string]$SourceDirectory, [string]$ProvenanceDirectory, [string]$PackageDirectory,
        [string]$ExpectedCommitSha, [string]$ExpectedBuildId,
        [string]$ExpectedRepositoryUrl, [string]$ExpectedSourceRef
    )
    if ($ExpectedCommitSha -cnotmatch '\A[0-9a-fA-F]{40}\z' -or $ExpectedCommitSha -eq ('0' * 40)) { throw 'Expected a nonzero full GitLab commit SHA.' }
    if ($ExpectedBuildId -cnotmatch '\A[1-9][0-9]*\z') { throw 'Expected the current ADO build ID.' }
    $sha = $ExpectedCommitSha.ToLowerInvariant()
    if (-not $SourceDirectory -or -not $ProvenanceDirectory -or -not $PackageDirectory) { throw 'Source, provenance and package directories are required.' }
    $source = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($SourceDirectory)
    $output = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PackageDirectory)
    if (-not (Test-Path -LiteralPath (Join-Path $source '.git') -PathType Container)) { throw 'Expected the verified isolated Git checkout.' }
    if ((Test-Path -LiteralPath $output) -or $output.StartsWith($source.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Use a new package directory outside the source checkout.' }
    $evidenceFile = Join-Path $ProvenanceDirectory 'source-provenance.json'
    $record = [IO.File]::ReadAllText($evidenceFile) | ConvertFrom-Json
    if ($record.gitlabCommitSha -cne $sha -or $record.adoBuildId -cne $ExpectedBuildId -or
        $record.repositoryUrl -cne $ExpectedRepositoryUrl -or $record.sourceRef -cne $ExpectedSourceRef -or
        $record.applicationBuildExecuted -ne $false) { throw 'Source provenance differs from this repository/ref/SHA/ADO run.' }

    # Import the existing hardened, credential-free Git process helper in this scope.
    # Its top-level parameter names deliberately differ from this function's inputs.
    . (Join-Path $PSScriptRoot 'Get-GitLabSource.ps1')
    $git = Get-Command git.exe -ErrorAction SilentlyContinue
    $gitPath = if ($git) { $git.Source } else { Join-Path $env:AGENT_HOMEDIRECTORY 'externals\git\cmd\git.exe' }
    $gitArgs = @{ GitPath = $gitPath; Directory = $source }
    if ((Invoke-SourceGit @gitArgs -Arguments @('rev-parse', 'HEAD')) -cne $sha) { throw 'Checkout HEAD differs from the requested SHA.' }
    $null = Invoke-SourceGit @gitArgs -Arguments @('diff', '--no-ext-diff', '--no-textconv', '--exit-code', 'HEAD', '--')
    $tree = Invoke-SourceGit @gitArgs -Arguments @('ls-tree', '-rz', '--full-tree', 'HEAD')
    $entries = @($tree.Split([char]0) | Where-Object { $_.Length -gt 0 })
    if ($entries.Count -eq 0) { throw 'The selected source tree contains no files.' }

    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $parent = Split-Path -Parent $output
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    $temp = Join-Path $parent ('.source-package-' + [Guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($temp) | Out-Null
    $zipName = "Rayin-$ExpectedBuildId-$sha.zip"
    $zipPath = Join-Path $temp $zipName
    $zip = $null
    try {
        $zip = [IO.Compression.ZipFile]::Open($zipPath, [IO.Compression.ZipArchiveMode]::Create)
        foreach ($item in $entries) {
            if ($item -notmatch '(?s)\A(100644|100755) blob [0-9a-f]{40}\t(.+)\z') { throw 'Only regular tracked files are supported; symlinks/submodules are refused.' }
            $relative = $Matches[2]
            if ($relative -match '[\x00-\x1f\\:"<>|?*]' -or $relative.StartsWith('/') -or
                @($relative.Split('/') | Where-Object { $_ -in @('', '.', '..', '.git') }).Count -gt 0) { throw 'Unsupported or unsafe tracked path.' }
            $file = Join-Path $source $relative.Replace('/', '\')
            $current = Get-Item -LiteralPath $file -Force
            if ($current.PSIsContainer -or ($current.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Tracked source must be a regular file.' }
            # Do not silently deliver LFS pointer text as the real content.
            $stream = [IO.File]::OpenRead($file)
            try {
                $prefix = New-Object byte[] 128
                $length = $stream.Read($prefix, 0, $prefix.Length)
                if ([Text.Encoding]::ASCII.GetString($prefix, 0, $length).StartsWith('version https://git-lfs.github.com/spec/v1')) { throw 'Git LFS pointers are unsupported; no package is published.' }
            } finally { $stream.Dispose() }
            $null = [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $file, $relative, [IO.Compression.CompressionLevel]::Optimal)
        }
        $zip.Dispose(); $zip = $null
        $manifest = [ordered]@{
            schema = 1; purpose = 'GitLabSourceZipDeliveryOnly'
            repositoryUrl = $ExpectedRepositoryUrl; sourceRef = $ExpectedSourceRef; gitlabCommitSha = $sha
            adoBuildId = $ExpectedBuildId; adoToolCommit = [string]$env:BUILD_SOURCEVERSION
            zipFileName = $zipName; zipSha256 = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
            zipLength = (Get-Item -LiteralPath $zipPath).Length; fileCount = $entries.Count
            packagedAtUtc = [DateTime]::UtcNow.ToString('o'); applicationBuildExecuted = $false
        }
        [IO.File]::WriteAllText((Join-Path $temp 'source-package.json'), ($manifest | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
        [IO.File]::Copy($evidenceFile, (Join-Path $temp 'source-provenance.json'))
        [IO.Directory]::Move($temp, $output)
        Write-Host "Packaged $($entries.Count) tracked checkout files: $zipName"
        Write-Host "ZIP SHA-256: $($manifest.zipSha256). No application build executed."
    } finally {
        if ($zip) { $zip.Dispose() }
        if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Recurse -Force }
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    New-GitLabSourcePackage -SourceDirectory $SourceDirectory -ProvenanceDirectory $ProvenanceDirectory -PackageDirectory $PackageDirectory -ExpectedCommitSha $ExpectedCommitSha -ExpectedBuildId $ExpectedBuildId -ExpectedRepositoryUrl $ExpectedRepositoryUrl -ExpectedSourceRef $ExpectedSourceRef
}
