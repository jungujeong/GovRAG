@echo off
REM Windows index restore script

echo Restoring index from backup...
cd backend
python utils\index_manager.py restore
cd ..
echo Restore complete!