# -*- coding: utf-8 -*-
"""Модуль конфигурации файлового источника данных.

Содержит модель `FileSourceConfig` на основе Pydantic для хранения и валидации
настроек, связанных с чтением данных из файла. Поле `filename` опционально,
что позволяет использовать конфигурацию как шаблон, где отсутствие пути означает,
что файловый источник не задействован.
"""

# System imports
from pathlib import Path
from typing import Optional

# External imports
from pydantic import BaseModel, Field

# User imports

#############################################

class FileSourceConfig(BaseModel):
    """Настройки файлового источника данных.

    Хранит путь к файлу, из которого будут считываться байты.
    Если путь не указан (None), считается, что файловый источник
    не используется.

    Attributes:
        filename (Optional[Path]): Абсолютный или относительный путь к файлу.
            При сериализации в JSON преобразуется в строку.
    """

    filename: Optional[Path] = Field(
        None,
        description="Путь к файлу с данными. Если None или отсутствует, источник не используется."
    )