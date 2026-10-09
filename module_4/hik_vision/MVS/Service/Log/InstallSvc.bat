@echo off
set base_dir=%~dp0
%base_dir:~0,2%
pushd %base_dir%
echo %cd%

cd.>Path.ini
echo %systemroot%\Temp>Path.ini

echo install LogServer...
MvLogServer.exe install

@Xcopy LogServer.ini %systemroot%\Temp\MvSDKLog\  /y

pushd %systemroot%\system32
echo %cd%

echo start LogServer...
sc start MvLogServer

@ping 127.0.0.1 -n 3 >nul