#!/bin/bash
# Двойной щелчок в macOS открывает этот файл как программу.
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
    exec python3 main.py
fi
echo "Не найден python3. Установите его с https://www.python.org/downloads/"
read -n 1 -s -r -p "Нажмите любую клавишу…"
