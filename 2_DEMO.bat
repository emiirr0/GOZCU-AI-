@echo off
setlocal
call "%~dp0_ortam.bat"
if not defined PY ( pause & exit /b 1 )
%PY% -m gozcu demo
if exist "cikti\demo\rapor.html" start "" "cikti\demo\rapor.html"
pause
