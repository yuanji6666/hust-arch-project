@echo off
rem ============================================================
rem  Logisim launcher for the RISC-V course project
rem  Double-click to open Logisim, then use File > Open for a .circ
rem  Or drag a .circ file onto this .cmd to open it directly
rem ============================================================
setlocal

set "JAR=%~dp0logisim.jar"

set "JAVA="
if exist "C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot\bin\javaw.exe" set "JAVA=C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot\bin\javaw.exe"
if not defined JAVA if defined JAVA_HOME if exist "%JAVA_HOME%\bin\javaw.exe" set "JAVA=%JAVA_HOME%\bin\javaw.exe"
if not defined JAVA for /f "delims=" %%i in ('where javaw 2^>nul') do if not defined JAVA set "JAVA=%%i"

if not defined JAVA (
  echo [ERROR] Java not found. Install Eclipse Temurin JDK 17:
  echo         https://adoptium.net/temurin/releases/?version=17
  pause
  exit /b 1
)

if not exist "%JAR%" (
  echo [ERROR] logisim.jar not found next to this script:
  echo         %JAR%
  pause
  exit /b 1
)

rem Logisim resolves jar#... library references by looking in the .circ file's
rem own directory first, then in its *current working directory*. If neither
rem has cs3410.jar / riscv-probe.jar it pops a file-chooser dialog on every
rem open. Pinning the working directory here makes the root copies win.
cd /d "%~dp0"
if not exist "cs3410.jar" echo [WARN] cs3410.jar not found in "%~dp0" - Logisim may ask for it.
if not exist "riscv-probe.jar" echo [WARN] riscv-probe.jar not found in "%~dp0" - Logisim may ask for it.

start "" "%JAVA%" -jar "%JAR%" %*
endlocal