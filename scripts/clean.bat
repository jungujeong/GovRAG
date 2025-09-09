@echo off
REM Windows cleanup script

echo Cleaning up generated files...
if exist "data\index\*" rmdir /s /q "data\index" 2>nul
if exist "data\chroma\*" rmdir /s /q "data\chroma" 2>nul
if exist "__pycache__" rmdir /s /q "__pycache__" 2>nul
if exist ".pytest_cache" rmdir /s /q ".pytest_cache" 2>nul

REM Recreate directories
mkdir "data\index" 2>nul
mkdir "data\chroma" 2>nul

REM Delete Python cache files
for /r . %%i in (*.pyc) do del "%%i" 2>nul

echo Cleanup complete!