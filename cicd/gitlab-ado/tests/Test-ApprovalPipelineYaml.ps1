# Offline PS 5.1 checks that the approval YAML is the proven pipeline-5 YAML
# plus only a SHA run name and an approver-evidence tag step.
# The approval boundary itself is an ADO Environment check and is NOT testable here.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$package = Split-Path -Parent $PSScriptRoot
$mainYaml = [IO.File]::ReadAllText((Join-Path $package 'ado/azure-pipelines-gitlab-file-delivery.yml')).Replace("`r`n", "`n")
$approvalYaml = [IO.File]::ReadAllText((Join-Path $package 'ado/azure-pipelines-gitlab-file-delivery-approval.yml')).Replace("`r`n", "`n")
$count = 0
function Assert-Check($Value, [string]$Message) { if (-not $Value) { throw $Message }; $script:count++; Write-Host "PASS $Message" }

$stepPattern = '(?ms)^          - task: PowerShell@2\n            displayName: Tag run with ZIP SHA-256 for approvers\n.*?^                # END APPROVAL EVIDENCE\n            env:\n              EXPECTED_COMMIT_SHA: \$\{\{ parameters\.gitlabCommitSha \}\}\n'
$step = [regex]::Match($approvalYaml, $stepPattern)
Assert-Check $step.Success 'Approval YAML has exactly-delimited evidence step'

function Get-Normalized([string]$Text) {
    $Text = [regex]::Replace($Text, $stepPattern, '')
    $Text = [regex]::Replace($Text, '(?m)^name: .*\n', '')
    # Full-line YAML comments only; inline script lines starting with '#' are equal in both files.
    return [regex]::Replace($Text, '(?m)^[ ]*# (?!BEGIN |END ).*\n', '')
}
Assert-Check ((Get-Normalized $mainYaml) -ceq (Get-Normalized $approvalYaml)) 'Approval YAML equals pipeline-5 YAML apart from name, comments and evidence step'
Assert-Check ($approvalYaml -cmatch '(?m)^name: rayin-approval-\$\{\{ parameters\.gitlabCommitSha \}\}-\$\(Date:yyyyMMdd\)\$\(Rev:\.r\)$') 'Run name shows the requested GitLab SHA'
$packageAt = $approvalYaml.IndexOf('# END SOURCE PACKAGE INVOCATION')
$uploadAt = $approvalYaml.IndexOf('# BEGIN NATIVE BUILD ARTIFACT UPLOAD')
Assert-Check ($packageAt -lt $step.Index -and $step.Index -lt $uploadAt) 'Evidence step runs after packaging and before upload, in Package stage'
Assert-Check ($approvalYaml.IndexOf('- stage: Deliver') -gt $step.Index) 'Evidence step is not in Deliver stage'
Assert-Check ($approvalYaml -cmatch '(?m)^          name: test-deploy-agent\n          resourceName: SECSVR4-80\n          resourceType: virtualMachine$') 'Deliver still consumes Environment test-deploy-agent / SECSVR4-80'

$code = [regex]::Match($approvalYaml, '(?ms)^                # BEGIN APPROVAL EVIDENCE\n(?<code>.*?)^                # END APPROVAL EVIDENCE').Groups['code'].Value
$code = [regex]::Replace($code, '(?m)^                ', '')
$evidence = [scriptblock]::Create($code)
$root = Join-Path ([IO.Path]::GetTempPath()) ('approval evidence tests-' + [Guid]::NewGuid().ToString('N'))
$saved = @{ BUILD_ARTIFACTSTAGINGDIRECTORY = $env:BUILD_ARTIFACTSTAGINGDIRECTORY; EXPECTED_COMMIT_SHA = $env:EXPECTED_COMMIT_SHA }
function Write-Manifest([string]$Sha, [string]$Hash) {
    $manifest = [ordered]@{ gitlabCommitSha = $Sha; zipFileName = 'Rayin-7-x.zip'; zipSha256 = $Hash }
    [IO.File]::WriteAllText((Join-Path $root 'source-package\source-package.json'), ($manifest | ConvertTo-Json))
}
function Invoke-Evidence { try { return @{ Output = (& $evidence 6>&1 | Out-String); Error = $null } } catch { return @{ Output = ''; Error = $_.Exception.Message } } }
try {
    [IO.Directory]::CreateDirectory((Join-Path $root 'source-package')) | Out-Null
    $env:BUILD_ARTIFACTSTAGINGDIRECTORY = $root
    $sha = 'a' * 40; $hash = 'b' * 64
    $env:EXPECTED_COMMIT_SHA = $sha.ToUpperInvariant()
    Write-Manifest $sha $hash
    $result = Invoke-Evidence
    Assert-Check (-not $result.Error -and $result.Output -match [regex]::Escape("##vso[build.addbuildtag]zip-sha256-$hash")) 'Valid manifest emits ZIP SHA-256 build tag (SHA compare is case-insensitive)'

    Write-Manifest ('c' * 40) $hash
    $result = Invoke-Evidence
    Assert-Check ($result.Error -match 'differs' -and $result.Output -notmatch 'addbuildtag') 'Different manifest SHA fails without tagging'

    Write-Manifest $sha 'not-a-hash]'
    $result = Invoke-Evidence
    Assert-Check ($result.Error -match 'no valid ZIP SHA-256' -and $result.Output -notmatch 'addbuildtag') 'Invalid hash (logging-command injection) fails without tagging'

    Remove-Item -LiteralPath (Join-Path $root 'source-package\source-package.json')
    $result = Invoke-Evidence
    Assert-Check ($result.Error -and $result.Output -notmatch 'addbuildtag') 'Missing manifest fails without tagging'
} finally {
    foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name, $saved[$name]) }
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
}
Write-Host "Approval pipeline YAML checks passed: $count"
