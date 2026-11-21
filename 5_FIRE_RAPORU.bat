@echo off
setlocal
call "%~dp0_ortam.bat"
if not defined PY ( pause & exit /b 1 )
%PY% -m gozcu rapor
if exist "cikti\fire_raporu.html" start "" "cikti\fire_raporu.html"
pause
