@echo off
echo stop LogServer...
sc stop MvLogServer
@ping 127.0.0.1 -n 3 >nul

echo delete LogServer...
sc delete MvLogServer

@ping 127.0.0.1 -n 3 >nul

set service_name=MvFGLogServer
sc query %service_name% >nul
if %errorlevel% equ 0 (
    echo delete MvFGLogServer...
    sc stop MvFGLogServer
    sc delete MvFGLogServer
) else (
    echo MvFGLogServer not exist.
)

set base_dir=%~dp0
%base_dir:~0,2%
pushd %base_dir%
echo %cd%

del Path.ini