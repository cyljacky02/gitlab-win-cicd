# Run AFTER authorization and artifact download, BEFORE the existing deployment tool.
# This verifies an explicitly selected importer build; it does not authorize/deploy.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ArtifactDirectory,
    [Parameter(Mandatory = $true)][string]$ExpectedImportBuildId,
    [Parameter(Mandatory = $true)][string]$ExpectedProjectId,
    [Parameter(Mandatory = $true)][string]$ExpectedRef,
    [Parameter(Mandatory = $true)][string]$ExpectedCandidateId,
    [Parameter(Mandatory = $true)][string]$ExpectedReleaseId
)
. (Join-Path $PSScriptRoot '../../shared/Bridge.Common.ps1')
Assert-BridgeId $ExpectedImportBuildId 'expected importer build ID'
Assert-BridgeId $ExpectedProjectId 'expected GitLab project ID'
$root = (Resolve-Path -LiteralPath $ArtifactDirectory).Path
$verification = Get-Content -LiteralPath (Join-Path $root 'verification.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$manifest = Get-Content -LiteralPath (Join-Path $root 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$zip = Join-Path $root 'site.zip'
Assert-BridgeSha ([string]$verification.sha)
Assert-BridgeId ([string]$verification.pipeline_id) 'verified pipeline ID'
Assert-BridgeId ([string]$verification.job_id) 'verified job ID'
if ($verification.schema_version -ne 1 -or $manifest.schema -ne 1 -or
    [string]$verification.ado_build_id -cne $ExpectedImportBuildId -or
    [string]$verification.project_id -cne $ExpectedProjectId -or
    [string]$verification.ref -cne $ExpectedRef -or
    [string]$verification.candidate_id -cne $ExpectedCandidateId -or
    [string]$verification.release_id -cne $ExpectedReleaseId -or
    [string]$verification.candidate_id -cne "$ExpectedProjectId-$($verification.pipeline_id)-$($verification.job_id)" -or
    [string]$verification.pipeline_status_at_verification -cne 'success' -or
    [string]$verification.package -cne 'site.zip' -or [string]$manifest.zipName -cne 'site.zip' -or
    [string]$manifest.releaseId -cne $ExpectedReleaseId -or
    [string]$manifest.projectId -cne $ExpectedProjectId -or
    [string]$manifest.projectPath -cne [string]$verification.project_path -or
    [string]$manifest.pipelineId -cne [string]$verification.pipeline_id -or
    [string]$manifest.jobId -cne [string]$verification.job_id -or
    [string]$manifest.commitSha -ine [string]$verification.sha -or
    [string]$manifest.ref -cne $ExpectedRef) { throw 'Candidate does not match the explicitly selected authorization subject.' }
$hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
if ($hash -ine [string]$verification.sha256 -or $hash -ine [string]$manifest.zipSha256 -or
    (Get-Item -LiteralPath $zip).Length -ne $verification.size_bytes -or
    (Get-Item -LiteralPath $zip).Length -ne $manifest.zipBytes) { throw 'Downloaded candidate hash/length mismatch.' }
Test-BridgeZip -Path $zip -MaxExpandedBytes 268435456 -MaxEntries 10000
Assert-BridgeZipMarker -Path $zip -Manifest $manifest
Write-Host "Verified selected candidate $ExpectedCandidateId from importer build $ExpectedImportBuildId. No deployment performed."
