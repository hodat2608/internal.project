@echo off

set base_dir=%~dp0
%base_dir:~0,2%
pushd %base_dir% 1>nul 2>&1

:: 清空tracelog缓存，将内容flush至文件
tracelog -flush MvVirtualSerial 1>nul 2>&1
:: 关闭Tracelog
tracelog -stop MvVirtualSerial 1>nul 2>&1