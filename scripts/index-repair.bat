@echo off
REM Windows index repair script

echo Repairing corrupted indexes...
cd backend
python utils\index_manager.py repair
cd ..
echo Repair complete!