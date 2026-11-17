# Offline PS 5.1 checks of the YAML's native Build Artifact upload command.
# No ADO server is contacted; actual artifact transport requires on-host verification.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $PSScriptRoot
$yaml = [IO.File]::ReadAllText((Join-Path $packageRoot 'ado/azure-pipelines-gitlab-file-delivery.yml'))
$match = [regex]::Match($yaml, '(?ms)^                # BEGIN NATIVE BUILD ARTIFACT UPLOAD\r?\n(?<code>.*?)^                # END NATIVE BUILD ARTIFACT UPLOAD')
if (-not $match.Success) { throw 'Missing node-independent Build Artifact upload step.' }
$code = [regex]::Replace($match.Groups['code'].Value, '(?m)^                ', '')
$upload = [scriptblock]::Create($code)
$root = Join-Path ([IO.Path]::GetTempPath()) ('artifact upload tests-%;[literal]-' + [Guid]::NewGuid().ToString('N'))
$staging = Join-Path $root 'staging'
$package = Join-Path $staging 'source-package'
$saved = $env:BUILD_ARTIFACTSTAGINGDIRECTORY
$count = 0
function Assert-Check($Value, [string]$Message) { if (-not $Value) { throw $Message }; $script:count++; Write-Host "PASS $Message" }
function Assert-Rejected([string]$Name) {
    $message = $null
    $script:observed = @()
    try { & $upload 6>&1 | ForEach-Object { $script:observed += [string]$_ } } catch { $message = $_.Exception.Message }
    Assert-Check ([bool]$message) "$Name is rejected"
    Assert-Check (-not ($script:observed -match '^##vso\[artifact.upload ')) "$Name emits no upload command"
}
try {
    $env:BUILD_ARTIFACTSTAGINGDIRECTORY = $staging
    Assert-Check ($yaml -notmatch '(?m)^          - task: PublishBuildArtifacts@') 'Package job no longer invokes the missing-Node task'
    Assert-Rejected 'Missing package directory'
    [IO.Directory]::CreateDirectory($package) | Out-Null
    [IO.File]::WriteAllText((Join-Path $package 'source-package.json'), '{"schema":1}')
    [IO.File]::WriteAllText((Join-Path $package 'source-provenance.json'), '{"schema":1}')
    Assert-Rejected 'Missing ZIP'
    [IO.File]::WriteAllBytes((Join-Path $package 'Rayin-offline-fixture.zip'), [byte[]]@(80,75,5,6))
    $output = @(& $upload 6>&1 | ForEach-Object { [string]$_ })
    $commands = @($output | Where-Object { $_ -match '^##vso\[artifact.upload ' })
    Assert-Check ($commands.Count -eq 1) 'Exactly one directory upload command is emitted'
    $escaped = $package.Replace('%', '%AZP25').Replace(';', '%3B').Replace(']', '%5D')
    Assert-Check ($commands[0] -ceq "##vso[artifact.upload containerfolder=source-package;artifactname=source-package;]$escaped") 'Current-run Container artifact name/root/path and command escaping are preserved'
    Assert-Check (@(Get-ChildItem -LiteralPath $package -Force).Count -eq 3) 'Upload emitter does not modify the source package'
    [IO.File]::WriteAllText((Join-Path $package 'unexpected.txt'), 'do not publish extra files')
    Assert-Rejected 'Unexpected extra file'
    Remove-Item -LiteralPath (Join-Path $package 'unexpected.txt')
    Remove-Item -LiteralPath (Join-Path $package 'Rayin-offline-fixture.zip')
    [IO.Directory]::CreateDirectory((Join-Path $package 'nested.zip')) | Out-Null
    Assert-Rejected 'Directory posing as ZIP'
} finally {
    $env:BUILD_ARTIFACTSTAGINGDIRECTORY = $saved
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
}
Write-Host "Native Build Artifact upload checks: $count passed; server transport not exercised."
