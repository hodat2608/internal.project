@echo off
set base_dir=%~dp0
%base_dir:~0,2%
pushd %base_dir% 1>nul 2>&1

set wintemp=%SYSTEMROOT%\temp
set _LOG_FILE=%wintemp%\MvFGDriverLog.log

echo [%date% %time%] >> %_LOG_FILE%

:: 移除证书文件
certutil.exe -delstore "TrustedPublisher" MvVirtualSerial_Microsoft.cer >> %_LOG_FILE%
certutil.exe -delstore "TrustedPublisher" MvVirtualSerial_SHA256.cer >> %_LOG_FILE%
certutil.exe -delstore "TrustedPublisher" MvVirtualSerial_SHA256_EV.cer >> %_LOG_FILE%
echo. >> %_LOG_FILE%

:: 卸载驱动文件
MvDriverInstall.exe /u MvVirtualSerial.inf MVFGVIRTUALCOMBUS\CAMPORT >> %_LOG_FILE%
MvDriverInstall.exe /u MvVirtualSerial.inf MVFGVIRTUALCOMBUS\PSPORT >> %_LOG_FILE%

:: 关闭驱动日志记录
call StopTrace.cmd >> %_LOG_FILE%

echo. >> %_LOG_FILE%