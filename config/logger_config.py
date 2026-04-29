# -*- coding: utf-8 -*-
"""Модуль конфигурации логгера.

Содержит модель `LoggerConfig` для настройки файлового и консольного логирования.
"""

# System imports
import logging
from pathlib import Path

# External imports
from pydantic import BaseModel, Field, field_validator

# User imports

#############################################

class LoggerConfig(BaseModel):
    """Настройки логгера приложения.

    Attributes:
        log_dir (Path):        Директория для сохранения логов. По умолчанию ".logs".
        log_filename (str):    Имя файла лога. По умолчанию ".logger.log".
        log_format (str):      Строка форматирования логов.
        date_format (str):     Формат даты в логах.
        log_level (int):       Уровень логирования (logging.DEBUG, INFO и т.д.).
        use_file (bool):       Включить запись логов в файл. По умолчанию True.
        use_console (bool):    Включить вывод логов в консоль. По умолчанию True.
    """

    log_dir: Path = Field(Path(__file__).parent.parent / ".logs",
                          description='Директория для логов')
    log_filename: str  = Field('.logger.log', description='Имя файла лога')
    log_format: str  = Field(
        '%(asctime)s - %(levelname)s - %(name)s:\n%(message)s',
        description='Строка форматирования логов'
    )
    date_format: str = Field('%Y-%m-%d %H:%M:%S', description='Формат даты')
    log_level: int = Field(logging.DEBUG, description='Уровень логирования')
    use_file: bool = Field(True, description='Запись логов в файл')
    use_console: bool = Field(True, description='Вывод логов в консоль')

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v: int) -> int:
        allowed = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]
        if v not in allowed:
            raise ValueError(f'Недопустимый уровень логирования: {v}. Допустимые: {allowed}')
        return v
