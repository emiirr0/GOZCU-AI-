@echo off
setlocal
call "%~dp0_ortam.bat"
if not defined PY ( pause & exit /b 1 )
%PY% -m gozcu incele
if exist "cikti\rapor.html" start "" "cikti\rapor.html"
pause
