# Shared by the GitLab jobs and the management-side importer. PowerShell 5.1.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

function Assert-BridgeId {
    param([string]$Value, [string]$Name)
    if ($Value -cnotmatch '^[1-9][0-9]{0,17}$') { throw "Invalid $Name; expected a positive decimal ID." }
}

function Assert-BridgeSha {
    param([string]$Value)
    if ($Value -cnotmatch '^[a-fA-F0-9]{40}$') { throw 'Expected a full 40-character Git commit SHA.' }
}

function Get-BridgeBaseUrl {
    param([string]$Value, [switch]$AllowInsecureHttp)
    $uri = $null
    if (-not [Uri]::TryCreate($Value, [UriKind]::Absolute, [ref]$uri) -or
        $uri.Scheme -notin @('https', 'http') -or $uri.UserInfo -or $uri.Query -or $uri.Fragment) {
        throw 'Service URL must be an absolute HTTP(S) URL without credentials, query or fragment.'
    }
    if ($uri.Scheme -ne 'https' -and -not $AllowInsecureHttp) { throw 'HTTPS is required. HTTP is an explicit isolated-lab exception only.' }
    if ($uri.Scheme -eq 'http') { Write-Warning 'LAB ONLY: HTTP exposes credentials and payloads. Do not use real/production credentials.' }
    return $uri.AbsoluteUri.TrimEnd('/')
}

function Write-BridgeJson {
    param([object]$Value, [string]$Path)
    $fullPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
    $parent = Split-Path -Parent $fullPath
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    [IO.File]::WriteAllText($fullPath, ($Value | ConvertTo-Json -Depth 12), (New-Object Text.UTF8Encoding($false)))
}

function Invoke-BridgeHttp {
    # Fail closed on redirects: never forward either token to an object-storage/SSO host.
    # Bound both JSON and file reads; do not print response bodies or Authorization headers.
    param(
        [string]$Uri, [ValidateSet('GET', 'POST')][string]$Method = 'GET',
        [hashtable]$Headers = @{}, [string]$Body,
        [string]$OutFile, [long]$MaxBytes = 4194304
    )
    $request = [Net.HttpWebRequest]::Create($Uri)
    $request.Method = $Method
    $request.AllowAutoRedirect = $false
    $request.Timeout = 60000
    $request.ReadWriteTimeout = 60000
    foreach ($key in $Headers.Keys) { $request.Headers[$key] = $Headers[$key] }
    $response = $null; $inputStream = $null; $outputStream = $null
    try {
        if ($Method -eq 'POST') {
            $request.ContentType = 'application/json; charset=utf-8'
            $bytes = [Text.Encoding]::UTF8.GetBytes($Body)
            $request.ContentLength = $bytes.Length
            $stream = $request.GetRequestStream()
            try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
        }
        $response = $request.GetResponse()
        if ([int]$response.StatusCode -lt 200 -or [int]$response.StatusCode -ge 300) {
            throw 'Non-success HTTP status; redirects are not supported.'
        }
        if ($response.ContentLength -gt $MaxBytes) { throw 'Response exceeds the configured size limit.' }
        $inputStream = $response.GetResponseStream()
        if ($OutFile) {
            $outputStream = [IO.File]::Open($OutFile, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        } else { $outputStream = New-Object IO.MemoryStream }
        $buffer = New-Object byte[] 65536
        [long]$total = 0
        while (($count = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $total += $count
            if ($total -gt $MaxBytes) { throw 'Response exceeds the configured size limit.' }
            $outputStream.Write($buffer, 0, $count)
        }
        if (-not $OutFile) {
            $text = [Text.Encoding]::UTF8.GetString($outputStream.ToArray())
            try { return ($text | ConvertFrom-Json -ErrorAction Stop) }
            catch { throw 'API returned invalid JSON; response body not logged.' }
        }
    } catch [Net.WebException] {
        $status = 'network/TLS/timeout'
        if ($_.Exception.Response) {
            $status = [string][int]$_.Exception.Response.StatusCode
            $_.Exception.Response.Dispose()
        }
        throw "Bridge HTTP request failed ($status). No response body logged; check endpoint, TLS, ACL and token expiry."
    } finally {
        if ($outputStream) { $outputStream.Dispose() }
        if ($inputStream) { $inputStream.Dispose() }
        if ($response) { $response.Dispose() }
    }
}

function Test-BridgeZip {
    # Inspect only; the importer never extracts or executes developer-produced content.
    param([string]$Path, [long]$MaxExpandedBytes, [int]$MaxEntries = 10000)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($Path)
    try {
        if ($zip.Entries.Count -eq 0 -or $zip.Entries.Count -gt $MaxEntries) { throw 'Empty ZIP or too many ZIP entries.' }
        $seen = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
        $files = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
        [long]$total = 0
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName.Replace('\', '/')
            if (-not $name -or $name.StartsWith('/') -or $name.Contains(':') -or
                $name -match '[\x00-\x1f]' -or $name -match '(^|/)\.\.?(/|$)') { throw 'Unsafe ZIP path.' }
            foreach ($part in $name.TrimEnd('/').Split('/')) {
                if (-not $part -or $part.EndsWith('.') -or $part.EndsWith(' ') -or
                    $part -match '[<>"|?*]' -or $part -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)') {
                    throw 'Unsafe Windows ZIP path.'
                }
            }
            if (-not $seen.Add($name.TrimEnd('/'))) { throw 'Duplicate or case-colliding ZIP path.' }
            if (-not $name.EndsWith('/')) { $files.Add($name) | Out-Null }
            $unixType = (($entry.ExternalAttributes -shr 16) -band 0xF000)
            if ($unixType -ne 0 -and $unixType -notin @(0x8000, 0x4000)) { throw 'Non-regular ZIP entry (for example, symlink).' }
            if (($entry.ExternalAttributes -band 0x400) -ne 0) { throw 'ZIP reparse-point entry is not permitted.' }
            $total += $entry.Length
            if ($total -gt $MaxExpandedBytes) { throw 'Expanded ZIP size exceeds policy.' }
        }
        foreach ($name in $seen) {
            $parts = $name.Split('/')
            for ($index = 1; $index -lt $parts.Count; $index++) {
                if ($files.Contains(($parts[0..($index - 1)] -join '/'))) { throw 'ZIP file/directory collision.' }
            }
        }
    } finally { $zip.Dispose() }
}

function Assert-BridgeZipMarker {
    param([string]$Path, $Manifest)
    $zip = [IO.Compression.ZipFile]::OpenRead($Path)
    $reader = $null
    try {
        $entry = $zip.GetEntry('release.json')
        if (-not $entry -or $entry.Length -gt 65536) { throw 'Missing or oversized root release.json.' }
        $reader = New-Object IO.StreamReader($entry.Open(), [Text.Encoding]::UTF8)
        $buffer = New-Object char[] 65537
        $count = $reader.ReadBlock($buffer, 0, $buffer.Length)
        if ($count -eq 0 -or $count -gt 65536) { throw 'Empty or oversized root release.json.' }
        $marker = (-join $buffer[0..($count - 1)]) | ConvertFrom-Json
        if ([string]$marker.releaseId -cne [string]$Manifest.releaseId -or
            [string]$marker.commitSha -ine [string]$Manifest.commitSha -or
            [string]$marker.projectId -cne [string]$Manifest.projectId -or
            [string]$marker.pipelineId -cne [string]$Manifest.pipelineId -or
            [string]$marker.jobId -cne [string]$Manifest.jobId) { throw 'ZIP release.json provenance mismatch.' }
    } finally {
        if ($reader) { $reader.Dispose() }
        $zip.Dispose()
    }
}
