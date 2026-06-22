@echo off
setlocal EnableExtensions

set "HOST=127.0.0.1"
set "PORT=%~1"
if "%PORT%"=="" set "PORT=8765"
set "ROOT=%~dp0"

echo Restarting game_reverse web server on http://%HOST%:%PORT%/web/index.html
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference = 'Stop';" ^
  "$root = (Resolve-Path '%ROOT%').Path.TrimEnd('\');" ^
  "$port = [int]'%PORT%';" ^
  "$matches = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'game_reverse\.web_server' -and $_.CommandLine -match ('--port\s+' + $port) };" ^
  "$matches | ForEach-Object { Write-Host ('Stopping PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue };" ^
  "Start-Sleep -Milliseconds 800;" ^
  "$proc = Start-Process -FilePath 'python' -ArgumentList @('-m','game_reverse.web_server','--host','%HOST%','--port','%PORT%') -WorkingDirectory $root -WindowStyle Hidden -PassThru;" ^
  "Start-Sleep -Seconds 2;" ^
  "$health = Invoke-RestMethod -Uri ('http://%HOST%:%PORT%/api/health') -TimeoutSec 5;" ^
  "Write-Host ('Started PID ' + $proc.Id);" ^
  "Write-Host ('Health: ' + $health.status);" ^
  "Write-Host 'URL: http://%HOST%:%PORT%/web/index.html';"

if errorlevel 1 (
  echo.
  echo Restart failed.
  exit /b 1
)

echo.
echo Done.
endlocal
