@echo off
REM Windows index cleanup script

echo Cleaning old backups...
cd backend
python utils\index_manager.py clean
cd ..
echo Cleanup complete!