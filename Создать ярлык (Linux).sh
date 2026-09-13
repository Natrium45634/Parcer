#!/bin/bash
# Создаёт значок запуска в меню приложений и на рабочем столе.
HERE="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Рабочий стол")"
FILE_BODY="[Desktop Entry]
Type=Application
Name=Хронист
GenericName=Генератор фэнтезийных историй
Comment=Детерминированный генератор истории фэнтезийного мира
Exec=python3 \"$HERE/main.py\"
Path=$HERE
Icon=$HERE/assets/icon.png
Terminal=false
Categories=Game;Utility;
"
mkdir -p "$HOME/.local/share/applications"
printf '%s' "$FILE_BODY" > "$HOME/.local/share/applications/chronicler.desktop"
chmod +x "$HOME/.local/share/applications/chronicler.desktop"
if [ -d "$DESKTOP_DIR" ]; then
    printf '%s' "$FILE_BODY" > "$DESKTOP_DIR/Хронист.desktop"
    chmod +x "$DESKTOP_DIR/Хронист.desktop"
    gio set "$DESKTOP_DIR/Хронист.desktop" metadata::trusted true 2>/dev/null
fi
echo "Готово: значок «Хронист» добавлен в меню приложений."
