@echo off
set base_dir=%~dp0
%base_dir:~0,2%
pushd %base_dir% 1>nul 2>&1

set wintemp=%SYSTEMROOT%\temp
set _LOG_FILE=%wintemp%\MvFGDriverLog.log

echo [%date% %time%] >> %_LOG_FILE%

:: 移除证书文件
certutil.exe -delstore "TrustedPublisher"  MvCmlFrameGrabber_Microsoft.cer >> %_LOG_FILE%
certutil.exe -delstore "TrustedPublisher" MvCmlFrameGrabber_SHA256.cer >> %_LOG_FILE%
certutil.exe -delstore "TrustedPublisher" MvCmlFrameGrabber_SHA256_EV.cer >> %_LOG_FILE%

echo. >> %_LOG_FILE%

::卸载驱动文件
MvDriverInstall.exe /u MvCmlFrameGrabber.inf "PCI\VEN_10EE&DEV_7024&SUBSYS_312710EE&REV_00" >> %_LOG_FILE%

:: 关闭驱动日志记录
call StopTrace.cmd >> %_LOG_FILE%
echo. >> %_LOG_FILE%