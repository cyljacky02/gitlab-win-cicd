# Management-side IMPORT ONLY. Never clone or execute GitLab repository content.
[CmdletBinding()]
param(
    [string]$PolicyPath,
    [string]$PipelineId = $env:GITLAB_PIPELINE_ID,
    [string]$JobId = $env:GITLAB_JOB_ID,
    [string]$CommitSha = $env:GITLAB_COMMIT_SHA,
    [string]$OutputDirectory,
    [string]$ExpectedProjectId = $env:GITLAB_PROJECT_ID,
    [string]$ExpectedReleaseId = $env:GITLAB_RELEASE_ID,
    [string]$ExpectedZipSha256 = $env:GITLAB_ZIP_SHA256
)
. (Join-Path $PSScriptRoot '../../shared/Bridge.Common.ps1')

function Assert-CandidateJob {
    param($Job, $Policy, [string]$ExpectedPipelineId, [string]$ExpectedSha)
    if ([string]$Job.status -cne 'success' -or $Job.allow_failure -ne $false -or
        $Job.tag -ne $false -or [string]$Job.ref -cne [string]$Policy.allowedRef -or
        [string]$Job.pipeline.id -cne $ExpectedPipelineId -or [string]$Job.commit.id -ine $ExpectedSha) {
        throw 'Required job is not a successful blocking branch job for this pipeline/SHA.'
    }
}

function Invoke-GitLabCandidateImport {
    param(
        [string]$PolicyPath, [string]$PipelineId, [string]$JobId, [string]$CommitSha, [string]$OutputDirectory,
        [string]$ExpectedProjectId, [string]$ExpectedReleaseId, [string]$ExpectedZipSha256
    )
    Assert-BridgeId $PipelineId 'GitLab pipeline ID'
    Assert-BridgeId $JobId 'GitLab job ID'
    Assert-BridgeSha $CommitSha
    if (-not $env:GITLAB_READ_TOKEN) { throw 'Missing GITLAB_READ_TOKEN (ADO secret variable).' }
    $policy = Get-Content -LiteralPath $PolicyPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($policy.schemaVersion -ne 1) { throw 'Unsupported import policy schema.' }
    Assert-BridgeId ([string]$policy.projectId) 'policy project ID'
    if ($ExpectedProjectId -and $ExpectedProjectId -cne [string]$policy.projectId) { throw 'Not the policy project.' }
    if (-not $policy.projectPath -or -not $policy.allowedRef -or -not $policy.packageJobName -or
        -not $policy.packageJobStage -or @($policy.requiredJobs).Count -eq 0 -or
        $policy.allowInsecureHttp -isnot [bool] -or
        $policy.waitForPipelineSeconds -lt 1 -or $policy.waitForPipelineSeconds -gt 1800 -or
        $policy.pollIntervalSeconds -lt 1 -or $policy.pollIntervalSeconds -gt 60 -or
        $policy.maxPackageBytes -lt 1 -or $policy.maxPackageBytes -gt 1073741824 -or
        $policy.maxExpandedBytes -lt 1 -or $policy.maxExpandedBytes -gt 4294967296 -or
        $policy.maxZipEntries -lt 1 -or $policy.maxZipEntries -gt 100000) { throw 'Invalid import policy bounds.' }
    $base = Get-BridgeBaseUrl ([string]$policy.gitlabBaseUrl) -AllowInsecureHttp:($policy.allowInsecureHttp)
    $api = "$base/api/v4/projects/$($policy.projectId)"
    $headers = @{ 'PRIVATE-TOKEN' = $env:GITLAB_READ_TOKEN }
    $project = Invoke-BridgeHttp -Uri $api -Headers $headers
    if ([string]$project.id -cne [string]$policy.projectId -or
        [string]$project.path_with_namespace -cne [string]$policy.projectPath) { throw 'GitLab project identity mismatch.' }
    $timer = [Diagnostics.Stopwatch]::StartNew()
    do {
        $pipeline = Invoke-BridgeHttp -Uri "$api/pipelines/$PipelineId" -Headers $headers
        if ([string]$pipeline.id -cne $PipelineId -or [string]$pipeline.project_id -cne [string]$policy.projectId -or
            [string]$pipeline.sha -ine $CommitSha -or [string]$pipeline.ref -cne [string]$policy.allowedRef -or
            [string]$pipeline.source -cne 'push') { throw 'GitLab pipeline identity/source/ref/SHA mismatch.' }
        if ([string]$pipeline.status -ceq 'success') { break }
        if ([string]$pipeline.status -notin @('created', 'waiting_for_resource', 'preparing', 'pending', 'running', 'manual', 'scheduled')) {
            throw 'GitLab pipeline did not succeed; no candidate will be published.'
        }
        if ($timer.Elapsed.TotalSeconds -ge $policy.waitForPipelineSeconds) { throw 'Timed out waiting for final GitLab pipeline success.' }
        Write-Host 'Waiting for final GitLab pipeline success (notification job must exit, not wait for ADO).'
        Start-Sleep -Seconds ([int]$policy.pollIntervalSeconds)
    } while ($true)

    # Paginate current, non-retried jobs. A supplied historical job ID must not
    # silently replace the currently selected package job after a GitLab retry.
    $jobs = @(); $page = 1
    do {
        $batch = @(Invoke-BridgeHttp -Uri "$api/pipelines/$PipelineId/jobs?include_retried=false&per_page=100&page=$page" -Headers $headers)
        $jobs += $batch
        if ($batch.Count -lt 100) { break }
        $page++
        if ($page -gt 100) { throw 'Job pagination limit reached; refusing partial verification.' }
    } while ($true)
    foreach ($required in $policy.requiredJobs) {
        $matches = @($jobs | Where-Object { $_.name -ceq $required.name -and $_.stage -ceq $required.stage })
        if ($matches.Count -ne 1) { throw 'Missing or ambiguous required job; parallel/child jobs need an explicit policy redesign.' }
        Assert-CandidateJob $matches[0] $policy $PipelineId $CommitSha
    }
    $packages = @($jobs | Where-Object { $_.name -ceq $policy.packageJobName -and $_.stage -ceq $policy.packageJobStage })
    if ($packages.Count -ne 1 -or [string]$packages[0].id -cne $JobId) { throw 'Not the unique current package job; candidate may have been retried.' }
    $job = Invoke-BridgeHttp -Uri "$api/jobs/$JobId" -Headers $headers
    if ([string]$job.id -cne $JobId -or $job.name -cne $policy.packageJobName -or $job.stage -cne $policy.packageJobStage) {
        throw 'Package job identity mismatch.'
    }
    Assert-CandidateJob $job $policy $PipelineId $CommitSha

    if (-not $OutputDirectory) { throw 'OutputDirectory is required.' }
    $output = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputDirectory)
    if (Test-Path -LiteralPath $output) { throw 'OutputDirectory already exists; use a clean build staging directory.' }
    $parent = Split-Path -Parent $output
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    $temp = Join-Path $parent ('.candidate-' + [Guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($temp) | Out-Null
    try {
        $manifestPath = Join-Path $temp 'manifest.json'
        $zipPath = Join-Path $temp 'site.zip'
        Invoke-BridgeHttp -Uri "$api/jobs/$JobId/artifacts/out/manifest.json" -Headers $headers -OutFile $manifestPath -MaxBytes 65536
        $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        Assert-BridgeId ([string]$pipeline.iid) 'GitLab pipeline IID'
        $expectedRelease = 'r' + [string]$pipeline.iid + '-' + $CommitSha.Substring(0, 8).ToLowerInvariant()
        if ($manifest.schema -ne 1 -or [string]$manifest.projectId -cne [string]$policy.projectId -or
            [string]$manifest.projectPath -cne [string]$policy.projectPath -or
            [string]$manifest.pipelineId -cne $PipelineId -or [string]$manifest.jobId -cne $JobId -or
            [string]$manifest.commitSha -ine $CommitSha -or [string]$manifest.ref -cne [string]$policy.allowedRef -or
            [string]$manifest.releaseId -cne $expectedRelease -or [string]$manifest.zipName -cne 'site.zip' -or
            [string]$manifest.zipSha256 -cnotmatch '^[a-fA-F0-9]{64}$') { throw 'Manifest schema/provenance mismatch.' }
        if (($ExpectedReleaseId -and $ExpectedReleaseId -cne [string]$manifest.releaseId) -or
            ($ExpectedZipSha256 -and $ExpectedZipSha256 -ine [string]$manifest.zipSha256)) { throw 'Notification and downloaded manifest disagree.' }
        [long]$expectedSize = 0
        if (-not [long]::TryParse([string]$manifest.zipBytes, [ref]$expectedSize) -or
            $expectedSize -lt 1 -or $expectedSize -gt $policy.maxPackageBytes) { throw 'Manifest package size is invalid.' }
        Invoke-BridgeHttp -Uri "$api/jobs/$JobId/artifacts/out/site.zip" -Headers $headers -OutFile $zipPath -MaxBytes ([long]$policy.maxPackageBytes)
        $hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ((Get-Item -LiteralPath $zipPath).Length -ne $expectedSize -or $hash -ine [string]$manifest.zipSha256) { throw 'Package size/SHA-256 mismatch.' }
        Test-BridgeZip -Path $zipPath -MaxExpandedBytes ([long]$policy.maxExpandedBytes) -MaxEntries ([int]$policy.maxZipEntries)
        Assert-BridgeZipMarker -Path $zipPath -Manifest $manifest
        $verification = [ordered]@{
            schema_version = 1
            candidate_id = "$($policy.projectId)-$PipelineId-$JobId"
            release_id = [string]$manifest.releaseId
            gitlab_base_url = $base
            project_id = [string]$policy.projectId
            project_path = [string]$policy.projectPath
            pipeline_id = $PipelineId
            job_id = $JobId
            ref = [string]$policy.allowedRef
            sha = $CommitSha.ToLowerInvariant()
            package = 'site.zip'
            sha256 = $hash
            size_bytes = $expectedSize
            pipeline_status_at_verification = [string]$pipeline.status
            verified_at_utc = [DateTime]::UtcNow.ToString('o')
            ado_build_id = [string]$env:BUILD_BUILDID
            ado_cd_commit = [string]$env:BUILD_SOURCEVERSION
            policy_sha256 = (Get-FileHash -LiteralPath $PolicyPath -Algorithm SHA256).Hash.ToLowerInvariant()
        }
        Write-BridgeJson $verification (Join-Path $temp 'verification.json')
        [IO.Directory]::Move($temp, $output)
        Write-Host "Verified candidate $($verification.candidate_id). Import only; no deployment dispatched."
    } finally {
        if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Recurse -Force }
    }
}

# Dot-sourcing exposes the functions for offline tests without contacting a server.
if ($MyInvocation.InvocationName -ne '.') {
    Invoke-GitLabCandidateImport -PolicyPath $PolicyPath -PipelineId $PipelineId -JobId $JobId -CommitSha $CommitSha -OutputDirectory $OutputDirectory -ExpectedProjectId $ExpectedProjectId -ExpectedReleaseId $ExpectedReleaseId -ExpectedZipSha256 $ExpectedZipSha256
}
