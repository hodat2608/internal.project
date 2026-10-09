@echo off
set base_dir=%~dp0
%base_dir:~0,2%
pushd %base_dir% 1>nul 2>&1

set wintemp=%SYSTEMROOT%\temp
set _LOG_FILE=%wintemp%\MvFGDriverLog.log

echo [%date% %time%] >> %_LOG_FILE%

:: 导入将证书文件
certutil.exe -f -addstore "TrustedPublisher" MvXoFFrameGrabber_Microsoft.cer >> %_LOG_FILE%
certutil.exe -f -addstore "TrustedPublisher" MvXoFFrameGrabber_SHA256.cer >> %_LOG_FILE%
certutil.exe -f -addstore "TrustedPublisher" MvXoFFrameGrabber_SHA256_EV.cer >> %_LOG_FILE%

echo. >> %_LOG_FILE%

:: 开启驱动日志记录
call StartTrace.cmd >> %_LOG_FILE%

:: 安装驱动文件并刷新设备列表
MvDriverInstall.exe /i MvXoFFrameGrabber.inf "PCI\VEN_10EE&DEV_7028&SUBSYS_862710EE&REV_00" >> %_LOG_FILE%
if ERRORLEVEL 0 (
	MvDriverInstall.exe /r MvXoFFrameGrabber.inf "PCI\VEN_10EE&DEV_7028&SUBSYS_864710EE&REV_00" >> %_LOG_FILE%
	MvDriverInstall.exe /r MvXoFFrameGrabber.inf "PCI\VEN_10EE&DEV_8038&SUBSYS_864710EE&REV_00" >> %_LOG_FILE%
	MvDriverInstall.exe /r MvXoFFrameGrabber.inf "PCI\VEN_10EE&DEV_8034&SUBSYS_862710EE&REV_00" >> %_LOG_FILE%
	MvDriverInstall.exe /r MvXoFFrameGrabber.inf "PCI\VEN_10EE&DEV_8034&SUBSYS_864710EE&REV_00" >> %_LOG_FILE%
	MvDriverInstall.exe /r MvXoFFrameGrabber.inf "PCI\VEN_10EE&DEV_8038&SUBSYS_878710EE&REV_00" >> %_LOG_FILE%
	MvDriverInstall.exe /r MvXoFFrameGrabber.inf "PCI\VEN_10EE&DEV_8038&SUBSYS_874710EE&REV_00" >> %_LOG_FILE%
)

echo. >> %_LOG_FILE%