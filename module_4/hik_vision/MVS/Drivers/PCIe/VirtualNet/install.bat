@echo off
set base_dir=%~dp0
%base_dir:~0,2%
pushd %base_dir% 1>nul 2>&1

set wintemp=%SYSTEMROOT%\temp
set _LOG_FILE=%wintemp%\MvFGDriverMiniportLog.log

echo [%date% %time%] >> %_LOG_FILE%

:: 导入将证书文件
:: certutil.exe -f -addstore "TrustedPublisher"  MvGigEFrameGrabber_Microsoft.cer >> %_LOG_FILE%
:: certutil.exe -f -addstore "TrustedPublisher" MvGigEFrameGrabber_SHA256.cer >> %_LOG_FILE%
:: certutil.exe -f -addstore "TrustedPublisher" MvGigEFrameGrabber_SHA256_EV.cer >> %_LOG_FILE%

echo. >> %_LOG_FILE%

:: 开启驱动日志记录
call StartTrace.cmd >> %_LOG_FILE%

:: 安装驱动文件并刷新设备列表
MvDriverInstall.exe /i MvVirtualMiniport.inf "MVFGVIRTUALCOMBUS\NICPORT" >> %_LOG_FILE%

::加载配置
LoadSettings.exe >> %_LOG_FILE% 2>&1 

echo. >> %_LOG_FILE%