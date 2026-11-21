@echo off
setlocal
call "%~dp0_ortam.bat"
if not defined PY ( pause & exit /b 1 )
%PY% -m gozcu ornek
if exist "cikti\ornek\cikti\rapor.html" start "" "cikti\ornek\cikti\rapor.html"
pause
