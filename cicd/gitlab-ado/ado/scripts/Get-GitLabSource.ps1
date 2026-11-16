# Manual CD-owned source checkout, PowerShell 5.1. Never attach to the open smoke webhook.
[CmdletBinding()]
param(
    [string]$RepositoryUrl = $env:SOURCE_REPOSITORY_URL,
    [string]$SourceRef = $env:SOURCE_REF,
    [string]$CommitSha = $env:EXPECTED_COMMIT_SHA,
    [string]$OutputDirectory,
    [string]$EvidenceDirectory,
    [switch]$AllowInsecureHttpLab
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-SourceGit {
    param([string]$GitPath, [string]$Directory, [string[]]$Arguments, [string]$AuthHeader, [string]$RepositoryUrl, [int]$TimeoutSeconds = 120)
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $GitPath
    $start.WorkingDirectory = $Directory
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $fixed = @('-c','credential.helper=','-c','credential.interactive=false',
        '-c','http.sslVerify=true','-c','http.sslBackend=schannel','-c','http.followRedirects=false',
        '-c','http.lowSpeedLimit=1','-c','http.lowSpeedTime=30',
        '-c','protocol.file.allow=never','-c','protocol.ext.allow=never',
        '-c','submodule.recurse=false','-c','core.symlinks=false','-c','filter.lfs.required=false',
        '-c','filter.lfs.smudge=','-c','filter.lfs.process=')
    $quoted = foreach ($argument in @($fixed) + @($Arguments)) {
        if ($argument.Contains('"') -or $argument -match '[\x00-\x1f]') { throw 'Unsafe Git argument.' }
        # Windows process command-line quoting. No token appears in these arguments.
        '"' + [regex]::Replace($argument, '(\\+)$', '$1$1') + '"'
    }
    $start.Arguments = $quoted -join ' '
    foreach ($key in @($start.EnvironmentVariables.Keys)) {
        if ($key -match '^(GIT_|GITLAB_)' -or $key -eq 'SYSTEM_ACCESSTOKEN') { $start.EnvironmentVariables.Remove($key) }
    }
    $start.EnvironmentVariables['GIT_CONFIG_NOSYSTEM'] = '1'
    $start.EnvironmentVariables['GIT_CONFIG_GLOBAL'] = 'NUL'
    $start.EnvironmentVariables['GIT_TERMINAL_PROMPT'] = '0'
    $start.EnvironmentVariables['GIT_LFS_SKIP_SMUDGE'] = '1'
    if ($AuthHeader) {
        # Runtime-only config scoped to this fixed repository, never argv/.gitconfig/URL.
        $start.EnvironmentVariables['GIT_CONFIG_COUNT'] = '1'
        $start.EnvironmentVariables['GIT_CONFIG_KEY_0'] = "http.$RepositoryUrl.extraHeader"
        $start.EnvironmentVariables['GIT_CONFIG_VALUE_0'] = $AuthHeader
    }
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $start
    try {
        if (-not $process.Start()) { throw 'Git could not start.' }
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            & "$env:SystemRoot\System32\taskkill.exe" /PID $process.Id /T /F *> $null
            throw 'Git timed out; no source checkout accepted.'
        }
        $text = $stdout.GetAwaiter().GetResult()
        $null = $stderr.GetAwaiter().GetResult()
        if ($process.ExitCode -ne 0) { throw 'Git failed. Check repository permission, URL, TLS, branch and SHA; raw Git output is not logged.' }
        return $text.Trim()
    } finally {
        $start.EnvironmentVariables.Remove('GIT_CONFIG_VALUE_0')
        $process.Dispose()
    }
}

function Get-GitLabSource {
    param([string]$RepositoryUrl, [string]$SourceRef, [string]$CommitSha, [string]$OutputDirectory, [string]$EvidenceDirectory, [switch]$AllowInsecureHttpLab)
    if ($CommitSha -cnotmatch '^[a-fA-F0-9]{40}$') { throw 'Specify the full 40-character GitLab commit SHA; never latest.' }
    $CommitSha = $CommitSha.ToLowerInvariant()
    if ($SourceRef -cnotmatch '^refs/heads/[A-Za-z0-9._/-]+$') { throw 'Expected an explicit refs/heads/... source ref.' }
    $uri = $null
    if (-not [Uri]::TryCreate($RepositoryUrl, [UriKind]::Absolute, [ref]$uri) -or
        $uri.Scheme -notin @('http','https') -or $uri.UserInfo -or $uri.Query -or $uri.Fragment -or
        $RepositoryUrl -match '[\x00-\x20"\\]' -or -not $uri.AbsolutePath.EndsWith('.git')) { throw 'Expected a fixed HTTP(S) Git URL without embedded credentials.' }
    if ($uri.Scheme -ne 'https' -and -not $AllowInsecureHttpLab) {
        throw 'HTTP source URL refused before sending credentials. Use approved HTTPS, or explicitly authorize the isolated-lab HTTP exception.'
    }
    if ($uri.Scheme -eq 'http') { Write-Warning 'LAB ONLY: Git credentials and private source travel in plaintext. Use only an approved short-lived read-only credential; revoke after testing.' }
    $username = $env:GITLAB_GIT_USERNAME
    $token = $env:GITLAB_GIT_TOKEN
    $env:GITLAB_GIT_USERNAME = $null
    $env:GITLAB_GIT_TOKEN = $null
    if (-not $username -or -not $token -or $username.Contains(':') -or $username -match '[\x00-\x1f]' -or $token -match '[\x00-\x1f]') { throw 'Missing/invalid GitLab read-only Git credential.' }
    $auth = 'Authorization: Basic ' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($username + ':' + $token))
    $token = $null; $username = $null
    $git = Get-Command git.exe -ErrorAction SilentlyContinue
    $gitPath = if ($git) { $git.Source } else { Join-Path $env:AGENT_HOMEDIRECTORY 'externals\git\cmd\git.exe' }
    if (-not (Test-Path -LiteralPath $gitPath -PathType Leaf)) { throw 'Git for Windows is unavailable to this agent.' }
    if (-not $OutputDirectory -or -not $EvidenceDirectory) { throw 'Source and evidence output directories are required.' }
    $output = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputDirectory)
    $evidence = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($EvidenceDirectory)
    if ($output -eq $evidence -or $evidence.StartsWith($output.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase) -or
        $output.StartsWith($evidence.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Keep source and evidence directories separate.' }
    if ((Test-Path -LiteralPath $output) -or (Test-Path -LiteralPath $evidence)) { throw 'Source/evidence output already exists; use a clean isolated job workspace.' }
    $parent = Split-Path -Parent $output
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    $temp = Join-Path $parent ('.gitlab-source-' + [Guid]::NewGuid().ToString('N'))
    $empty = Join-Path $parent ('.gitlab-empty-template-' + [Guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($temp) | Out-Null
    [IO.Directory]::CreateDirectory($empty) | Out-Null
    $moved = $false; $evidenceOwned = $false
    try {
        $gitBase = @{ GitPath = $gitPath; Directory = $temp }
        $version = Invoke-SourceGit @gitBase -Arguments @('--version')
        if ($version -notmatch '^git version (\d+)\.(\d+)\.') { throw 'Cannot identify Git version.' }
        if ([int]$Matches[1] -lt 2 -or ([int]$Matches[1] -eq 2 -and [int]$Matches[2] -lt 31)) { throw 'Git 2.31+ required for runtime-only credential configuration.' }
        $null = Invoke-SourceGit @gitBase -Arguments @('check-ref-format', $SourceRef)
        $null = Invoke-SourceGit @gitBase -Arguments @('init','--quiet',"--template=$empty")
        $null = Invoke-SourceGit @gitBase -Arguments @('config','core.hooksPath', $empty)
        $null = Invoke-SourceGit @gitBase -Arguments @('remote','add','origin',$RepositoryUrl)
        # Fetch the fixed branch, not a caller-selected URL; verify SHA ancestry.
        $null = Invoke-SourceGit @gitBase -Arguments @('fetch','--quiet','--no-tags','--no-recurse-submodules','origin',("+${SourceRef}:refs/remotes/origin/selected")) -AuthHeader $auth -RepositoryUrl $RepositoryUrl -TimeoutSeconds 300
        $auth = $null
        $resolved = Invoke-SourceGit @gitBase -Arguments @('rev-parse','--verify',"${CommitSha}^{commit}")
        if ($resolved -cne $CommitSha) { throw 'Git object differs from the selected exact commit.' }
        $null = Invoke-SourceGit @gitBase -Arguments @('merge-base','--is-ancestor',$CommitSha,'refs/remotes/origin/selected')
        # No credentials in this process; no global filters/hooks, LFS or submodule execution.
        $null = Invoke-SourceGit @gitBase -Arguments @('checkout','--quiet','--detach',$CommitSha)
        $head = Invoke-SourceGit @gitBase -Arguments @('rev-parse','HEAD')
        if ($head -cne $CommitSha) { throw 'Checked-out HEAD differs from the selected exact commit.' }
        [IO.Directory]::Move($temp,$output); $moved = $true
        $record = [ordered]@{
            schema = 1; purpose = 'ManualGitLabSourceCheckoutOnly'
            repositoryUrl = $RepositoryUrl; sourceRef = $SourceRef; gitlabCommitSha = $CommitSha
            adoBuildId = [string]$env:BUILD_BUILDID; adoToolCommit = [string]$env:BUILD_SOURCEVERSION
            gitVersion = $version; fetchedAtUtc = [DateTime]::UtcNow.ToString('o')
            submodulesFetched = $false; lfsObjectsFetched = $false; applicationBuildExecuted = $false
        }
        [IO.Directory]::CreateDirectory($evidence) | Out-Null; $evidenceOwned = $true
        [IO.File]::WriteAllText((Join-Path $evidence 'source-provenance.json'), ($record | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
        Write-Host "Checked out exact GitLab commit $CommitSha on the selected VM1 agent. No application build or deployment executed."
    } catch {
        if ($moved) { Remove-Item -LiteralPath $output -Recurse -Force }
        if ($evidenceOwned) { Remove-Item -LiteralPath $evidence -Recurse -Force }
        throw
    } finally {
        $auth = $null; $token = $null
        foreach ($path in @($temp,$empty)) { if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force } }
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    Get-GitLabSource -RepositoryUrl $RepositoryUrl -SourceRef $SourceRef -CommitSha $CommitSha -OutputDirectory $OutputDirectory -EvidenceDirectory $EvidenceDirectory -AllowInsecureHttpLab:($AllowInsecureHttpLab -or $env:ALLOW_INSECURE_HTTP_LAB -eq 'true')
}
