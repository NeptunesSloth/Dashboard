@echo off
REM Install MayBot as a clickable Windows app: creates Desktop + Start-Menu
REM shortcuts to the launcher. Pass --autostart to also start it on login.
REM
REM   launch\install-windows.bat
REM   launch\install-windows.bat --autostart
setlocal
set "HERE=%~dp0"
set "TARGET=%HERE%maybot.bat"
set "ICON=%HERE%..\maybot_control_center\static\assets\sect\hq.png"

call :mkshortcut "%USERPROFILE%\Desktop\MayBot.lnk"
call :mkshortcut "%APPDATA%\Microsoft\Windows\Start Menu\Programs\MayBot.lnk"

if /i "%~1"=="--autostart" (
  call :mkshortcut "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\MayBot.lnk"
  echo Autostart enabled: MayBot will start on login.
)

echo Done. Double-click the "MayBot" icon on your Desktop to launch the dashboard.
pause
endlocal
exit /b 0

:mkshortcut
REM %1 = full path to the .lnk to create
powershell -NoProfile -Command ^
  "$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut('%~1'); $s.TargetPath='%TARGET%'; $s.WorkingDirectory='%HERE%'; $s.Description='Start the MayBot dashboard'; if (Test-Path '%ICON%') { $s.IconLocation='%ICON%' }; $s.Save()"
echo Created shortcut: %~1
exit /b 0
