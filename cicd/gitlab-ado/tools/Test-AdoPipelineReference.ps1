# Operator-only Windows PowerShell 5.1 probe. GET requests only: never queues a run.
# Run locally with the SAME ADO PAT used in the GitLab Authorization header.
[CmdletBinding()]
param(
    [string]$ProjectUrl = 'http://10.92.4.86/DefaultCollection/Deployment',
    [ValidateRange(1,2147483647)][int]$PipelineId = 5,
    [string]$SourceRef = 'refs/heads/poc/webhook-smoke',
    [Security.SecureString]$Pat
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-AdoProbeField($Object, [string]$Name) {
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -ne $property) { return $property.Value }
    return $null
}

function Get-AdoProbeJson([string]$Url, [string]$Authorization) {
    $request = [Net.HttpWebRequest]::Create($Url)
    $request.Method = 'GET'
    $request.AllowAutoRedirect = $false
    $request.UseDefaultCredentials = $false
    $request.Credentials = $null
    $request.Accept = 'application/json'
    $request.ContentType = 'application/json'
    $request.Headers['Authorization'] = $Authorization
    $request.Headers['X-TFS-FedAuthRedirect'] = 'Suppress'
    $request.Timeout = 15000
    $request.ReadWriteTimeout = 15000
    $response = $null; $reader = $null
    try {
        try { $response = $request.GetResponse() }
        catch [Net.WebException] {
            if ($_.Exception.Response) { $response = $_.Exception.Response }
            else { return [pscustomobject]@{ Status=$null; Format=('network-' + [string]$_.Exception.Status); Json=$null } }
        }
        $status = [int]$response.StatusCode
        # Do not read/log server error pages, identities, challenges or cookies.
        if ($status -ne 200) { return [pscustomobject]@{ Status=$status; Format='http-error-or-redirect'; Json=$null } }
        $reader = New-Object IO.StreamReader($response.GetResponseStream())
        $buffer = New-Object char[] 4096
        $text = New-Object Text.StringBuilder
        while (($length = $reader.Read($buffer, 0, $buffer.Length)) -gt 0) {
            if ($text.Length + $length -gt 1048576) { return [pscustomobject]@{ Status=$status; Format='response-too-large'; Json=$null } }
            $null = $text.Append($buffer, 0, $length)
        }
        try { $json = $text.ToString() | ConvertFrom-Json -ErrorAction Stop }
        catch { return [pscustomobject]@{ Status=$status; Format='non-json'; Json=$null } }
        return [pscustomobject]@{ Status=$status; Format='json'; Json=$json }
    } finally {
        if ($reader) { $reader.Dispose() }
        if ($response) { $response.Dispose() }
        $request.Abort()
    }
}

function Get-AdoPipelineReferenceReport {
    param([string]$ProjectUrl, [int]$PipelineId, [string]$SourceRef, [Security.SecureString]$Pat)
    $uri = $null
    if (-not [Uri]::TryCreate($ProjectUrl, [UriKind]::Absolute, [ref]$uri) -or
        $uri.Scheme -notin @('http','https') -or $uri.UserInfo -or $uri.Query -or $uri.Fragment) { throw 'Use a project URL without credentials, query parameters or fragments.' }
    if ($SourceRef -cnotmatch '\Arefs/heads/[A-Za-z0-9._/-]+\z') { throw 'Expected an explicit ADO refs/heads/... reference.' }
    if (-not $Pat -or $Pat.Length -eq 0) { throw 'The same ADO trigger PAT is required; do not use the GitLab source token.' }
    $base = $ProjectUrl.TrimEnd('/')
    $report = [ordered]@{
        pipelineId = $PipelineId; requestedAdoRef = $SourceRef
        definitionHttpStatus = $null; definitionFormat = $null; definitionId = $null; pipelineName = $null
        adoRepoId = $null; adoRepoName = $null; adoRepoType = $null; definitionDefaultBranch = $null; yamlPath = $null
        refsHttpStatus = $null; refsFormat = $null; exactRefCount = $null; refTipCommit = $null
        successRunsHttpStatus = $null; successRunsFormat = $null
        lastSuccessfulRunId = $null; lastSuccessfulRepoId = $null; lastSuccessfulAdoRef = $null; lastSuccessfulAdoToolCommit = $null
    }
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Pat)
    $authorization = $null; $plain = $null
    try {
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        if ($plain -match '[\r\n]') { throw 'PAT input contains an invalid newline.' }
        $authorization = 'Basic ' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(':' + $plain))
        $plain = $null
        $definition = Get-AdoProbeJson "$base/_apis/build/definitions/${PipelineId}?api-version=7.1" $authorization
        $report.definitionHttpStatus = $definition.Status; $report.definitionFormat = $definition.Format
        if ($null -eq $definition.Json) { return [pscustomobject]$report }
        $repository = Get-AdoProbeField $definition.Json 'repository'
        $process = Get-AdoProbeField $definition.Json 'process'
        $report.definitionId = Get-AdoProbeField $definition.Json 'id'
        $report.pipelineName = Get-AdoProbeField $definition.Json 'name'
        $report.adoRepoId = Get-AdoProbeField $repository 'id'
        $report.adoRepoName = Get-AdoProbeField $repository 'name'
        $report.adoRepoType = Get-AdoProbeField $repository 'type'
        $report.definitionDefaultBranch = Get-AdoProbeField $repository 'defaultBranch'
        $report.yamlPath = Get-AdoProbeField $process 'yamlFilename'
        $repoGuid = [Guid]::Empty
        if ($report.adoRepoType -in @('TfsGit','azureReposGit') -and [Guid]::TryParse([string]$report.adoRepoId, [ref]$repoGuid)) {
            $filter = [Uri]::EscapeDataString($SourceRef.Substring('refs/'.Length))
            $refs = Get-AdoProbeJson "$base/_apis/git/repositories/$($repoGuid.ToString('D'))/refs?filter=$filter&api-version=7.1" $authorization
            $report.refsHttpStatus = $refs.Status; $report.refsFormat = $refs.Format
            if ($null -ne $refs.Json) {
                $values = $refs.Json.PSObject.Properties['value']
                if ($null -eq $values -or $values.Value -is [string]) { $report.refsFormat = 'unexpected-json' }
                else {
                    $exact = @($values.Value | Where-Object { (Get-AdoProbeField $_ 'name') -ceq $SourceRef })
                    $report.exactRefCount = $exact.Count
                    if ($exact.Count -eq 1) { $report.refTipCommit = Get-AdoProbeField $exact[0] 'objectId' }
                }
            }
        } else { $report.refsFormat = 'not-an-identified-azure-repos-git-repository' }
        $query = '/_apis/build/builds?definitions={0}&statusFilter=completed&resultFilter=succeeded&queryOrder=finishTimeDescending&$top=1&api-version=7.1' -f $PipelineId
        $success = Get-AdoProbeJson ($base + $query) $authorization
        $report.successRunsHttpStatus = $success.Status; $report.successRunsFormat = $success.Format
        $runs = @((Get-AdoProbeField $success.Json 'value') | Where-Object { $null -ne $_ })
        if ($runs.Count -gt 0) {
            $report.lastSuccessfulRunId = Get-AdoProbeField $runs[0] 'id'
            $report.lastSuccessfulRepoId = Get-AdoProbeField (Get-AdoProbeField $runs[0] 'repository') 'id'
            $report.lastSuccessfulAdoRef = Get-AdoProbeField $runs[0] 'sourceBranch'
            $report.lastSuccessfulAdoToolCommit = Get-AdoProbeField $runs[0] 'sourceVersion'
        }
        return [pscustomobject]$report
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        $plain = $null; $authorization = $null
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    if (-not $Pat) { $Pat = Read-Host 'ADO webhook trigger PAT (not GitLab token; do not paste into chat)' -AsSecureString }
    Get-AdoPipelineReferenceReport -ProjectUrl $ProjectUrl -PipelineId $PipelineId -SourceRef $SourceRef -Pat $Pat | ConvertTo-Json -Depth 4
}
