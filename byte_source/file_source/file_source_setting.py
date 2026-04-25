# -*- coding: utf-8 -*-
"""Модуль для настройки файлового источника данных.

Предоставляет класс `AsyncFileSourceSetting` — фабрику, унаследованную от
`AsyncBytesSourceFactory`. Управляет выбором файла с лог-данными через
глобальную конфигурацию приложения (`config`). Позволяет использовать
сохранённый путь из конфига или запросить новый у пользователя, а затем
сохраняет выбранный путь обратно в конфигурацию.
"""

# System imports
from pathlib import Path
from typing import Optional

# External imports

# User imports
from config import config
from logger import app_logger
from utils import confirm_from_console
from byte_source.bytes_source import AsyncBytesSource, AsyncBytesSourceFactory
from byte_source.file_source.file_source import FileSource

#########################

_logger = app_logger.get_logger('App.FileSource')

# ------------------------------------------


class AsyncFileSourceSetting(AsyncBytesSourceFactory):
    """Фабрика для настройки файлового источника через консоль.

    Настройка пути к файлу собирается в `configure_source()` из кэша
    конфига или через интерактивный ввод. Создание готового источника
    выполняется в `get_bytes_source()`. Если `get_bytes_source()` вызван
    без предварительной настройки — `configure_source()` вызывается
    автоматически.

    Пример использования:
        setting = AsyncFileSourceSetting()
        setting.configure_source()          # явный вызов
        source = setting.get_bytes_source()

        # или ленивая настройка:
        source = AsyncFileSourceSetting().get_bytes_source()

        async with source:
            byte = await source.read_byte()
    """

    def __init__(self) -> None:
        self._filename: Optional[Path] = None

    def configure_source(self) -> None:
        """Собирает путь к файлу: из кэша конфига или через консоль.

        Если в `config.file_source.filename` указан путь и файл существует,
        пользователю предлагается подтвердить его использование. При отказе
        пользователя или отсутствии кэша — запускает интерактивный ввод пути.
        """
        self._load_from_config()

    def get_bytes_source(self) -> AsyncBytesSource:
        """Создание FileSource с выбранным путём.

        Если источник не был настроен — вызывает `configure_source()`
        автоматически.

        Returns:
            AsyncBytesSource: Готовый к использованию файловый источник.
        """
        if self._filename is None:
            _logger.debug('Источник не настроен — ленивый вызов configure_source()')
            self.configure_source()

        _logger.debug(f'Создан FileSource: {self._filename}')
        return FileSource(self._filename)

    def _load_from_config(self) -> None:
        """Пытается загрузить путь из конфига, если файл существует.

        Если в `config.file_source.filename` указан путь и файл существует,
        пользователю предлагается подтвердить его использование.
        При подтверждении путь сохраняется в `_filename` и метод завершается.
        Иначе вызывается `_load_filename_from_console()` для ручного ввода.
        """
        cached_path = config.file_source.filename

        if cached_path and cached_path.is_file():
            print(f'Использовать файл "{cached_path}" в качестве источника данных?')
            if confirm_from_console():
                self._filename = cached_path
                _logger.debug(f'Используется сохранённый путь: {self._filename}')
                return

        # Если нет сохранённого пути, файл не найден или пользователь отказался
        self._load_filename_from_console()

    def _load_filename_from_console(self) -> None:
        """Запрашивает путь к файлу у пользователя, проверяет существование и сохраняет в конфиг.

        Выводит приглашение для ввода абсолютного пути к файлу.
        Введённая строка очищается от кавычек и преобразуется в объект `Path`.
        Если файл существует:
            - сохраняет нормализованный путь в `_filename`
            - обновляет `config.file_source.filename` и вызывает `config.save()`
        Иначе выводит сообщение об ошибке и завершает программу (exit(1)).
        """
        user_input = input('Введите абсолютный путь log файла с записанными данными:\n').strip()

        # Удаляем возможные кавычки
        user_input = user_input.replace('"', '').replace("'", '')
        path = Path(user_input).resolve()

        if path.is_file():
            self._filename = path
            # Сохраняем путь в глобальный конфиг
            config.file_source.filename = path
            config.save()
            _logger.debug(f'Выбран файл: {self._filename}')
        else:
            _logger.error(f'Файл не найден: {path}')
            print(f'Не удаётся найти файл "{path}"!\n'
                  f'Проверьте корректность ввода.\n')
            exit(1)
