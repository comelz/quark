@echo off
setlocal
set "basepath=%~dp0"
pushd %basepath%
py -3 quark %*
