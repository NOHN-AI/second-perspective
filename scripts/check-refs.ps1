$root = $args[0]
Get-ChildItem $root -Recurse -File -Filter "*.ts*" | Select-String -Pattern "statusProvider|historyProvider|webviewPanel|refreshHistory" | ForEach-Object {
    Write-Host ("{0}:{1}: {2}" -f $_.Path, $_.LineNumber, $_.Line)
}
Write-Host "---DONE---"
