# CD-owned source checkout, PowerShell 5.1. Never attach to the open smoke webhook.
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
    # Log only an allowlisted operation, never argv, URL, headers or raw stderr.
    $operation = 'git-command'
    if ($Arguments.Count -gt 0 -and $Arguments[0] -in @('--version','check-ref-format','init','config','remote','ls-remote','fetch','rev-parse','merge-base','checkout','diff','ls-tree')) { $operation = $Arguments[0] }
    Write-Host "[GitSource] start $operation; timeout=${TimeoutSeconds}s"
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $GitPath
    $start.WorkingDirectory = $Directory
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    # Git -z paths are UTF-8, including on Windows with a non-UTF-8 console.
    $start.StandardOutputEncoding = New-Object Text.UTF8Encoding($false)
    $start.StandardErrorEncoding = New-Object Text.UTF8Encoding($false)
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
    if ($operation -eq 'fetch') {
        # Capture headers/info in this process's private stderr only. Never dump
        # trace text or body data; below emits only method/status allowlist fields.
        $start.EnvironmentVariables['GIT_TRACE_CURL'] = '1'
        $start.EnvironmentVariables['GIT_TRACE_CURL_NO_DATA'] = '1'
        $start.EnvironmentVariables['GIT_TRACE_REDACT'] = '1'
    }
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $start
    $clock = [Diagnostics.Stopwatch]::StartNew()
    try {
        if (-not $process.Start()) { throw 'Git could not start.' }
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $timedOut = $false
        $nextReport = 15
        while (-not $process.WaitForExit(1000)) {
            if ($clock.Elapsed.TotalSeconds -ge $TimeoutSeconds) {
                & "$env:SystemRoot\System32\taskkill.exe" /PID $process.Id /T /F *> $null
                $null = $process.WaitForExit(5000)
                $timedOut = $true
                break
            }
            if ($operation -eq 'fetch' -and $clock.Elapsed.TotalSeconds -ge $nextReport) {
                # Git writes incoming pack data here. Increasing bytes is evidence of
                # local pack activity; zero does NOT prove the connection never opened.
                $packBytes = [long]0
                $packDirectory = Join-Path $Directory '.git/objects/pack'
                foreach ($file in @(Get-ChildItem -LiteralPath $packDirectory -File -Force -ErrorAction SilentlyContinue)) { $packBytes += $file.Length }
                Write-Host "[GitSource] fetch elapsed=$([int]$clock.Elapsed.TotalSeconds)s; temporary-pack-bytes=$packBytes"
                $nextReport += 15
            }
        }
        $diagnostics = ''
        if ($stderr.Wait(2000)) { $diagnostics = $stderr.GetAwaiter().GetResult() }
        if ($operation -eq 'fetch') {
            $hasProgress = $false
            foreach ($phase in @('Counting objects', 'Receiving objects', 'Resolving deltas')) {
                $progress = [regex]::Matches($diagnostics, ([regex]::Escape($phase) + ':\s*(\d{1,3})%\s*\((\d{1,12})/(\d{1,12})\)'))
                if ($progress.Count -gt 0) {
                    $last = $progress[$progress.Count - 1]
                    Write-Host "[GitSource] $phase $($last.Groups[1].Value)% ($($last.Groups[2].Value)/$($last.Groups[3].Value))"
                    $hasProgress = $true
                }
            }
            if (-not $hasProgress) { Write-Host '[GitSource] fetch: no numeric transfer progress captured; connection state is not established by this observation.' }
            $requests = New-Object 'Collections.Generic.List[object]'
            $events = [regex]::Matches($diagnostics, '(?m)(?:=> Send header: (?:(GET|POST)\s+[^\r\n]*?\s+HTTP/[0-9.]+|:method:\s*(GET|POST))|<= Recv header: HTTP/[0-9.]+\s+([0-9]{3}))')
            foreach ($event in $events) {
                if ($event.Groups[1].Success -or $event.Groups[2].Success) {
                    $method = if ($event.Groups[1].Success) { $event.Groups[1].Value } else { $event.Groups[2].Value }
                    $requests.Add([pscustomobject]@{ Method=$method; Status='not-observed' })
                } elseif ($requests.Count -gt 0) {
                    # Last observed HTTP status, not a claim of backend receipt or
                    # a complete response body. Never include any header value.
                    $requests[$requests.Count - 1].Status = $event.Groups[3].Value
                }
            }
            for ($index = 0; $index -lt $requests.Count; $index++) {
                Write-Host "[GitSource] HTTP request $($index + 1): method=$($requests[$index].Method); response-status=$($requests[$index].Status)"
            }
            if ($requests.Count -eq 0) { Write-Host '[GitSource] HTTP trace: no method/status events captured; this does not prove no request was sent.' }
        }
        if ($timedOut) { throw "Git timed out during $operation after ${TimeoutSeconds}s; no source checkout accepted." }
        if ($process.ExitCode -ne 0) {
            $category = 'unspecified'
            if ($operation -eq 'ls-remote' -and $process.ExitCode -eq 2) { $category = 'ref-not-found' }
            elseif ($diagnostics -match 'Authentication failed|HTTP[^\r\n]*(?:401|403)|could not read Username') { $category = 'authentication' }
            elseif ($diagnostics -match 'Could not resolve host|Could not resolve proxy') { $category = 'name-resolution' }
            elseif ($diagnostics -match 'Failed to connect|Connection refused|Connection timed out|Could not connect') { $category = 'connection' }
            elseif ($diagnostics -match 'SSL certificate|certificate problem|schannel:') { $category = 'tls' }
            elseif ($diagnostics -match 'Operation too slow|Less than .* bytes/sec') { $category = 'low-speed' }
            throw "Git failed. operation=$operation; category=$category. Check repository permission, URL, TLS, branch and SHA; raw Git output is not logged."
        }
        if (-not $stdout.Wait(2000)) { throw "Git output collection timed out during $operation; no source checkout accepted." }
        $text = $stdout.GetAwaiter().GetResult()
        Write-Host "[GitSource] completed $operation; elapsed=$([int]$clock.Elapsed.TotalSeconds)s"
        return $text.Trim()
    } finally {
        $clock.Stop()
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
        # Read only one ref before downloading history, using the same Git process
        # isolation and transient URL-scoped credential as fetch. Never print refs.
        Write-Host "[GitSource] ALL_PROXY present: $([bool]$env:ALL_PROXY); proxy values are not logged."
        $advertisedRef = Invoke-SourceGit @gitBase -Arguments @('ls-remote','--exit-code','--refs','origin',$SourceRef) -AuthHeader $auth -RepositoryUrl $RepositoryUrl -TimeoutSeconds 30
        if ($advertisedRef -cnotmatch ('\A[0-9a-fA-F]{40}\t' + [regex]::Escape($SourceRef) + '\z')) {
            throw 'Ref probe returned no unique valid commit for the fixed source ref; no fetch or checkout accepted.'
        }
        Write-Host '[GitSource] Git ref probe passed; fixed source ref is readable. Starting exact-commit fetch.'
        # Fetch the fixed branch, not a caller-selected URL; verify SHA ancestry.
        $null = Invoke-SourceGit @gitBase -Arguments @('fetch','--progress','--no-tags','--no-recurse-submodules','origin',("+${SourceRef}:refs/remotes/origin/selected")) -AuthHeader $auth -RepositoryUrl $RepositoryUrl -TimeoutSeconds 300
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
            schema = 1; purpose = 'GitLabSourceCheckoutOnly'
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
