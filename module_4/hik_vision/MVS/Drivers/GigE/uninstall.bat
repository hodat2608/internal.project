@echo off
set base_dir=%~dp0
%base_dir:~0,2%
pushd %base_dir% 1>nul 2>&1
echo %cd%

SETLOCAL ENABLEEXTENSIONS
SETLOCAL ENABLEDELAYEDEXPANSION

:: 判断驱动是否已经安装
sc query neugevfilter 1>nul 2>&1
if "%errorlevel%" == "1060" (
    echo Driver is not installed
    exit /b %errorlevel%
)

:: 卸载驱动
GigEVisionDriverTool.exe -l .\neugevsf.inf -u HKR_neuGEVFilter
GigEInst.exe /u neugevsf.inf

takeown /f "%systemroot%\system32\DriverStore\FileRepository\neugevsf*" 1>nul 2>&1 && icacls "%systemroot%\system32\DriverStore\FileRepository\neugevsf*" /grant administrators:F 1>nul 2>&1
takeown /f "%systemroot%\system32\DriverStore\FileRepository\neugevsf*" /r /d y 1>nul 2>&1 && icacls "%systemroot%\system32\DriverStore\FileRepository\neugevsf*" /grant administrators:F /t 1>nul 2>&1

dir %systemroot%\system32\DriverStore\FileRepository\neugevsf* /b >"%cd%\dellist.txt" 2>nul
for /F "usebackq delims=" %%A in ("%cd%\dellist.txt") do (
    RD /S /q %systemroot%\system32\DriverStore\FileRepository\%%A
) 1>nul 2>&1

DEL "%cd%\dellist.txt" 1>nul 2>&1

:: 判断驱动是否正常卸载
for /f "skip=3 tokens=1,2,3*" %%i in ('sc query neugevfilter') do (
    set state=%%i
    set value=%%k
    if "STATE" == "!state!" (
        if not "%%k" == "4" (
            echo ERROR: Need to reboot
            exit /b !value!
        )
    )
)

ENDLOCAL

@ping 127.0.0.1 -n 3 1>nul 2>&1