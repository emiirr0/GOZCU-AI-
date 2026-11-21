@echo off
setlocal
call "%~dp0_ortam.bat"
if not defined PY ( pause & exit /b 1 )
%PY% -m gozcu canli 0 otomatik

pause
