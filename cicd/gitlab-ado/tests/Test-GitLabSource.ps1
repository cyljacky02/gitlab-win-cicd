# Offline Windows PowerShell 5.1 tests. Fake credentials/local Git only; no remote HTTP.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$package = Split-Path -Parent $PSScriptRoot
. (Join-Path $package 'ado/scripts/Get-GitLabSource.ps1')
$nativeGit = ${function:Invoke-SourceGit}
$gitPath = (Get-Command git.exe).Source
$root = Join-Path ([IO.Path]::GetTempPath()) ('gitlab source tests-' + [Guid]::NewGuid().ToString('N'))
$fixture = Join-Path $root 'fixture'
$count = 0; $failures = New-Object 'Collections.Generic.List[string]'
$envNames = @('GITLAB_GIT_USERNAME','GITLAB_GIT_TOKEN','BUILD_BUILDID','BUILD_SOURCEVERSION')
$saved = @{}; foreach ($name in $envNames) { $saved[$name] = [Environment]::GetEnvironmentVariable($name) }
$repoUrl = 'https://gitlab.invalid/group/application.git'
function Assert-Test($Value, [string]$Message) { if (-not $Value) { throw $Message } }
function Local-Git([string[]]$Args_) {
    $result = & $gitPath -C $fixture @Args_ 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'Local Git fixture setup failed.' }
    return ($result -join "`n").Trim()
}
function Case([string]$Name, [scriptblock]$Body) {
    $script:count++
    $env:GITLAB_GIT_USERNAME = 'offline-user'; $env:GITLAB_GIT_TOKEN = 'offline-token'
    $env:BUILD_BUILDID = '123'; $env:BUILD_SOURCEVERSION = ('b' * 40)
    $script:failFetch = $false; $script:failProbe = $false; $script:wrongProbe = $false; $script:failAncestry = $false; $script:wrongHead = $false
    $script:calls = New-Object 'Collections.Generic.List[object]'
    $script:caseDir = Join-Path $root ([Guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($script:caseDir) | Out-Null
    try { & $Body; Write-Host "PASS $Name" }
    catch { $script:failures.Add("${Name}: $($_.Exception.Message)"); Write-Host "FAIL $Name" }
}
function Checkout-Args {
    return @{RepositoryUrl=$repoUrl;SourceRef='refs/heads/main';CommitSha=$script:firstSha;OutputDirectory=(Join-Path $script:caseDir 'source');EvidenceDirectory=(Join-Path $script:caseDir 'evidence')}
}
function Reject([string]$Name,[scriptblock]$Change,[string]$Pattern,[switch]$BeforeFetch) {
    Case $Name {
        $params = Checkout-Args; & $Change $params; $message = $null
        try { Get-GitLabSource @params } catch { $message = $_.Exception.Message }
        Assert-Test ($message -match $Pattern) "Wrong/missing rejection: $message"
        Assert-Test (-not (Test-Path -LiteralPath $params.OutputDirectory)) 'Rejected source was published.'
        Assert-Test (-not (Test-Path -LiteralPath $params.EvidenceDirectory)) 'Rejected evidence was published.'
        Assert-Test (@(Get-ChildItem $script:caseDir -Force -Filter '.gitlab-*').Count -eq 0) 'Owned temporary directories leaked.'
        if ($BeforeFetch) { Assert-Test (@($script:calls | Where-Object { $_.Arguments[0] -eq 'fetch' }).Count -eq 0) 'Fetch ran after rejected ref probe.' }
    }
}
try {
    [IO.Directory]::CreateDirectory($fixture) | Out-Null
    $null = Local-Git @('init','--quiet','--initial-branch=main')
    $null = Local-Git @('config','user.name','Offline Test')
    $null = Local-Git @('config','user.email','offline@example.invalid')
    [IO.File]::WriteAllText((Join-Path $fixture 'app.txt'),'first')
    $null = Local-Git @('add','app.txt'); $null = Local-Git @('commit','--quiet','-m','first')
    $script:firstSha = Local-Git @('rev-parse','HEAD')
    [IO.File]::WriteAllText((Join-Path $fixture 'app.txt'),'second')
    $null = Local-Git @('add','app.txt'); $null = Local-Git @('commit','--quiet','-m','second')
    $script:lastSha = Local-Git @('rev-parse','HEAD')

    Case 'native Git helper runs with quoted space-containing working directory' {
        $version = & $nativeGit -GitPath $gitPath -Directory $root -Arguments @('--version')
        Assert-Test ($version -match '^git version ') 'Native Git did not execute.'
    }
    Case 'runtime scoped credential config is available only to that child process' {
        $header = 'Authorization: Basic ' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes('offline-user:offline-token'))
        $value = & $nativeGit -GitPath $gitPath -Directory $root -Arguments @('config','--get',"http.$repoUrl.extraHeader") -AuthHeader $header -RepositoryUrl $repoUrl
        Assert-Test ($value -ceq $header) 'Runtime config did not reach child.'
        Assert-Test (-not (Test-Path (Join-Path $root '.gitconfig'))) 'Credential config file was created.'
        $failed = $false
        try { $null = & $nativeGit -GitPath $gitPath -Directory $root -Arguments @('config','--get',"http.$repoUrl.extraHeader") } catch { $failed = $true }
        Assert-Test $failed 'Credential config survived to another child.'
    }
    Case 'native errors are sanitized' {
        $message=$null
        try { $null=& $nativeGit -GitPath $gitPath -Directory $root -Arguments @('not-a-real-subcommand') } catch { $message=$_.Exception.Message }
        Assert-Test ($message -match '^Git failed\.' -and $message -notmatch 'offline-token') 'Native stderr escaped or error was lost.'
    }

    # Only the network read operations are replaced with the real local fixture;
    # all other verification/checkout uses the production Git process helper.
    function Invoke-SourceGit {
        param([string]$GitPath,[string]$Directory,[string[]]$Arguments,[string]$AuthHeader,[string]$RepositoryUrl,[int]$TimeoutSeconds=120)
        $script:calls.Add([pscustomobject]@{Arguments=$Arguments;HasAuth=[bool]$AuthHeader;Directory=$Directory;TimeoutSeconds=$TimeoutSeconds})
        Assert-Test (-not (($Arguments -join ' ') -match 'offline-token|Authorization:')) 'Credential appeared in argv.'
        Assert-Test (-not $env:GITLAB_GIT_TOKEN -and -not $env:GITLAB_GIT_USERNAME) 'Parent credential env was not cleared before Git.'
        if ($Arguments[0] -eq 'ls-remote') {
            Assert-Test ([bool]$AuthHeader -and $RepositoryUrl -ceq $repoUrl) 'Ref probe credential not scoped to fixed origin.'
            Assert-Test ($TimeoutSeconds -eq 30 -and ($Arguments -join ' ') -ceq 'ls-remote --exit-code --refs origin refs/heads/main') 'Ref probe must be bounded and restricted to the fixed branch.'
            if ($script:failProbe) { throw 'Fake ls-remote timed out.' }
            if ($script:wrongProbe) { return ($script:lastSha + "`trefs/heads/unexpected") }
            $result=& $gitPath -c protocol.file.allow=always -C $Directory ls-remote --exit-code --refs $fixture refs/heads/main 2>&1
            if ($LASTEXITCODE -ne 0) { throw 'Local fixture ref probe failed.' }
            return ($result -join "`n").Trim()
        }
        if ($Arguments[0] -eq 'fetch') {
            Assert-Test ([bool]$AuthHeader -and $RepositoryUrl -ceq $repoUrl) 'Fetch credential not scoped to fixed origin.'
            if ($script:failFetch) { throw 'Fake fetch failed.' }
            $result=& $gitPath -c protocol.file.allow=always -C $Directory fetch --quiet --no-tags --no-recurse-submodules $fixture '+refs/heads/main:refs/remotes/origin/selected' 2>&1
            if ($LASTEXITCODE -ne 0) { throw 'Local fixture fetch failed.' }
            return ''
        }
        Assert-Test (-not $AuthHeader) 'Non-network-read child received credential.'
        if ($script:failAncestry -and $Arguments[0] -eq 'merge-base') { throw 'Fake commit is outside allowed branch.' }
        if ($script:wrongHead -and $Arguments[0] -eq 'rev-parse' -and $Arguments[1] -eq 'HEAD') { return ('f'*40) }
        return (& $nativeGit -GitPath $GitPath -Directory $Directory -Arguments $Arguments -TimeoutSeconds $TimeoutSeconds)
    }
    Case 'exact historical SHA checked out detached, not newer branch tip' {
        $params=Checkout-Args; Get-GitLabSource @params
        Assert-Test ([IO.File]::ReadAllText((Join-Path $params.OutputDirectory 'app.txt')) -ceq 'first') 'Latest bytes substituted for selected commit.'
        $head=& $gitPath -C $params.OutputDirectory rev-parse HEAD
        Assert-Test ($head -ceq $script:firstSha -and $head -cne $script:lastSha) 'Wrong exact SHA.'
        $branch=& $gitPath -C $params.OutputDirectory symbolic-ref -q HEAD 2>$null
        Assert-Test ($LASTEXITCODE -ne 0) 'Checkout is not detached.'
        $record=Get-Content (Join-Path $params.EvidenceDirectory 'source-provenance.json') -Raw | ConvertFrom-Json
        Assert-Test ($record.gitlabCommitSha -ceq $script:firstSha -and $record.adoBuildId -ceq '123' -and -not $record.applicationBuildExecuted) 'Evidence binding incorrect.'
        $persisted=[IO.File]::ReadAllText((Join-Path $params.OutputDirectory '.git/config')) + [IO.File]::ReadAllText((Join-Path $params.EvidenceDirectory 'source-provenance.json'))
        Assert-Test ($persisted -notmatch 'offline-token|offline-user|Authorization:|extraHeader') 'Credential persisted to config/evidence.'
        $networkCalls = @($script:calls | Where-Object HasAuth)
        Assert-Test ($networkCalls.Count -eq 2 -and $networkCalls[0].Arguments[0] -ceq 'ls-remote' -and $networkCalls[1].Arguments[0] -ceq 'fetch') 'Only ref probe then fetch may receive the transient credential.'
        Assert-Test ($networkCalls[0].TimeoutSeconds -eq 30 -and $networkCalls[1].TimeoutSeconds -eq 300) 'Probe must be short without changing the full fetch deadline.'
        Assert-Test (@(Get-ChildItem $script:caseDir -Force -Filter '.gitlab-*').Count -eq 0) 'Temporary directories leaked.'
    }
    Reject 'ref probe timeout stops before fetch and publishes nothing' {param($p) $script:failProbe=$true} 'Fake ls-remote timed out' -BeforeFetch
    Reject 'wrong advertised ref is refused without fetch' {param($p) $script:wrongProbe=$true} 'Ref probe returned no unique valid commit for the fixed source ref' -BeforeFetch
    Reject 'short SHA rejected before fetch' {param($p) $p.CommitSha='deadbeef'} '40-character'
    Reject 'unknown SHA rejected without latest fallback' {param($p) $p.CommitSha=('f'*40)} 'Git failed'
    Reject 'wrong branch ancestry rejected' {param($p) $script:failAncestry=$true} 'outside allowed branch'
    Reject 'wrong checked out HEAD rejected' {param($p) $script:wrongHead=$true} 'Checked-out HEAD'
    Reject 'failed fetch publishes neither source nor evidence' {param($p) $script:failFetch=$true} 'Fake fetch failed'
    Reject 'HTTP blocked by default before fetch' {param($p) $p.RepositoryUrl='http://gitlab.invalid/group/application.git'} 'HTTP source URL refused'
    Reject 'credential-bearing URL rejected' {param($p) $p.RepositoryUrl='https://user:secret@gitlab.invalid/group/application.git'} 'without embedded credentials'
    Reject 'URL query rejected' {param($p) $p.RepositoryUrl='https://gitlab.invalid/group/application.git?x=1'} 'without embedded credentials'
    Reject 'file protocol rejected' {param($p) $p.RepositoryUrl='file:///C:/private.git'} 'without embedded credentials'
    Reject 'invalid source ref rejected' {param($p) $p.SourceRef='--upload-pack=bad'} 'explicit refs/heads'
    Reject 'missing token rejected' {param($p) $env:GITLAB_GIT_TOKEN=$null} 'Missing/invalid'
    Reject 'credential newline rejected' {param($p) $env:GITLAB_GIT_TOKEN="bad`nvalue"} 'Missing/invalid'
    Case 'preexisting source directory is preserved' {
        $params=Checkout-Args; [IO.Directory]::CreateDirectory($params.OutputDirectory)|Out-Null
        $file=Join-Path $params.OutputDirectory 'keep.txt'; [IO.File]::WriteAllText($file,'keep'); $message=$null
        try {Get-GitLabSource @params} catch {$message=$_.Exception.Message}
        Assert-Test ($message -match 'already exists' -and [IO.File]::ReadAllText($file) -ceq 'keep') 'Existing output was adopted or deleted.'
        Assert-Test ($script:calls.Count -eq 0) 'Git started before existing directory rejection.'
    }
    Case 'preexisting evidence directory is preserved' {
        $params=Checkout-Args; [IO.Directory]::CreateDirectory($params.EvidenceDirectory)|Out-Null
        $file=Join-Path $params.EvidenceDirectory 'keep.txt'; [IO.File]::WriteAllText($file,'keep'); $message=$null
        try {Get-GitLabSource @params} catch {$message=$_.Exception.Message}
        Assert-Test ($message -match 'already exists' -and [IO.File]::ReadAllText($file) -ceq 'keep') 'Existing evidence was adopted or deleted.'
    }
    Case 'manual-only YAML routes explicitly to VM1 and publishes metadata only' {
        foreach($file in @('azure-pipelines-gitlab-source.yml','azure-pipelines-gitlab-connectivity.yml')) {
            $text=[IO.File]::ReadAllText((Join-Path $package ('ado/'+$file)))
            Assert-Test ($text -match '(?m)^trigger: none$' -and $text -match '(?m)^pr: none$') 'Automatic trigger enabled.'
            Assert-Test ($text -notmatch '(?m)^resources:' -and $text -match 'Agent.Name -equals SECSVR004-086T') 'Webhook attached or VM1 demand missing.'
            Assert-Test ($text -notmatch '(?m)^\s*- deployment:') 'Deployment job found.'
        }
        $yaml=[IO.File]::ReadAllText((Join-Path $package 'ado/azure-pipelines-gitlab-source.yml'))
        Assert-Test ($yaml -match 'ArtifactName: source-provenance' -and $yaml -match 'PublishBuildArtifacts@1') 'Wrong publication contract.'
    }
} finally {
    foreach ($name in $envNames) { [Environment]::SetEnvironmentVariable($name,$saved[$name]) }
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
}
Write-Host ("Tests: {0} passed; {1} failed; {2} total." -f ($count-$failures.Count),$failures.Count,$count)
if ($failures.Count) { throw ($failures -join [Environment]::NewLine) }
