# Offline PS 5.1 regression: execute the actual YAML inline entrypoint wrappers.
# Uses real Git/ZIP/copy in a temporary workspace; no network or ADO server calls.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $PSScriptRoot
$mainYaml = [IO.File]::ReadAllText((Join-Path $packageRoot 'ado/azure-pipelines-gitlab-file-delivery.yml'))
$sourceYaml = [IO.File]::ReadAllText((Join-Path $packageRoot 'ado/azure-pipelines-gitlab-source.yml'))
$root = Join-Path ([IO.Path]::GetTempPath()) ('task entrypoint tests-' + [Guid]::NewGuid().ToString('N'))
$source = Join-Path $root 'gitlab-source'
$staging = Join-Path $root 'staging'
$evidence = Join-Path $staging 'source-provenance'
$package = Join-Path $staging 'source-package'
$artifactParent = Join-Path $root 'current-source-package'
$destination = Join-Path $root 'destination'
$git = (Get-Command git.exe -ErrorAction Stop | Select-Object -First 1).Source
$envNames = @('BUILD_SOURCESDIRECTORY','PIPELINE_WORKSPACE','BUILD_ARTIFACTSTAGINGDIRECTORY','BUILD_BUILDID','BUILD_SOURCEVERSION','EXPECTED_COMMIT_SHA','SOURCE_REPOSITORY_URL','SOURCE_REF','DELIVERY_DIRECTORY')
$saved = @{}; foreach ($name in $envNames) { $saved[$name] = [Environment]::GetEnvironmentVariable($name) }
$count = 0
function Assert-Check($Value, [string]$Message) { if (-not $Value) { throw $Message }; $script:count++; Write-Host "PASS $Message" }
function Get-InlineWrapper([string]$Yaml, [string]$Name) {
    $pattern = '(?ms)^ +# BEGIN ' + [regex]::Escape($Name) + '\r?\n(?<code>.*?)^ +# END ' + [regex]::Escape($Name)
    $match = [regex]::Match($Yaml, $pattern)
    if (-not $match.Success) { throw "Missing explicit inline entrypoint invocation: $Name" }
    return [scriptblock]::Create($match.Groups['code'].Value)
}
function Invoke-LocalGit([string[]]$Arguments) {
    $result = & $git -C $source @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'Local Git fixture setup failed.' }
    return ($result -join "`n").Trim()
}
try {
    $env:BUILD_SOURCESDIRECTORY = Join-Path $packageRoot 'ado'
    $env:PIPELINE_WORKSPACE = $root
    $env:BUILD_ARTIFACTSTAGINGDIRECTORY = $staging
    $env:BUILD_BUILDID = '123'; $env:BUILD_SOURCEVERSION = ('b' * 40)
    $env:SOURCE_REPOSITORY_URL = 'https://gitlab.invalid/group/app.git'
    $env:SOURCE_REF = 'refs/heads/poc/cicd'
    $env:DELIVERY_DIRECTORY = $destination
    $packWrapper = Get-InlineWrapper $mainYaml 'SOURCE PACKAGE INVOCATION'
    $copyWrapper = Get-InlineWrapper $mainYaml 'SOURCE DELIVERY INVOCATION'
    [IO.Directory]::CreateDirectory($source) | Out-Null
    [IO.Directory]::CreateDirectory($evidence) | Out-Null
    $null = Invoke-LocalGit @('init', '--quiet', '--initial-branch=poc/cicd')
    [IO.File]::WriteAllText((Join-Path $source 'app.txt'), 'expected exact fixture bytes')
    $null = Invoke-LocalGit @('add', 'app.txt')
    $null = Invoke-LocalGit @('-c', 'user.name=Offline', '-c', 'user.email=offline@example.invalid', 'commit', '--quiet', '-m', 'fixture')
    $sha = Invoke-LocalGit @('rev-parse', 'HEAD'); $env:EXPECTED_COMMIT_SHA = $sha
    $record = @{gitlabCommitSha=$sha;adoBuildId='123';repositoryUrl=$env:SOURCE_REPOSITORY_URL;sourceRef=$env:SOURCE_REF;applicationBuildExecuted=$false}
    [IO.File]::WriteAllText((Join-Path $evidence 'source-provenance.json'), ($record | ConvertTo-Json))
    & $packWrapper
    Assert-Check (Test-Path -LiteralPath $package -PathType Container) 'Actual YAML ZIP wrapper creates the source-package directory'
    $manifest = [IO.File]::ReadAllText((Join-Path $package 'source-package.json')) | ConvertFrom-Json
    Assert-Check ($manifest.gitlabCommitSha -ceq $sha -and $manifest.adoBuildId -ceq '123' -and -not $manifest.applicationBuildExecuted) 'Executed package is bound to the selected SHA/run'
    $zipPath = Join-Path $package $manifest.zipFileName
    $zip = [IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        $reader = New-Object IO.StreamReader($zip.GetEntry('app.txt').Open())
        try { $content = $reader.ReadToEnd() } finally { $reader.Dispose() }
        Assert-Check ($zip.Entries.Count -eq 1 -and $content -ceq 'expected exact fixture bytes') 'ZIP contains the expected tracked bytes, not merely a green task'
    } finally { $zip.Dispose() }
    [IO.Directory]::CreateDirectory($artifactParent) | Out-Null
    Copy-Item -LiteralPath $package -Destination (Join-Path $artifactParent 'source-package') -Recurse
    & $copyWrapper
    $delivered = Join-Path $destination $manifest.zipFileName
    Assert-Check ((Test-Path -LiteralPath $delivered -PathType Leaf) -and @(Get-ChildItem -LiteralPath $destination -Force).Count -eq 1) 'Actual YAML Copy wrapper delivers only the ZIP'
    Assert-Check ((Get-FileHash -LiteralPath $delivered -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $manifest.zipSha256) 'Delivered ZIP hash matches the executed package'
    $env:EXPECTED_COMMIT_SHA = 'invalid'
    foreach ($yaml in @($mainYaml, $sourceYaml)) {
        $checkoutWrapper = Get-InlineWrapper $yaml 'SOURCE CHECKOUT INVOCATION'
        $message = $null
        try { & $checkoutWrapper } catch { $message = $_.Exception.Message }
        Assert-Check ($message -match '40-character GitLab commit SHA') 'Actual YAML Get wrapper enters validation before any network/credential use'
    }
    $importPath = Join-Path $root 'import-only-package'
    & { param($Path,$Output) . $Path -PackageDirectory $Output } (Join-Path $packageRoot 'ado/scripts/New-GitLabSourcePackage.ps1') $importPath
    Assert-Check (-not (Test-Path -LiteralPath $importPath)) 'Intentional dot-source helper imports remain non-executing'
} finally {
    foreach ($name in $envNames) { [Environment]::SetEnvironmentVariable($name, $saved[$name]) }
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
}
Write-Host "PowerShell task entrypoint checks: $count passed; ADO runner/server and real GitLab fetch not exercised."
