@echo off
REM Windows index backup script

echo Creating index backup...
cd backend
python utils\index_manager.py backup
cd ..
echo Backup complete!