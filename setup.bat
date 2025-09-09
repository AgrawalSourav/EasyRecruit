@echo off
echo Setting up Job Matching System...

REM Create Python virtual environment
cd backend
python -m venv venv
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt

echo Backend dependencies installed!

REM Install frontend dependencies
cd ..\frontend
npm install

echo Frontend dependencies installed!
echo Setup complete!
echo.
echo To start the system:
echo 1. Backend: cd backend && venv\Scripts\activate.bat && python app.py
echo 2. Frontend: cd frontend && npm start

"curl -X POST http://localhost:5000/debug/clear_database"
