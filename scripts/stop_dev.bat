@echo off
echo Stopping MapleTrade Development Environment...

echo.
echo Stopping Docker services...
docker-compose down

echo.
echo Development environment stopped.
pause