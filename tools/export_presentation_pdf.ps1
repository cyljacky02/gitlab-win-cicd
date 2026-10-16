param(
    [Parameter(Mandatory=$true)][string]$InputPath,
    [Parameter(Mandatory=$true)][string]$OutputPath
)
# Export an untitled, read-only copy. Never attach to/close/save the user's deck
# and never Quit PowerPoint, since its COM server may share the user's session.
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path $InputPath).Path
$destination = [IO.Path]::GetFullPath($OutputPath)
if ([IO.Path]::GetExtension($destination) -ne '.pdf') { throw 'PDF output required' }
$copy = Join-Path ([IO.Path]::GetTempPath()) (([guid]::NewGuid().ToString()) + '.pptx')
$deck = $null
$app = $null
try {
    Copy-Item -LiteralPath $source -Destination $copy
    $app = New-Object -ComObject PowerPoint.Application
    # ReadOnly=true, Untitled=true, WithWindow=false.
    $deck = $app.Presentations.Open($copy, -1, -1, 0)
    $deck.SaveAs($destination, 32) # ppSaveAsPDF
    Write-Output "Exported $destination"
} finally {
    if ($null -ne $deck) {
        $deck.Close()
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($deck)
    }
    if ($null -ne $app) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($app) }
    Remove-Item -LiteralPath $copy -ErrorAction SilentlyContinue
}
