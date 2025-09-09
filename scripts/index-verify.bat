@echo off
REM Windows index verification script

echo Verifying index integrity...
cd backend
python utils\index_manager.py verify
cd ..
echo Verification complete!