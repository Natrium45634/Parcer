@echo off
chcp 65001 >nul
set "HERE=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$shell = New-Object -ComObject WScript.Shell;" ^
 "$link = $shell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Хронист.lnk');" ^
 "$exe = (Get-Command pythonw -ErrorAction SilentlyContinue).Source;" ^
 "if (-not $exe) { $exe = (Get-Command python -ErrorAction SilentlyContinue).Source }" ^
 "if (-not $exe) { Write-Host 'Python не найден'; exit 1 }" ^
 "$link.TargetPath = $exe;" ^
 "$link.Arguments = '\"%HERE%main.py\"';" ^
 "$link.WorkingDirectory = '%HERE%';" ^
 "$link.IconLocation = '%HERE%assets\icon.ico';" ^
 "$link.Description = 'Хронист — генератор фэнтезийных историй';" ^
 "$link.Save(); Write-Host 'Ярлык создан на рабочем столе.'"
echo.
pause
