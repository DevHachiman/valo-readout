@echo off
setlocal
title valo-readout
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

%PY% -c "import aiohttp" >nul 2>&1
if errorlevel 1 (
  echo.
  echo   Manca aiohttp, lo installo adesso. Serve solo la prima volta.
  echo.
  %PY% -m pip install --disable-pip-version-check aiohttp
  if errorlevel 1 (
    echo.
    echo   Installazione non riuscita. Prova a mano con:
    echo       %PY% -m pip install aiohttp
    echo.
    pause
    exit /b 1
  )
  echo.
)

%PY% bridge.py %*
set "CODE=%ERRORLEVEL%"

if not "%CODE%"=="0" (
  echo.
  echo   ---------------------------------------------------------------
  echo   Il ponte si e' chiuso. Il motivo e' scritto qui sopra.
  echo   ---------------------------------------------------------------
  echo.
  pause
)
endlocal
