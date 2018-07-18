@echo off
setlocal
set "basepath=%~dp0"
py -3 %basepath%\quark %*
