@echo off
rem ---------------------------------------------------------------------------
rem Informe automatico de datos de la EIA (ver datos\README.md)
rem
rem Esto es lo que ejecuta el Programador de tareas de Windows. Para darlo de
rem alta una sola vez, en una consola (cmd) como usuario normal:
rem
rem   schtasks /create /tn "Instituto - informe EIA" /tr "C:\Users\User\Downloads\instituto-app\instituto-app\datos\correr_semanal.bat" /sc weekly /d MON /st 07:30
rem
rem Para probarlo ya mismo:        schtasks /run /tn "Instituto - informe EIA"
rem Para ver cuando corrio:        schtasks /query /tn "Instituto - informe EIA" /v /fo list
rem Para darlo de baja:            schtasks /delete /tn "Instituto - informe EIA" /f
rem
rem El resultado de cada corrida queda en datos\semanal.log.
rem ---------------------------------------------------------------------------
cd /d "%~dp0.."
if not exist "venv\Scripts\python.exe" (
  echo No se encontro venv\Scripts\python.exe en %cd%
  exit /b 1
)
"venv\Scripts\python.exe" "datos\semanal.py" --silencioso
exit /b %errorlevel%
