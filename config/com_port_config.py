# -*- coding: utf-8 -*-
"""Модуль конфигурации COM-порта.

Содержит модель `ComPortConfig` на основе Pydantic для хранения и валидации
настроек последовательного порта. Все поля опциональны, что позволяет
использовать конфигурацию как шаблон с возможностью частичного заполнения.
"""

# System imports
from typing import Optional

# External imports
from pydantic import BaseModel, Field, field_validator

# User imports

#############################################

class ComPortConfig(BaseModel):
    """Настройки COM-порта.

    Используется для хранения параметров com порта.

    Attributes:
        name (Optional[str]): Имя порта (например, 'COM3' или '/dev/ttyUSB0').
        desc (Optional[str]): Описание порта (может быть пустым).
        hwid (Optional[str]): Аппаратный идентификатор (USB VID/PID и т.п.).
        baudrate (Optional[int]): Скорость передачи данных. Допустимые значения:
            9600, 57600, 115200, 230400, 460800, 921600.
    """

    name: Optional[str] = None
    desc: Optional[str] = None
    hwid: Optional[str] = None
    baudrate: Optional[int] = Field(
        None,
        description="Скорость передачи данных (допустимые значения: 9600, 57600, 115200, 230400, 460800, 921600)"
    )

    @field_validator('baudrate')
    @classmethod
    def _validate_baudrate(cls, v: int) -> int:
        allowed = [None, ] + [9600, 57600, 115200, 230400, 460800, 921600]
        if v not in allowed:
            raise ValueError(f'baudrate должен быть одним из {allowed}')
        return v
