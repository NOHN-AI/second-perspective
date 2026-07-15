Set-Location $args[0]
$log = & npx vsce package --no-git-tag-version 2>&1
$log | Out-File -FilePath "$args[0]\package.log" -Encoding utf8
$log | ForEach-Object { Write-Host $_ }
