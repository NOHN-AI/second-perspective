Add-Type -AssemblyName System.IO.Compression.FileSystem
$vsix = $args[0]
$zip = [System.IO.Compression.ZipFile]::OpenRead($vsix)
$zip.Entries | Where-Object { $_.FullName -notmatch "node_modules" } | ForEach-Object {
    "{0,-65} {1,10}" -f $_.FullName, $_.Length
}
$zip.Dispose()
