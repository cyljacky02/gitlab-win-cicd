# Queue only. NEVER wait here for ADO: the importer waits for this pipeline to finish.
[CmdletBinding()]
param([string]$ManifestPath = 'out/manifest.json', [string]$ReceiptPath = 'out/bridge-receipt.json')
. (Join-Path $PSScriptRoot '../../shared/Bridge.Common.ps1')
foreach ($name in @('ADO_COLLECTION_URL', 'ADO_PROJECT', 'ADO_PIPELINE_ID', 'ADO_CD_COMMIT', 'ADO_QUEUE_PAT')) {
    if (-not [Environment]::GetEnvironmentVariable($name)) { throw "Missing $name." }
}
Assert-BridgeId $env:ADO_PIPELINE_ID 'ADO_PIPELINE_ID'
Assert-BridgeSha $env:ADO_CD_COMMIT
$base = Get-BridgeBaseUrl $env:ADO_COLLECTION_URL -AllowInsecureHttp:($env:ADO_ALLOW_INSECURE_HTTP -eq 'true')
$manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
Assert-BridgeId ([string]$manifest.jobId) 'manifest jobId'
Assert-BridgeId ([string]$manifest.pipelineId) 'manifest pipelineId'
Assert-BridgeSha ([string]$manifest.commitSha)
if ($manifest.schema -ne 1 -or [string]$manifest.projectId -cne $env:CI_PROJECT_ID -or
    [string]$manifest.projectPath -cne $env:CI_PROJECT_PATH -or
    [string]$manifest.pipelineId -cne $env:CI_PIPELINE_ID -or
    [string]$manifest.commitSha -ine $env:CI_COMMIT_SHA -or
    [string]$manifest.ref -cne $env:CI_COMMIT_BRANCH -or
    [string]$manifest.releaseId -cne ('r' + $env:CI_PIPELINE_IID + '-' + $env:CI_COMMIT_SHA.Substring(0, 8).ToLowerInvariant()) -or
    [string]$manifest.zipSha256 -cnotmatch '^[a-fA-F0-9]{64}$') { throw 'Manifest does not belong to this GitLab pipeline.' }
$body = @{
    # This must point at a CD-owned IMPORT-ONLY pipeline, never a deploy pipeline.
    resources = @{ repositories = @{ self = @{ refName = 'refs/heads/main'; version = $env:ADO_CD_COMMIT } } }
    templateParameters = @{
        gitlabProjectId = [string]$manifest.projectId
        gitlabPipelineId = [string]$manifest.pipelineId
        gitlabJobId = [string]$manifest.jobId
        commitSha = [string]$manifest.commitSha
        releaseId = [string]$manifest.releaseId
        zipSha256 = [string]$manifest.zipSha256
    }
} | ConvertTo-Json -Depth 8 -Compress
$project = [Uri]::EscapeDataString($env:ADO_PROJECT)
$uri = "$base/$project/_apis/pipelines/$($env:ADO_PIPELINE_ID)/runs?api-version=7.0"
$auth = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(':' + $env:ADO_QUEUE_PAT))
try {
    $run = Invoke-BridgeHttp -Uri $uri -Method POST -Headers @{ Authorization = "Basic $auth" } -Body $body
} catch {
    throw 'ADO queue request failed or its outcome is unknown. Check ADO Runs before retrying; no automatic POST retry is performed.'
}
Assert-BridgeId ([string]$run.id) 'ADO run ID'
if ([string]$run.pipeline.id -cne $env:ADO_PIPELINE_ID) { throw 'ADO response pipeline mismatch; reconcile the queued run before retrying.' }
Write-BridgeJson ([ordered]@{
    gitlab_project_id = [string]$manifest.projectId
    gitlab_pipeline_id = [string]$manifest.pipelineId
    gitlab_job_id = [string]$manifest.jobId
    gitlab_commit_sha = [string]$manifest.commitSha
    ado_run_id = [string]$run.id
    ado_pipeline_id = [string]$env:ADO_PIPELINE_ID
    ado_cd_commit = $env:ADO_CD_COMMIT
    queued_at_utc = [DateTime]::UtcNow.ToString('o')
}) $ReceiptPath
Write-Host "ADO importer run $($run.id) queued. This is NOT import success or deployment authorization."
