@echo off
echo Starting MapleTrade Development Environment...

echo.
echo Starting Docker services...
docker-compose up -d redis

echo.
echo Waiting for services to be ready...
timeout /t 5

echo.
echo Activating virtual environment...
call venv\Scripts\activate

echo.
echo Starting Django development server...
python manage.py runserver

pause