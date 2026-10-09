:: 控制PS调试串口是否打开
:: 不带参数，默认打开
:: 带参数：0为关闭，其他值打开
@echo off & cd /d "%~dp0"

setlocal ENABLEEXTENSIONS
setlocal ENABLEDELAYEDEXPANSION

if not "%1" == "" (
    set /A PS_DEBUG=%1
) else (
    set /A PS_DEBUG=1
)

if %PS_DEBUG% EQU 0 (
    set PS_DEBUG_STR=OFF
) else (
    set PS_DEBUG_STR=ON
)

set ROOT_KEY="HKLM\SYSTEM\CurrentControlSet\Enum\PCI"
set wintemp=%SYSTEMROOT%\temp
set _LOG_FILE=%wintemp%\MvFGDriverLog.log

REM Find Config\
reg query %ROOT_KEY% /f "Config" /s /k /e > temp.txt

REM REM Add PsDebugPortOn and set its value to 1
for /F "usebackq delims=" %%A in ("%cd%\temp.txt") do (
    set "tmp=%%A"
    if "!tmp:~0,18!" == "HKEY_LOCAL_MACHINE" (
        reg ADD "!tmp!" /v PsDebugPortOn /t REG_DWORD /d %PS_DEBUG% /f 1>nul 2>&1
        echo Ps debug serial of [!tmp:~53,-27!] is turned %PS_DEBUG_STR%
    )
)

DEL "%cd%\temp.txt" 1>nul 2>&1
endlocal 
pause