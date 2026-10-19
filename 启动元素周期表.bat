@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem ---- 1. Find a Python interpreter (prefer the py launcher) ----
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo [!] Python not found. Please install Python 3.9+ from python.org ^(check Tcl/Tk^).
  pause
  exit /b 1
)

rem ---- 2. Make sure the interpreter has tkinter ----
%PY% -c "import tkinter" 2>nul
if errorlevel 1 (
  echo [!] This Python has no tkinter. Trying to locate another one...
  for /f "delims=" %%i in ('where python 2^>nul') do (
    "%%i" -c "import tkinter" 2>nul && set "PY=%%i" && goto :tk_ok
  )
  echo [!] No Python with tkinter found. Please use a python.org build.
  pause
  exit /b 1
)
:tk_ok

rem ---- 3. Make sure reportlab is installed ----
%PY% -c "import reportlab" 2>nul
if errorlevel 1 (
  echo [*] Installing dependency: reportlab ...
  %PY% -m pip install reportlab
  if errorlevel 1 (
    echo [!] Failed to install reportlab. Run manually:
    echo     %PY% -m pip install reportlab
    pause
    exit /b 1
  )
)

rem ---- 4. Launch ----
%PY% periodictable.py
if errorlevel 1 pause
