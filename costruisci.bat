@echo off
rem
setlocal
title costruisci valo-readout
cd /d "%~dp0"

set "PY=python"
where py >nul 2>&1
if not errorlevel 1 set "PY=py"

%PY% --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo   Python non risulta installato.
  echo   Prendilo da https://www.python.org/downloads/ e durante
  echo   l'installazione lascia spuntato "Add Python to PATH".
  echo.
  pause
  exit /b 1
)

echo.
echo   Installo cio' che serve per costruire ^(solo la prima volta^)...
echo.
%PY% -m pip install --disable-pip-version-check -r requirements.txt pyinstaller
if errorlevel 1 (
  echo.
  echo   Installazione non riuscita. Senza queste non si puo' costruire.
  echo.
  pause
  exit /b 1
)

echo.
echo   Costruisco. Ci vuole un minuto.
echo.
%PY% -m PyInstaller --onefile --noconsole --name valo-readout ^
  --icon valo-readout.ico --add-data "index.html;." --noconfirm bridge.py
if errorlevel 1 (
  echo.
  echo   Costruzione non riuscita. Il motivo e' scritto qui sopra.
  echo.
  pause
  exit /b 1
)

echo.
echo   ---------------------------------------------------------------
echo   Fatto:  %CD%\dist\valo-readout.exe
echo   Questo l'hai costruito tu. Usa questo, non quello di altri.
echo   ---------------------------------------------------------------
echo.
pause
endlocal
