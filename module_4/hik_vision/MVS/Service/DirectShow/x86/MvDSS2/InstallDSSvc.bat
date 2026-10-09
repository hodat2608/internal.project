@echo off
set base_dir=%~dp0
%base_dir:~0,2%
pushd %base_dir%
echo %cd%

echo install DSServer...

MvDSServer.exe install


pushd %systemroot%\system32
echo %cd%

echo start DSServer...
sc start MvDSServer

@ping 127.0.0.1 -n 3 >nul
