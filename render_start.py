#!/usr/bin/env python3
"""
Файл для запуска приложения на Render
"""
import os
from server import app

# Для gunicorn
if __name__ == '__main__':
    # Получаем порт из переменной окружения Render или используем 5000 по умолчанию
    port = int(os.environ.get('PORT', 5000))
    
    # Запускаем приложение
    app.run(host='0.0.0.0', port=port, debug=False)
