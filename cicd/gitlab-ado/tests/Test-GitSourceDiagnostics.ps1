# Offline PS 5.1: exercise the real Git process runner with controlled executables.
# Reproduces its timeout path quickly; does not diagnose company network connectivity.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$package = Split-Path -Parent $PSScriptRoot
. (Join-Path $package 'ado/scripts/Get-GitLabSource.ps1')
$root = Join-Path ([IO.Path]::GetTempPath()) ('git diagnostic tests-' + [Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($root) | Out-Null
$count = 0
function Assert-Check($Value, [string]$Message) { if (-not $Value) { throw $Message }; $script:count++; Write-Host "PASS $Message" }
try {
    $fixture = Join-Path $root 'diagnostic-git.exe'
    Add-Type -OutputAssembly $fixture -OutputType ConsoleApplication -TypeDefinition @'
using System;
using System.IO;
using System.Threading;
public class DiagnosticGit {
    public static int Main(string[] args) {
        string input = String.Join(" ", args);
        Console.Error.WriteLine("remote: offline-token Authorization: Basic cHJpdmF0ZTpwYXNz; private-repo-name");
        if (input.Contains("--fixture-hang")) {
            if (input.Contains("--fixture-heartbeat")) {
                string pack = Path.Combine(Environment.CurrentDirectory, ".git", "objects", "pack");
                Directory.CreateDirectory(pack);
                File.WriteAllBytes(Path.Combine(pack, "tmp_pack_fixture"), new byte[4096]);
            }
            Console.Error.Write("Receiving objects: 42% (42/100), 1.23 MiB | 12.34 KiB/s\r");
            Console.Error.Flush();
            Thread.Sleep(30000);
            return 0;
        }
        if (input.Contains("--fixture-auth")) {
            Console.Error.WriteLine("fatal: Authentication failed for http://offline-user:offline-token@gitlab.invalid/private-repo-name.git/");
            return 1;
        }
        if (input.Contains("--fixture-connect")) {
            Console.Error.WriteLine("fatal: unable to access private-repo-name: Failed to connect to 127.0.0.1 port 9: Connection refused");
            return 1;
        }
        Console.Out.Write("expected-command-result");
        return 0;
    }
}
'@
    $script:message = $null
    $clock = [Diagnostics.Stopwatch]::StartNew()
    $logs = @(& {
        try { $null = Invoke-SourceGit -GitPath $fixture -Directory $root -Arguments @('fetch','--fixture-hang') -TimeoutSeconds 1 }
        catch { $script:message = $_.Exception.Message }
    } 6>&1 | ForEach-Object { [string]$_ }) -join "`n"
    $clock.Stop()
    Assert-Check ($message -match 'Git timed out during fetch after 1s') 'Timeout identifies fetch and its configured deadline'
    Assert-Check ($clock.Elapsed.TotalSeconds -lt 10) 'Hung Git is terminated promptly instead of waiting for the fixture exit'
    Assert-Check ($logs -match '\[GitSource\] start fetch; timeout=1s') 'Operation start is recorded before the process wait'
    Assert-Check ($logs -match 'Receiving objects 42% \(42/100\)') 'Only allowlisted numeric transfer progress is reported'
    Assert-Check (($logs + $message) -notmatch 'offline-token|offline-user|Authorization|cHJpdmF0ZTpwYXNz|private-repo-name') 'Timeout diagnostics do not expose raw stderr/credentials/repository text'
    $logs = @(& {
        try { $null = Invoke-SourceGit -GitPath $fixture -Directory $root -Arguments @('fetch','--fixture-hang','--fixture-heartbeat') -TimeoutSeconds 16 }
        catch { $script:message = $_.Exception.Message }
    } 6>&1 | ForEach-Object { [string]$_ }) -join "`n"
    Assert-Check ($logs -match '\[GitSource\] fetch elapsed=\d+s; temporary-pack-bytes=4096') 'A real wait emits the 15-second heartbeat and numeric local pack size'
    Assert-Check ($logs -notmatch 'offline-token|Authorization|private-repo-name') 'Heartbeat does not expose raw remote data'
    foreach ($case in @(@{Flag='--fixture-auth';Category='authentication'}, @{Flag='--fixture-connect';Category='connection'})) {
        $script:message = $null
        $logs = @(& {
            try { $null = Invoke-SourceGit -GitPath $fixture -Directory $root -Arguments @('fetch',$case.Flag) -TimeoutSeconds 5 }
            catch { $script:message = $_.Exception.Message }
        } 6>&1 | ForEach-Object { [string]$_ }) -join "`n"
        Assert-Check ($message -match ('Git failed\..*fetch.*category=' + $case.Category)) ('Safe failure category: ' + $case.Category)
        Assert-Check (($logs + $message) -notmatch 'offline-token|offline-user|Authorization|cHJpdmF0ZTpwYXNz|private-repo-name') ('No raw error data logged for ' + $case.Category)
    }
    $result = Invoke-SourceGit -GitPath $fixture -Directory $root -Arguments @('config','--fixture-success') -TimeoutSeconds 5
    Assert-Check ($result -ceq 'expected-command-result') 'Status logs do not contaminate the Git stdout return value'
    $code = [IO.File]::ReadAllText((Join-Path $package 'ado/scripts/Get-GitLabSource.ps1'))
    Assert-Check ($code -match "'fetch','--progress'" -and $code -match '-TimeoutSeconds 300') 'Fetch exposes progress but retains the 300-second timeout and existing source contract'
} finally {
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
}
Write-Host "Git diagnostics checks: $count passed. Actual GitLab transfer not exercised."
