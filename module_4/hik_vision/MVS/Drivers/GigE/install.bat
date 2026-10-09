@echo off
set base_dir=%~dp0
%base_dir:~0,2%
pushd %base_dir% 1>nul 2>&1
echo %cd%

certutil.exe -f -addstore "TrustedPublisher"  neugevsf_Microsoft.cer 1>nul 2>&1
certutil.exe -f -addstore "TrustedPublisher" neugevsf_SHA256.cer 1>nul 2>&1
certutil.exe -f -addstore "TrustedPublisher" neugevsf_SHA256_EV.cer 1>nul 2>&1

GigEVisionDriverTool.exe -l .\neugevsf.inf -u ms_neugevfilter 1>nul 2>&1
GigEInst.exe /u neugevsf.inf 1>nul 2>&1

SETLOCAL ENABLEEXTENSIONS
SETLOCAL ENABLEDELAYEDEXPANSION
takeown /f "%systemroot%\system32\DriverStore\FileRepository\neugevsf*" 1>nul 2>&1 && icacls "%systemroot%\system32\DriverStore\FileRepository\neugevsf*" /grant administrators:F 1>nul 2>&1
takeown /f "%systemroot%\system32\DriverStore\FileRepository\neugevsf*" /r /d y 1>nul 2>&1 && icacls "%systemroot%\system32\DriverStore\FileRepository\neugevsf*" /grant administrators:F /t 1>nul 2>&1

dir %systemroot%\system32\DriverStore\FileRepository\neugevsf* /b >"%cd%\dellist.txt" 2>nul
for /F "usebackq delims=" %%A in ("%cd%\dellist.txt") do (
    RD /S /q %systemroot%\system32\DriverStore\FileRepository\%%A
) 1>nul 2>&1

DEL "%cd%\dellist.txt" 1>nul 2>&1
ENDLOCAL

xcopy "%cd%\neugevfilter.sys" "%systemroot%\system32\drivers\" /y 1>nul 2>&1

GigEVisionDriverTool.exe -l "%cd%\neugevsf.inf" -i HKR_neuGEVFilter

@ping 127.0.0.1 -n 3 1>nul 2>&1