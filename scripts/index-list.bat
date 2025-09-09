@echo off
REM Windows index list script

echo Listing available backups...
cd backend
python utils\index_manager.py list
cd ..