@echo off
setlocal
call "%~dp0_ortam.bat"
if not defined PY ( pause & exit /b 1 )
%PY% -m gozcu simulasyon 25
if exist "cikti\simulasyon\rapor.html" start "" "cikti\simulasyon\rapor.html"
pause
