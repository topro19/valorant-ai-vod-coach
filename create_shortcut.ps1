$wsh = New-Object -ComObject WScript.Shell
$shortcutPath = [System.IO.Path]::Combine([System.Environment]::GetFolderPath('Desktop'), 'VALORANT AI VOD Coach.lnk')
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "d:\uwu\valorant-vod-coach\Launch Coach.bat"
$shortcut.WorkingDirectory = "d:\uwu\valorant-vod-coach"
$shortcut.Description = "VALORANT AI VOD Coach - Strict Player-Lock Analysis"
$shortcut.Save()
Write-Output "Shortcut created at $shortcutPath"
