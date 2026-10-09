@echo off
set base_dir=%~dp0
%base_dir:~0,2%
pushd %base_dir% 1>nul 2>&1

set wintemp=%SYSTEMROOT%\temp
set _LOG_FILE=%wintemp%\MvFGDriverLog.log

echo [%date% %time%] >> %_LOG_FILE%

:: 导入将证书文件
certutil.exe -f -addstore "TrustedPublisher" MvVirtualSerial_Microsoft.cer >> %_LOG_FILE%
certutil.exe -f -addstore "TrustedPublisher" MvVirtualSerial_SHA256.cer >> %_LOG_FILE%
certutil.exe -f -addstore "TrustedPublisher" MvVirtualSerial_SHA256_EV.cer >> %_LOG_FILE%
echo. >> %_LOG_FILE%

:: 开启驱动日志记录
call StartTrace.cmd >> %_LOG_FILE%

:: 安装驱动文件并刷新设备列表
MvDriverInstall.exe /i MvVirtualSerial.inf MVFGVIRTUALCOMBUS\CAMPORT >> %_LOG_FILE%
MvDriverInstall.exe /i MvVirtualSerial.inf MVFGVIRTUALCOMBUS\PSPORT >> %_LOG_FILE%

echo. >> %_LOG_FILE%