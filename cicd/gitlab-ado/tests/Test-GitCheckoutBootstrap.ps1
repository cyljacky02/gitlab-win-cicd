# Offline PS 5.1 checks of the actual pre-checkout inline Git selection code.
# Does not run an ADO agent or claim to reproduce a company-host checkout failure.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$package = Split-Path -Parent $PSScriptRoot
$yaml = [IO.File]::ReadAllText((Join-Path $package 'ado/azure-pipelines-gitlab-file-delivery.yml'))
$match = [regex]::Match($yaml, '(?ms)^                # BEGIN CHECKOUT GIT BOOTSTRAP\r?\n(?<code>.*?)^                # END CHECKOUT GIT BOOTSTRAP')
if (-not $match.Success) { throw 'Missing Git bootstrap before checkout: self.' }
$code = [regex]::Replace($match.Groups['code'].Value, '(?m)^                ', '')
$bootstrap = [scriptblock]::Create($code)
$gitPath = (Get-Command git.exe -CommandType Application | Select-Object -First 1).Source
$root = Join-Path ([IO.Path]::GetTempPath()) ('checkout git tests-' + [Guid]::NewGuid().ToString('N'))
$envNames = @('ProgramFiles', 'ProgramFiles(x86)', 'PATH', 'AGENT_HOMEDIRECTORY', 'AGENT_TEMPDIRECTORY')
$saved = @{}; foreach ($name in $envNames) { $saved[$name] = [Environment]::GetEnvironmentVariable($name) }
$count = 0
function Assert-Check($Value, [string]$Message) { if (-not $Value) { throw $Message }; $script:count++; Write-Host "PASS $Message" }
try {
    [IO.Directory]::CreateDirectory($root) | Out-Null
    $env:AGENT_TEMPDIRECTORY = $root
    $env:AGENT_HOMEDIRECTORY = Join-Path $root 'agent'
    $env:ProgramFiles = Join-Path $root 'program files'
    ${env:ProgramFiles(x86)} = Join-Path $root 'program files x86'
    $env:PATH = Split-Path -Parent $gitPath

    $firstCheckout = $yaml.IndexOf('          - checkout: self')
    Assert-Check ($match.Index -lt $firstCheckout) 'Git bootstrap is before VM1 checkout'
    Assert-Check ($yaml -match '(?m)^          - name: System.PreferGitFromPath\r?\n            value: ''true''') 'VM1 checkout is configured to prefer PATH Git'
    $output = (& $bootstrap 6>&1 | Out-String)
    Assert-Check ($output -match [regex]::Escape('##vso[task.prependpath]' + (Split-Path -Parent $gitPath))) 'Real Git is selected and exported for subsequent steps'
    Assert-Check ($output -match 'git version \d+\.\d+') 'Real Git version was obtained'

    # Simulate an installed git.exe that cannot launch, while a real Git is in PATH.
    $broken = Join-Path $env:ProgramFiles 'Git\cmd\git.exe'
    [IO.Directory]::CreateDirectory((Split-Path -Parent $broken)) | Out-Null
    [IO.File]::WriteAllText($broken, 'not a Windows executable')
    $output = (& $bootstrap 6>&1 | Out-String)
    Assert-Check ($output -match [regex]::Escape('##vso[task.prependpath]' + (Split-Path -Parent $gitPath))) 'Unlaunchable Git candidate is skipped for working PATH Git'

    # A process exiting zero without any version output must not be accepted.
    $silent = Join-Path $root 'silent-git.exe'
    Add-Type -TypeDefinition 'public class SilentGit { public static int Main(string[] args) { return 0; } }' -OutputAssembly $silent -OutputType ConsoleApplication
    [IO.File]::Copy($silent, $broken, $true)
    $output = (& $bootstrap 6>&1 | Out-String)
    Assert-Check ($output -match [regex]::Escape('##vso[task.prependpath]' + (Split-Path -Parent $gitPath))) 'Zero-exit Git with no version is skipped'

    $env:PATH = Join-Path $root 'empty-path'
    $message = $null
    try { & $bootstrap 6>&1 | Out-Null } catch { $message = $_.Exception.Message }
    Assert-Check ($message -match 'No working Git for Windows 2\.31\+') 'Missing working Git stops before checkout with actionable error'
} finally {
    foreach ($name in $envNames) { [Environment]::SetEnvironmentVariable($name, $saved[$name]) }
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
}
Write-Host "Git bootstrap checks: $count passed. ADO checkout still requires on-host verification."
