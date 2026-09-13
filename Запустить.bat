@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem Ищем Python и запускаем окно без чёрной консоли.
where pythonw >nul 2>nul && (start "" pythonw "main.py" & exit /b)
where pyw     >nul 2>nul && (start "" pyw -3 "main.py" & exit /b)
where py      >nul 2>nul && (start "" py -3 "main.py" & exit /b)
where python  >nul 2>nul && (start "" python "main.py" & exit /b)

echo.
echo Не найден Python.
echo Скачайте его с https://www.python.org/downloads/
echo и при установке поставьте галочку "Add Python to PATH".
echo.
pause
