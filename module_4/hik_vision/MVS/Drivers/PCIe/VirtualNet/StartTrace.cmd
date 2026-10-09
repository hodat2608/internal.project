@echo off

set base_dir=%~dp0
%base_dir:~0,2%
pushd %base_dir% 1>nul 2>&1


:: FLAGS 定义
set DBG_ALL=                        0xFFFFF
set DBG_PNP=                        0x1
set DBG_CONTROL=                    0x2
set DBG_ADAPTER=                    0x4
set DBG_ISR=                        0x8
set DBG_READ=                       0x10
set DBG_WRITE=                      0x20
set DBG_DMA=                        0x40
set DBG_SGDMA=                      0x80
set DBG_CBDMA=                      0x100
set DBG_TIME=                       0x200
set DBG_DUMP=                       0x400
set DBG_TEST=                       0x800
set DBG_RSS=                        0x1000
set DBG_REG=                        0x2000
set DBG_DATA=                       0x4000
set DBG_HAL=                        0x8000
set DBG_VMQ=                        0x10000


:: LEVELS 定义
set TRACE_LEVEL_NONE=               0
set TRACE_LEVEL_CRITICAL=           1
set TRACE_LEVEL_FATAL=              1
set TRACE_LEVEL_ERROR=              2
set TRACE_LEVEL_WARNING=            3
set TRACE_LEVEL_INFORMATION=        4
set TRACE_LEVEL_VERBOSE=            5

:: 相关宏定义
set TRACE_NAME=MvVirtualMiniport
set TRACE_LEVEL=%TRACE_LEVEL_WARNING%
set /A TRACE_FLAGS=%DBG_ALL%


:: 关闭之前开启的tracelog
tracelog -stop %TRACE_NAME% >nul 2>&1

:: 开启tracelog %% 表示 %
tracelog    -start %TRACE_NAME% ^
            -guid MvVirtualMiniport.ctl ^
            -f ./MvVirtualMiniport.etl ^
            -cir 64 ^
            -ft 1 ^
            -flag %TRACE_FLAGS% ^
            -level %TRACE_LEVEL% ^
