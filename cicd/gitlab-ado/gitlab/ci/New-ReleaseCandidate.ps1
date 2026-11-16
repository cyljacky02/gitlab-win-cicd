# Run on a GitLab Windows shell runner after the real build/tests succeed.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$InputDirectory,
    [string]$OutputDirectory = 'out'
)
. (Join-Path $PSScriptRoot '../../shared/Bridge.Common.ps1')
foreach ($name in @('CI_PROJECT_ID', 'CI_PIPELINE_ID', 'CI_PIPELINE_IID', 'CI_JOB_ID')) {
    Assert-BridgeId ([Environment]::GetEnvironmentVariable($name)) $name
}
Assert-BridgeSha $env:CI_COMMIT_SHA
if (-not $env:CI_COMMIT_BRANCH -or $env:CI_COMMIT_TAG -or -not $env:CI_PROJECT_PATH) {
    throw 'Only a branch build with CI_PROJECT_PATH can produce a candidate.'
}
$source = (Resolve-Path -LiteralPath $InputDirectory).Path
if (-not (Test-Path -LiteralPath $source -PathType Container)) { throw 'InputDirectory must be a directory.' }
if (Test-Path -LiteralPath (Join-Path $source 'release.json')) { throw 'Root release.json is reserved for the bridge; resolve this package-layout conflict first.' }
$output = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputDirectory)
if ($source.TrimEnd('\', '/') -eq $output.TrimEnd('\', '/') -or
    $output.StartsWith($source.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'OutputDirectory must be outside InputDirectory.'
}
$items = @(Get-Item -LiteralPath $source) + @(Get-ChildItem -LiteralPath $source -Recurse -Force)
if (@($items | Where-Object { ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 }).Count) {
    throw 'Reparse points are not permitted in the package input.'
}
if (@($items | Where-Object { -not $_.PSIsContainer }).Count -eq 0) { throw 'Package input is empty.' }
[IO.Directory]::CreateDirectory($output) | Out-Null
$zip = Join-Path $output 'site.zip'
$manifestPath = Join-Path $output 'manifest.json'
foreach ($path in @($zip, $manifestPath)) {
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
}
$releaseId = 'r' + $env:CI_PIPELINE_IID + '-' + $env:CI_COMMIT_SHA.Substring(0, 8).ToLowerInvariant()
$marker = [ordered]@{
    releaseId = $releaseId
    commitSha = $env:CI_COMMIT_SHA.ToLowerInvariant()
    projectId = [long]$env:CI_PROJECT_ID
    pipelineId = [long]$env:CI_PIPELINE_ID
    jobId = [long]$env:CI_JOB_ID
}
# Stage a copy: do not modify the actual build output when adding release.json.
$temp = Join-Path $output ('.package-' + [Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($temp) | Out-Null
try {
    Get-ChildItem -LiteralPath $source -Force | Copy-Item -Destination $temp -Recurse -Force
    Write-BridgeJson $marker (Join-Path $temp 'release.json')
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory($temp, $zip, [IO.Compression.CompressionLevel]::Optimal, $false)
} finally { Remove-Item -LiteralPath $temp -Recurse -Force }
# Preserve the latest DIRECT-AGENT package's manifest field names and release ID.
$manifest = [ordered]@{
    schema = 1
    releaseId = $releaseId
    projectId = [long]$env:CI_PROJECT_ID
    projectPath = [string]$env:CI_PROJECT_PATH
    pipelineId = [long]$env:CI_PIPELINE_ID
    jobId = [long]$env:CI_JOB_ID
    commitSha = $env:CI_COMMIT_SHA.ToLowerInvariant()
    ref = [string]$env:CI_COMMIT_BRANCH
    zipName = 'site.zip'
    zipSha256 = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
    zipBytes = (Get-Item -LiteralPath $zip).Length
}
Write-BridgeJson $manifest $manifestPath
Write-Host "Packaged candidate $($manifest.projectId)/$($manifest.pipelineId)/$($manifest.jobId)."
