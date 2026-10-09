@echo off
set base_dir=%~dp0
%base_dir:~0,2%
pushd %base_dir%
echo %cd%
echo driver is installing , please wait for a few minutes ...
certutil.exe -f -addstore "TrustedPublisher" mvu3v.cer 1>nul 2>&1
certutil.exe -f -addstore "TrustedPublisher" mvu3v_Microsoft.cer 1>nul 2>&1
xdevcon.exe rescan
@ping 127.0.0.1 -n 3 >nul
dpinst.exe /F /S
cd.>Flag.ini
@ping 127.0.0.1 -n 2 >nul
echo driver install ok
