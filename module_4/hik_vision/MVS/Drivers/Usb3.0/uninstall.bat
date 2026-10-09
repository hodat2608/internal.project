@echo off
set base_dir=%~dp0
%base_dir:~0,2%
pushd %base_dir%
echo %cd%
dpinst.exe /U mvu3v.inf /S
echo delete file
del Flag.ini
@ping 127.0.0.1 -n 2 >nul
echo driver uninstall ok