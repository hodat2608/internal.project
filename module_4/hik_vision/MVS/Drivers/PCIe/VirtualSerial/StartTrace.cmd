@echo off

set base_dir=%~dp0
%base_dir:~0,2%
pushd %base_dir% 1>nul 2>&1


:: FLAGS 定义
set DBG_ALL=                        0xFFFF

:: LEVELS 定义
set TRACE_LEVEL_NONE=               0
set TRACE_LEVEL_CRITICAL=           1
set TRACE_LEVEL_FATAL=              1
set TRACE_LEVEL_ERROR=              2
set TRACE_LEVEL_WARNING=            3
set TRACE_LEVEL_INFORMATION=        4
set TRACE_LEVEL_VERBOSE=            5

:: 相关宏定义
set TRACE_NAME=MvVirtualSerial
set TRACE_LEVEL=%TRACE_LEVEL_WARNING%
set /A TRACE_FLAGS=%DBG_ALL%


:: 关闭之前开启的tracelog
tracelog -stop %TRACE_NAME% >nul 2>&1

:: 开启tracelog %% 表示 %
tracelog    -start %TRACE_NAME% ^
            -guid %TRACE_NAME%.ctl ^
            -f ./%TRACE_NAME%.etl ^
            -cir 64 ^
            -ft 1 ^
            -flag %TRACE_FLAGS% ^
            -level %TRACE_LEVEL% ^
