@echo off
setlocal
call "%~dp0_ortam.bat"
if not defined PY ( pause & exit /b 1 )
if exist ".venv\Scripts\python.exe" goto kur
echo Proje icin ayri bir Python ortami (.venv) olusturuluyor...
%PY% -m venv .venv
if errorlevel 1 (
  echo .venv olusturulamadi; kutuphaneler kullanici klasorune kurulacak.
  %PY% -m pip install --user -r requirements.txt
  goto bitti
)
:kur
echo Kutuphaneler kuruluyor (OpenCV, NumPy)... internet gerekir, birkac dakika surebilir.
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
:bitti
if errorlevel 1 (
  echo.
  echo  KURULUM BASARISIZ. Internet baglantisini kontrol edip tekrar dene.
  pause
  exit /b 1
)
echo.
echo  Kurulum tamam. Simdi 2_DEMO.bat ya da 0_ORNEK_DENE.bat calistirabilirsin.
call "%~dp0_ortam.bat"
%PY% -m gozcu kontrol
pause
