# -*- coding: utf-8 -*-
"""Модуль управления конфигурацией приложения.

Предоставляет модель `AppConfig` на основе Pydantic для загрузки, валидации
и сохранения настроек в JSON-файл. Структура конфигурации включает секции
для COM-порта и файлового источника, а также общие параметры.
"""

# System imports
import json
from pathlib import Path
from typing import Optional

# External imports
from pydantic import BaseModel, ConfigDict, Field

# User imports
from config.com_port_config import ComPortConfig
from config.file_source_config import FileSourceConfig
from config.logger_config import LoggerConfig

#############################################

class AppConfig(BaseModel):
    """Основная конфигурация приложения.

    Содержит настройки источников данных и общие параметры.
    Неизвестные поля в JSON-файле запрещены.

    Attributes:
        calibration (CalibrationConfig): Настройки калибровки.
        com_port (ComPortConfig): Настройки COM-порта.
        file_source (FileSourceConfig): Настройки файлового источника.
        save_dir (Path): Директория для сохранения результатов.
    """

    model_config = ConfigDict(extra='forbid')

    com_port: ComPortConfig = Field(default_factory=ComPortConfig, description="Настройки COM-порта")
    file_source: FileSourceConfig = Field(default_factory=FileSourceConfig, description="Настройки файлового источника")
    logger: LoggerConfig = Field(default_factory=LoggerConfig, description="Настройки логгера")

    save_dir: Path = Field(default_factory=lambda: Path("./results"), description="Директория для сохранения результатов")

    def __init__(self, **data):
        super().__init__(**data)
        self._config_path: Optional[Path] = None

    @classmethod
    def load(cls, config_path: Path) -> 'AppConfig':
        """Загружает конфигурацию из JSON-файла и запоминает путь.

        Если файл не существует, создаёт экземпляр со значениями по умолчанию,
        сохраняет его по указанному пути и возвращает этот экземпляр.

        Args:
            config_path (Path): Путь к JSON-файлу конфигурации.

        Returns:
            AppConfig: Экземпляр конфигурации, связанный с указанным путём.
        """
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            instance = cls(**data)
        else:
            instance = cls()
        instance._config_path = config_path
        if not config_path.exists():
            instance.save()  # сохраняем новый файл с умолчаниями
        return instance

    def save(self, config_path: Optional[Path] = None) -> None:
        """Сохраняет текущую конфигурацию в JSON-файл.

        Если путь не указан, используется путь, сохранённый при загрузке.
        Если сохранённого пути нет, выбрасывается ValueError.

        Args:
            config_path (Path, optional): Путь для сохранения. Если не указан,
                используется внутренний путь из загрузки.

        Raises:
            ValueError: Если не указан путь и внутренний путь не задан.
        """
        if config_path is None:
            config_path = self._config_path
        if config_path is None:
            raise ValueError("Не указан путь для сохранения конфигурации")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.model_dump(mode='json'), f, indent=4, ensure_ascii=False)
