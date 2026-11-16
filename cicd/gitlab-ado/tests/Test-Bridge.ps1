# Offline integration tests; run with powershell -NoProfile -File <absolute-path>/Test-Bridge.ps1.
# No Pester dependency. Import HTTP/sleep are fake; notifier HTTP uses loopback only.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$package = Split-Path -Parent $PSScriptRoot
$generator = Join-Path $package 'gitlab/ci/New-ReleaseCandidate.ps1'
$sender = Join-Path $package 'gitlab/ci/Send-AdoCandidate.ps1'
$root = Join-Path ([IO.Path]::GetTempPath()) ('bridge-tests-' + [Guid]::NewGuid().ToString('N'))
$sha = '0123456789abcdef0123456789abcdef01234567'
$cdSha = 'abcdef0123456789abcdef0123456789abcdef01'
$failures = New-Object 'Collections.Generic.List[string]'
$count = 0
$fakeEnv = @{
    CI_PROJECT_ID='123'; CI_PROJECT_PATH='group/application'; CI_PIPELINE_ID='456'; CI_PIPELINE_IID='7'
    CI_JOB_ID='789'; CI_COMMIT_SHA=$sha; CI_COMMIT_BRANCH='main'; CI_COMMIT_TAG=$null
    ADO_COLLECTION_URL='http://127.0.0.1:1/collection'; ADO_PROJECT='Import Project'; ADO_PIPELINE_ID='10'
    ADO_CD_COMMIT=$cdSha; ADO_QUEUE_PAT='offline-queue-token'; ADO_ALLOW_INSECURE_HTTP='true'
    GITLAB_READ_TOKEN='offline-read-token'; BUILD_BUILDID='1001'; BUILD_SOURCEVERSION=$cdSha
    GITLAB_PROJECT_ID=$null; GITLAB_RELEASE_ID=$null; GITLAB_ZIP_SHA256=$null
    GITLAB_PIPELINE_ID='456'; GITLAB_JOB_ID='789'; GITLAB_COMMIT_SHA=$sha
}
$savedEnv = @{}
foreach ($key in $fakeEnv.Keys) { $savedEnv[$key] = [Environment]::GetEnvironmentVariable($key) }
$savedTls = [Net.ServicePointManager]::SecurityProtocol
$savedProxy = [Net.WebRequest]::DefaultWebProxy
function Assert-Test($Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Put-Json($Value, $Path) { [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 12), (New-Object Text.UTF8Encoding($false))) }
function Read-Json($Path) { Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json }
function Case([string]$Name, [scriptblock]$Body) {
    $script:count++
    foreach ($key in $fakeEnv.Keys) { [Environment]::SetEnvironmentVariable($key, $fakeEnv[$key]) }
    try { & $Body; Write-Host "PASS $Name" }
    catch { $script:failures.Add("${Name}: $($_.Exception.Message) [line $($_.InvocationInfo.ScriptLineNumber)]"); Write-Host "FAIL $($script:failures[-1])" }
}
function Set-FixtureZip($f, [string[]]$Names = @('release.json','index.html'), [int]$Attributes = 0) {
    if (Test-Path -LiteralPath $f.Zip) { [IO.File]::Delete($f.Zip) }
    $zip = [IO.Compression.ZipFile]::Open($f.Zip, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($name in $Names) {
            $entry = $zip.CreateEntry($name); $entry.ExternalAttributes = $Attributes
            $writer = New-Object IO.StreamWriter($entry.Open(), (New-Object Text.UTF8Encoding($false)))
            try { if ($name -ceq 'release.json') { $writer.Write(($f.Marker | ConvertTo-Json -Compress)) } else { $writer.Write('offline payload') } }
            finally { $writer.Dispose() }
        }
    } finally { $zip.Dispose() }
    $f.Manifest.zipSha256 = (Get-FileHash -LiteralPath $f.Zip -Algorithm SHA256).Hash.ToLowerInvariant()
    $f.Manifest.zipBytes = (Get-Item -LiteralPath $f.Zip).Length
}
function New-Fixture {
    $dir = Join-Path $root ([Guid]::NewGuid().ToString('N')); [IO.Directory]::CreateDirectory($dir) | Out-Null
    $policy = Read-Json (Join-Path $package 'ado/import-policy.example.json')
    $policy.gitlabBaseUrl='https://gitlab.invalid'; $policy.waitForPipelineSeconds=1; $policy.pollIntervalSeconds=1
    $policy.requiredJobs = @($policy.requiredJobs) + @([pscustomobject]@{name='tests';stage='test'})
    $f = [pscustomobject]@{
        Dir=$dir; Output=(Join-Path $dir 'release'); PolicyPath=(Join-Path $dir 'policy.json'); Policy=$policy
        Zip=(Join-Path $dir 'site.zip'); ManifestPath=(Join-Path $dir 'manifest.json'); Input=(Join-Path $dir 'input'); PackageOut=(Join-Path $dir 'out')
        Manifest=[pscustomobject]@{schema=1;releaseId='r7-01234567';projectId=123;projectPath='group/application';pipelineId=456;jobId=789;commitSha=$sha;ref='main';zipName='site.zip';zipSha256='';zipBytes=0}
        Marker=[pscustomobject]@{releaseId='r7-01234567';commitSha=$sha;projectId=123;pipelineId=456;jobId=789}
        Project=[pscustomobject]@{id=123;path_with_namespace='group/application'}
        Pipeline=[pscustomobject]@{id=456;iid=7;project_id=123;sha=$sha;ref='main';source='push';status='success'}
        Jobs=@(); Job=$null; Statuses=@('success'); PipelineReads=0; Sleeps=0; Timeout=$false; FailArtifact=''; RawManifest=$null
        Calls=(New-Object 'Collections.Generic.List[string]'); PipelineId='456'; JobId='789'; CommitSha=$sha; Extra=@{}
    }
    foreach ($spec in @(@(789,'package','build'),@(790,'notify_ado','notify'),@(791,'tests','test'))) {
        $f.Jobs += [pscustomobject]@{id=$spec[0];name=$spec[1];stage=$spec[2];status='success';allow_failure=$false;tag=$false;ref='main';pipeline=[pscustomobject]@{id=456};commit=[pscustomobject]@{id=$sha}}
    }
    $f.Job = $f.Jobs[0] | ConvertTo-Json -Depth 8 | ConvertFrom-Json
    [IO.Directory]::CreateDirectory($f.Input) | Out-Null; [IO.File]::WriteAllText((Join-Path $f.Input 'index.html'), 'offline payload')
    Set-FixtureZip $f
    return $f
}
function Save-Fixture($f) {
    Put-Json $f.Policy $f.PolicyPath
    if ($null -ne $f.RawManifest) { [IO.File]::WriteAllText($f.ManifestPath, $f.RawManifest) } else { Put-Json $f.Manifest $f.ManifestPath }
}
function Import-Fixture($f) {
    Save-Fixture $f; $script:mock=$f
    $extra=$f.Extra
    Invoke-GitLabCandidateImport -PolicyPath $f.PolicyPath -PipelineId $f.PipelineId -JobId $f.JobId -CommitSha $f.CommitSha -OutputDirectory $f.Output @extra
}
function Assert-NoPublishedFailure($f) {
    Assert-Test (-not (Test-Path -LiteralPath $f.Output)) 'Rejected import published a release directory.'
    Assert-Test (@(Get-ChildItem -LiteralPath $f.Dir -Force -Filter '.candidate-*').Count -eq 0) 'Rejected import leaked temporary candidate files.'
}
function Reject-Import([string]$Name, [scriptblock]$Change, [string]$Pattern) {
    Case $Name {
        $f=New-Fixture; & $Change $f; $errorText=$null
        try { Import-Fixture $f } catch { $errorText=$_.Exception.Message }
        Assert-NoPublishedFailure $f
        Assert-Test ($null -ne $errorText) 'Import unexpectedly accepted an invalid candidate.'
        Assert-Test ($errorText -match $Pattern) "Wrong rejection: $errorText"
    }
}
function Reject-Package([string]$Name, [scriptblock]$Change, [string]$Pattern) {
    Case $Name {
        $f=New-Fixture; & $Change $f; $errorText=$null
        try { & $generator -InputDirectory $f.Input -OutputDirectory $f.PackageOut } catch { $errorText=$_.Exception.Message }
        Assert-Test ($null -ne $errorText -and $errorText -match $Pattern) "Wrong/missing packaging rejection: $errorText"
        Assert-Test (-not (Test-Path (Join-Path $f.PackageOut 'manifest.json'))) 'Invalid package published a manifest.'
    }
}
function Send-Loopback($f, [int]$Status = 200, [string]$Response = '{"id":42,"pipeline":{"id":10}}', [string]$ReceiptPath = '') {
    Save-Fixture $f
    $probe=New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback,0); $probe.Start(); $port=$probe.LocalEndpoint.Port; $probe.Stop()
    $listener=New-Object Net.HttpListener; $listener.Prefixes.Add("http://127.0.0.1:$port/")
    $worker=[PowerShell]::Create(); $receipt=if ($ReceiptPath) { $ReceiptPath } else { Join-Path $f.Dir 'receipt.json' }; $errorText=$null
    try {
        $listener.Start()
        [void]$worker.AddScript({ param($server,$status,$body)
            $context=$server.GetContext(); $reader=New-Object IO.StreamReader($context.Request.InputStream)
            try { $text=$reader.ReadToEnd() } finally { $reader.Dispose() }
            $request=[pscustomobject]@{Method=$context.Request.HttpMethod;Url=$context.Request.RawUrl;Body=$text;Auth=$context.Request.Headers['Authorization']}
            $bytes=[Text.Encoding]::UTF8.GetBytes($body); $context.Response.StatusCode=$status
            if ($status -eq 302) { $context.Response.RedirectLocation='http://127.0.0.1:1/never-follow' }
            $context.Response.ContentType='application/json'; $context.Response.ContentLength64=$bytes.Length
            $context.Response.OutputStream.Write($bytes,0,$bytes.Length); $context.Response.Close(); $request
        }).AddArgument($listener).AddArgument($Status).AddArgument($Response)
        $async=$worker.BeginInvoke(); $env:ADO_COLLECTION_URL="http://127.0.0.1:$port/collection"
        try { & $sender -ManifestPath $f.ManifestPath -ReceiptPath $receipt } catch { $errorText=$_.Exception.Message }
        Assert-Test ($async.AsyncWaitHandle.WaitOne(5000)) "Notifier did not reach loopback server: $errorText"
        $requests=@($worker.EndInvoke($async)); Assert-Test ($requests.Count -eq 1) 'Expected exactly one queue POST.'
        return [pscustomobject]@{Request=$requests[0];Error=$errorText;Receipt=$ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($receipt)}
    } finally { $listener.Stop(); $listener.Close(); $worker.Stop(); $worker.Dispose() }
}
try {
    [IO.Directory]::CreateDirectory($root) | Out-Null; Add-Type -AssemblyName System.IO.Compression; Add-Type -AssemblyName System.IO.Compression.FileSystem
    [Net.WebRequest]::DefaultWebProxy=$null
    . (Join-Path $package 'ado/scripts/Import-GitLabCandidate.ps1')
    # Override AFTER dot-sourcing. Unknown URLs fail rather than falling through to real HTTP.
    function Invoke-BridgeHttp {
        param([string]$Uri,[string]$Method='GET',[hashtable]$Headers=@{},[string]$Body,[string]$OutFile,[long]$MaxBytes=4194304)
        $f=$script:mock; $api='https://gitlab.invalid/api/v4/projects/123'; $f.Calls.Add($Uri)
        Assert-Test ($Method -eq 'GET' -and $Headers['PRIVATE-TOKEN'] -ceq 'offline-read-token') 'Unexpected import HTTP method/credentials.'
        if ($Uri -ceq $api) { return $f.Project }
        if ($Uri -ceq "$api/pipelines/456") { $f.Pipeline.status=$f.Statuses[[Math]::Min($f.PipelineReads,$f.Statuses.Count-1)]; $f.PipelineReads++; return $f.Pipeline }
        if ($Uri -match ('^'+[regex]::Escape($api)+'/pipelines/456/jobs\?include_retried=false&per_page=100&page=([1-9][0-9]*)$')) {
            return @($f.Jobs | Select-Object -Skip (([int]$Matches[1]-1)*100) -First 100)
        }
        if ($Uri -ceq "$api/jobs/789") { return $f.Job }
        if ($Uri -ceq "$api/jobs/789/artifacts/out/manifest.json") { $source=$f.ManifestPath }
        elseif ($Uri -ceq "$api/jobs/789/artifacts/out/site.zip") { $source=$f.Zip }
        else { throw 'Unmocked endpoint: external network is disabled in these tests.' }
        if ($f.FailArtifact -and $Uri.EndsWith($f.FailArtifact)) { throw 'Fake HTTP 404/500: artifact unavailable.' }
        Assert-Test ([bool]$OutFile) 'Artifact request must use bounded file download.'
        if ((Get-Item -LiteralPath $source).Length -gt $MaxBytes) { throw 'Fake HTTP response exceeds configured size limit.' }
        [IO.File]::Copy($source,$OutFile)
    }
    function Start-Sleep {
        param([int]$Seconds)
        $script:mock.Sleeps++; Assert-Test ($script:mock.Sleeps -lt 10) 'Unexpected endless pipeline polling.'
        if ($script:mock.Timeout) { [Threading.Thread]::Sleep(1100) } # Allow the real 1s deadline to elapse, once.
    }

    Case 'generator preserves exact archive contract and adds root marker without modifying input' {
        $f=New-Fixture; $sourceFile=Join-Path $f.Input 'index.html'; $inputHash=(Get-FileHash $sourceFile).Hash
        & $generator -InputDirectory $f.Input -OutputDirectory $f.PackageOut
        $m=Read-Json (Join-Path $f.PackageOut 'manifest.json'); $zipPath=Join-Path $f.PackageOut 'site.zip'
        $fields='schema,releaseId,projectId,projectPath,pipelineId,jobId,commitSha,ref,zipName,zipSha256,zipBytes'.Split(',')
        Assert-Test ((@($m.PSObject.Properties.Name | Sort-Object)-join ',') -ceq (($fields | Sort-Object)-join ',')) 'Manifest contract fields changed.'
        Assert-Test ($m.schema -eq 1 -and $m.releaseId -ceq 'r7-01234567' -and $m.projectId -eq 123 -and $m.pipelineId -eq 456 -and $m.jobId -eq 789 -and $m.projectPath -ceq 'group/application' -and $m.commitSha -ceq $sha -and $m.ref -ceq 'main' -and $m.zipName -ceq 'site.zip') 'Incorrect manifest provenance.'
        Assert-Test ($m.zipSha256 -ceq (Get-FileHash $zipPath -Algorithm SHA256).Hash.ToLowerInvariant() -and $m.zipBytes -eq (Get-Item $zipPath).Length) 'Manifest does not describe actual ZIP.'
        $zip=[IO.Compression.ZipFile]::OpenRead($zipPath)
        try {
            Assert-Test ($null -ne $zip.GetEntry('index.html')) 'Package unexpectedly added a top-level directory.'
            $reader=New-Object IO.StreamReader($zip.GetEntry('release.json').Open())
            try { $marker=$reader.ReadToEnd() | ConvertFrom-Json } finally { $reader.Dispose() }
            Assert-Test ($marker.releaseId -ceq 'r7-01234567' -and $marker.commitSha -ceq $sha -and $marker.projectId -eq 123 -and $marker.pipelineId -eq 456 -and $marker.jobId -eq 789) 'Wrong root marker.'
        } finally { $zip.Dispose() }
        Assert-Test ((Get-FileHash $sourceFile).Hash -ceq $inputHash -and -not (Test-Path (Join-Path $f.Input 'release.json'))) 'Generator changed build input.'
        Assert-Test (@(Get-ChildItem $f.PackageOut -Force -Filter '.package-*').Count -eq 0) 'Packaging temp files leaked.'
        # Exercise the importer with ACTUAL generator output, not merely hand-built fixtures.
        Copy-Item $zipPath $f.Zip -Force; $f.Manifest=$m; Import-Fixture $f
        Assert-Test (Test-Path (Join-Path $f.Output 'verification.json')) 'Generated package cannot be imported.'
    }
    Reject-Package 'generator rejects reserved input release.json' { param($f) [IO.File]::WriteAllText((Join-Path $f.Input 'release.json'),'business file') } 'reserved'
    Reject-Package 'generator rejects empty input' { param($f) Remove-Item (Join-Path $f.Input 'index.html') } 'empty'
    Reject-Package 'generator rejects output inside input' { param($f) $f.PackageOut=Join-Path $f.Input 'out' } 'outside'
    Reject-Package 'generator rejects tag pipeline' { param($f) $env:CI_COMMIT_TAG='v1' } 'branch'
    Reject-Package 'generator rejects missing project path' { param($f) $env:CI_PROJECT_PATH=$null } 'CI_PROJECT_PATH'
    Reject-Package 'generator rejects invalid pipeline IID' { param($f) $env:CI_PIPELINE_IID='0' } 'positive decimal'
    Reject-Package 'generator rejects abbreviated SHA' { param($f) $env:CI_COMMIT_SHA='01234567' } '40-character'

    Case 'relative package, import and queue receipt paths follow Set-Location rather than process cwd' {
        $f=New-Fixture; Push-Location $f.Dir
        try {
            & $generator -InputDirectory './input' -OutputDirectory './out'
            Assert-Test (Test-Path (Join-Path $f.PackageOut 'manifest.json')) 'Relative package output used process cwd.'
            $f.Manifest=Read-Json (Join-Path $f.PackageOut 'manifest.json'); Copy-Item (Join-Path $f.PackageOut 'site.zip') $f.Zip -Force
            Save-Fixture $f; $script:mock=$f
            Invoke-GitLabCandidateImport -PolicyPath './policy.json' -PipelineId '456' -JobId '789' -CommitSha $sha -OutputDirectory './release'
            Assert-Test (Test-Path (Join-Path $f.Output 'verification.json')) 'Relative import output used process cwd.'
            $sent=Send-Loopback $f -ReceiptPath './out/bridge-receipt.json'
            Assert-Test ($null -eq $sent.Error -and (Test-Path (Join-Path $f.PackageOut 'bridge-receipt.json'))) 'Relative receipt used process cwd.'
        } finally { Pop-Location }
    }
    Case 'import success stores only ZIP, manifest and auditable verification; never extracts/executes' {
        $f=New-Fixture; Import-Fixture $f; $v=Read-Json (Join-Path $f.Output 'verification.json')
        Assert-Test ((@(Get-ChildItem $f.Output | Sort-Object Name | ForEach-Object Name)-join ',') -ceq 'manifest.json,site.zip,verification.json') 'Importer extracted or published unexpected files.'
        Assert-Test ($v.candidate_id -ceq '123-456-789' -and $v.release_id -ceq 'r7-01234567' -and $v.sha -ceq $sha -and $v.pipeline_status_at_verification -ceq 'success' -and $v.ado_build_id -ceq '1001' -and $v.ado_cd_commit -ceq $cdSha) 'Invalid verification audit record.'
        Assert-Test ($v.policy_sha256 -ceq (Get-FileHash $f.PolicyPath -Algorithm SHA256).Hash.ToLowerInvariant() -and $v.sha256 -ceq $f.Manifest.zipSha256) 'Audit hashes do not bind policy and package.'
        Assert-Test ((Get-FileHash (Join-Path $f.Output 'site.zip')).Hash -ceq (Get-FileHash $f.Zip).Hash) 'Import changed original package bytes.'
    }
    Case 'import waits for running pipeline to succeed' {
        $f=New-Fixture; $f.Statuses=@('running','success'); Import-Fixture $f
        Assert-Test ($f.PipelineReads -eq 2 -and $f.Sleeps -eq 1 -and (Test-Path $f.Output)) 'Did not wait for terminal success.'
    }
    Case 'import paginates current jobs before accepting required jobs on page two' {
        $f=New-Fixture; $required=$f.Jobs; $f.Jobs=@(1..100 | ForEach-Object { [pscustomobject]@{name="other$_";stage='other'} }) + $required
        Import-Fixture $f; Assert-Test (@($f.Calls | Where-Object { $_ -match 'page=2$' }).Count -eq 1) 'Required jobs on page two were not verified.'
    }
    Reject-Import 'reject wrong pipeline source' { param($f) $f.Pipeline.source='web' } 'identity/source/ref/SHA'
    Reject-Import 'reject wrong pipeline ref' { param($f) $f.Pipeline.ref='feature' } 'identity/source/ref/SHA'
    Reject-Import 'reject wrong pipeline SHA' { param($f) $f.Pipeline.sha=('f'*40) } 'identity/source/ref/SHA'
    Reject-Import 'reject wrong pipeline ID' { param($f) $f.Pipeline.id=999 } 'identity/source/ref/SHA'
    Reject-Import 'reject wrong pipeline project' { param($f) $f.Pipeline.project_id=999 } 'identity/source/ref/SHA'
    Reject-Import 'reject wrong project identity' { param($f) $f.Project.id=999 } 'project identity'
    Reject-Import 'reject wrong project path' { param($f) $f.Project.path_with_namespace='attacker/application' } 'project identity'
    foreach ($status in @('failed','canceled','skipped')) { Reject-Import "reject $status pipeline" { param($f) $f.Statuses=@($status) } 'did not succeed' }
    Reject-Import 'reject pipeline running then canceled' { param($f) $f.Statuses=@('running','canceled') } 'did not succeed'
    Reject-Import 'reject always-running pipeline after bounded timeout' { param($f) $f.Statuses=@('running'); $f.Timeout=$true } 'Timed out waiting'
    Reject-Import 'reject invalid pipeline argument' { param($f) $f.PipelineId='0' } 'positive decimal'
    Reject-Import 'reject invalid job argument' { param($f) $f.JobId='../789' } 'positive decimal'
    Reject-Import 'reject invalid SHA argument' { param($f) $f.CommitSha='deadbeef' } '40-character'
    Reject-Import 'reject wrong requested job ID' { param($f) $f.JobId='788' } 'current package job'
    Reject-Import 'reject outdated retried package job' { param($f) $f.Jobs[0].id=799 } 'current package job'
    Reject-Import 'reject failed required job despite successful pipeline' { param($f) $f.Jobs[2].status='failed' } 'blocking branch job'
    Reject-Import 'reject canceled required job despite successful pipeline' { param($f) $f.Jobs[2].status='canceled' } 'blocking branch job'
    Reject-Import 'reject allow_failure required job' { param($f) $f.Jobs[2].allow_failure=$true } 'blocking branch job'
    Reject-Import 'reject missing required job' { param($f) $f.Jobs=@($f.Jobs[0],$f.Jobs[1]) } 'Missing or ambiguous'
    Reject-Import 'reject duplicate required job' { param($f) $f.Jobs+=@($f.Jobs[2]) } 'Missing or ambiguous'
    Reject-Import 'reject package detail with wrong ID' { param($f) $f.Job.id=999 } 'job identity'
    Reject-Import 'reject package detail with wrong pipeline' { param($f) $f.Job.pipeline.id=999 } 'blocking branch job'
    Reject-Import 'reject package detail with wrong SHA' { param($f) $f.Job.commit.id=('f'*40) } 'blocking branch job'
    Reject-Import 'reject package detail with tag' { param($f) $f.Job.tag=$true } 'blocking branch job'
    Reject-Import 'reject failed package detail' { param($f) $f.Job.status='failed' } 'blocking branch job'
    Reject-Import 'reject nonblocking package detail' { param($f) $f.Job.allow_failure=$true } 'blocking branch job'
    foreach ($field in @('schema','releaseId','projectId','projectPath','pipelineId','jobId','commitSha','ref','zipName')) {
        Reject-Import "reject incorrect manifest $field" { param($f) $f.Manifest.$field=if ($field -eq 'schema') { 2 } else { 'wrong' } } 'Manifest schema/provenance'
    }
    Reject-Import 'reject malformed manifest JSON' { param($f) $f.RawManifest='{broken' } 'JSON|Invalid object|Invalid.*passed'
    Reject-Import 'reject incorrect package hash' { param($f) $f.Manifest.zipSha256=('0'*64) } 'size/SHA-256'
    Reject-Import 'reject malformed package hash' { param($f) $f.Manifest.zipSha256='bad' } 'Manifest schema/provenance'
    Reject-Import 'reject incorrect package size' { param($f) $f.Manifest.zipBytes++ } 'size/SHA-256'
    Reject-Import 'reject package size over policy' { param($f) $f.Policy.maxPackageBytes=1 } 'package size'
    Reject-Import 'reject missing manifest artifact / HTTP error' { param($f) $f.FailArtifact='manifest.json' } 'Fake HTTP 404/500'
    Reject-Import 'reject missing ZIP artifact / HTTP error' { param($f) $f.FailArtifact='site.zip' } 'Fake HTTP 404/500'
    Reject-Import 'reject notification project mismatch' { param($f) $f.Extra=@{ExpectedProjectId='999'} } 'policy project'
    Reject-Import 'reject notification release mismatch' { param($f) $f.Extra=@{ExpectedReleaseId='r8-01234567'} } 'Notification.*disagree'
    Reject-Import 'reject notification hash mismatch' { param($f) $f.Extra=@{ExpectedZipSha256=('0'*64)} } 'Notification.*disagree'
    foreach ($unsafePath in @('../escape.txt','folder/../../escape.txt','folder\..\escape.txt','/absolute.txt','C:\absolute.txt','file:stream','CON.txt','dir/NUL','trailing.','trailing ','a//b','bad?.txt')) {
        Reject-Import "reject unsafe ZIP path $unsafePath" { param($f) Set-FixtureZip $f @('release.json',$unsafePath) } 'Unsafe.*ZIP path'
    }
    Reject-Import 'reject duplicate ZIP entries' { param($f) Set-FixtureZip $f @('release.json','index.html','index.html') } 'Duplicate|collid'
    Reject-Import 'reject case-colliding ZIP entries' { param($f) Set-FixtureZip $f @('release.json','index.html','INDEX.HTML') } 'Duplicate|collid'
    Reject-Import 'reject ZIP file/directory ancestor collision' { param($f) Set-FixtureZip $f @('release.json','ASSETS','assets/file.txt') } 'collision'
    Reject-Import 'reject ZIP symlink' { param($f) Set-FixtureZip $f @('release.json','link') -Attributes 0xA1FF0000 } 'Non-regular|symlink'
    Reject-Import 'reject ZIP reparse-point attribute' { param($f) Set-FixtureZip $f @('release.json','link') -Attributes 0x400 } 'reparse-point'
    Reject-Import 'reject oversized expanded ZIP' { param($f) $f.Policy.maxExpandedBytes=1 } 'Expanded ZIP size'
    Reject-Import 'reject excessive ZIP entry count' { param($f) $f.Policy.maxZipEntries=1 } 'too many ZIP entries'
    Reject-Import 'reject empty ZIP' { param($f) Set-FixtureZip $f @() } 'Empty ZIP'
    Reject-Import 'reject corrupt ZIP with correct transport hash' { param($f) [IO.File]::WriteAllText($f.Zip,'not a zip'); $f.Manifest.zipBytes=9; $f.Manifest.zipSha256=(Get-FileHash $f.Zip).Hash } 'End of Central|archive|ZIP|directory'
    Reject-Import 'reject absent root release.json' { param($f) Set-FixtureZip $f @('nested/release.json','index.html') } 'root release.json'
    foreach ($field in @('releaseId','commitSha','projectId','pipelineId','jobId')) {
        Reject-Import "reject wrong root release.json $field" { param($f) $f.Marker.$field='wrong'; Set-FixtureZip $f } 'release.json provenance'
    }
    Reject-Import 'reject oversized root release.json' { param($f) $f.Marker.releaseId=('x'*65537); Set-FixtureZip $f } 'oversized root release.json'

    Case 'notifier POST pins CD commit, sends six archive-contract parameters and writes queue receipt only' {
        $f=New-Fixture; $sent=Send-Loopback $f; Assert-Test ($null -eq $sent.Error) "Notifier failed: $($sent.Error)"
        Assert-Test ($sent.Request.Method -ceq 'POST' -and $sent.Request.Url -ceq '/collection/Import%20Project/_apis/pipelines/10/runs?api-version=7.0') 'Wrong queue method/endpoint.'
        Assert-Test ($sent.Request.Auth -ceq ('Basic '+[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(':offline-queue-token')))) 'Wrong queue auth.'
        $body=$sent.Request.Body | ConvertFrom-Json; $p=$body.templateParameters
        Assert-Test ((($p.PSObject.Properties.Name | Sort-Object)-join ',') -ceq 'commitSha,gitlabJobId,gitlabPipelineId,gitlabProjectId,releaseId,zipSha256') 'Wrong queue parameter contract.'
        Assert-Test ($p.gitlabProjectId -ceq '123' -and $p.gitlabPipelineId -ceq '456' -and $p.gitlabJobId -ceq '789' -and $p.commitSha -ceq $sha -and $p.releaseId -ceq 'r7-01234567' -and $p.zipSha256 -ceq $f.Manifest.zipSha256) 'Wrong queue provenance.'
        Assert-Test ($body.resources.repositories.self.version -ceq $cdSha -and $body.resources.repositories.self.refName -ceq 'refs/heads/main') 'CD repository commit is not pinned.'
        $receipt=Read-Json $sent.Receipt; Assert-Test ($receipt.ado_run_id -ceq '42' -and $receipt.gitlab_job_id -ceq '789' -and $receipt.ado_cd_commit -ceq $cdSha) 'Incorrect queue receipt.'
        Assert-Test (([IO.File]::ReadAllText($sent.Receipt)+$sent.Request.Body) -notmatch 'offline-(queue|read)-token') 'Token leaked to payload/receipt.'
        Assert-Test (-not (Test-Path $f.Output)) 'Notifier published an imported release.'
    }
    foreach ($status in @(401,500,302)) {
        Case "notifier rejects HTTP $status without receipt" {
            $f=New-Fixture; $sent=Send-Loopback $f $status
            Assert-Test ($sent.Error -match 'no automatic POST retry') 'Queue failure was not reported as unknown/no-retry outcome.'
            Assert-Test (-not (Test-Path $sent.Receipt)) 'Failed queue request wrote a receipt.'
        }
    }
    Case 'notifier rejects response for wrong ADO pipeline' {
        $f=New-Fixture; $sent=Send-Loopback $f 200 '{"id":42,"pipeline":{"id":99}}'
        Assert-Test ($sent.Error -match 'pipeline mismatch') 'Wrong returned ADO pipeline accepted.'
        Assert-Test (-not (Test-Path $sent.Receipt)) 'Wrong returned pipeline wrote receipt.'
    }
    Case 'notifier rejects invalid ADO run ID without receipt' {
        $f=New-Fixture; $sent=Send-Loopback $f 200 '{"id":0}'
        Assert-Test ($sent.Error -match 'ADO run ID') 'Invalid returned run ID accepted.'
        Assert-Test (-not (Test-Path $sent.Receipt)) 'Invalid run ID wrote receipt.'
    }
    Case 'notifier rejects manifest from another pipeline before queueing' {
        $f=New-Fixture; $f.Manifest.pipelineId=999; Save-Fixture $f; $errorText=$null; $receipt=Join-Path $f.Dir 'receipt.json'
        try { & $sender -ManifestPath $f.ManifestPath -ReceiptPath $receipt } catch { $errorText=$_.Exception.Message }
        Assert-Test ($errorText -match 'does not belong') 'Mismatched manifest was not rejected locally.'
        Assert-Test (-not (Test-Path $receipt)) 'Invalid manifest wrote receipt.'
    }
    Case 'consumer accepts explicitly selected imported candidate without changing artifact bytes' {
        $f=New-Fixture; Import-Fixture $f; $hashBefore=(Get-FileHash (Join-Path $f.Output 'site.zip')).Hash
        & (Join-Path $package 'ado/scripts/Test-ImportedCandidate.ps1') -ArtifactDirectory $f.Output -ExpectedImportBuildId '1001' -ExpectedProjectId '123' -ExpectedRef 'main' -ExpectedCandidateId '123-456-789' -ExpectedReleaseId 'r7-01234567'
        Assert-Test ((Get-FileHash (Join-Path $f.Output 'site.zip')).Hash -ceq $hashBefore) 'Consumer changed imported ZIP.'
    }
    foreach ($consumerFault in @('build','candidate','hash')) {
        Case "consumer rejects wrong expected $consumerFault" {
            $f=New-Fixture; Import-Fixture $f; $build='1001'; $candidate='123-456-789'
            if ($consumerFault -eq 'build') { $build='1002' }
            if ($consumerFault -eq 'candidate') { $candidate='123-456-799' }
            if ($consumerFault -eq 'hash') { $v=Read-Json (Join-Path $f.Output 'verification.json'); $v.sha256=('0'*64); Put-Json $v (Join-Path $f.Output 'verification.json') }
            $errorText=$null
            try { & (Join-Path $package 'ado/scripts/Test-ImportedCandidate.ps1') -ArtifactDirectory $f.Output -ExpectedImportBuildId $build -ExpectedProjectId '123' -ExpectedRef 'main' -ExpectedCandidateId $candidate -ExpectedReleaseId 'r7-01234567' } catch { $errorText=$_.Exception.Message }
            Assert-Test ($errorText -match 'authorization subject|hash/length mismatch') 'Consumer accepted inconsistent authorization subject/hash.'
        }
    }
    Case 'ADO YAML is import-only with triggers off and server Build Artifact publication' {
        $yaml=[IO.File]::ReadAllText((Join-Path $package 'ado/azure-pipelines-import.yml'))
        Assert-Test ($yaml -match '(?m)^trigger: none\s*$' -and $yaml -match '(?m)^pr: none\s*$') 'Automatic ADO trigger enabled.'
        Assert-Test ($yaml -match 'PublishBuildArtifacts@1' -and $yaml -match 'Import-GitLabCandidate.ps1') 'Missing import/Server publication steps.'
        Assert-Test ($yaml -notmatch '(?im)^\s*(-\s*)?(deployment:|environment:|strategy:|runOnce:)|DownloadSecureFile|AzureCLI|IISWebAppDeployment|WinRM|SSH@') 'Deployment primitive present in import YAML.'
    }
} finally {
    foreach ($key in $savedEnv.Keys) { [Environment]::SetEnvironmentVariable($key,$savedEnv[$key]) }
    [Net.ServicePointManager]::SecurityProtocol=$savedTls; [Net.WebRequest]::DefaultWebProxy=$savedProxy
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
}
Write-Host ("Tests: {0} passed; {1} failed; {2} total." -f ($count-$failures.Count),$failures.Count,$count)
if ($failures.Count) { throw ($failures -join [Environment]::NewLine) }
