# -*- coding: utf-8 -*-
"""Модуль для работы с файловым источником данных.

Предоставляет класс `FileSource`, наследующий от `AsyncBytesSource`, который
позволяет читать байты из бинарного файла. Используется для воспроизведения
ранее записанных логов (например, с COM-порта).
"""

# System imports
import io
from pathlib import Path

# External imports

# User imports
from byte_source import AsyncBytesSource
from byte_source.file_source.file_source_error import FileReadError

#########################

class FileSource(AsyncBytesSource):
    """Источник байтов, читающий данные из бинарного файла.

    Реализует интерфейс `AsyncBytesSource` для чтения байтов из файла.
    При входе в контекстный менеджер открывает файл, при выходе — закрывает.
    Метод `read_byte` читает один байт и выбрасывает `FileReadError`
    при достижении конца файла или ошибках ввода-вывода.

    Attributes:
        _filename (str | Path): Путь к файлу, из которого производится чтение.
        _bin_file (io.BufferedReader): Открытый бинарный файл (инициализируется в `setup`).
    """

    _bin_file: io.BufferedReader

    def __init__(self, file_name: str | Path) -> None:
        """Инициализирует источник с указанным файлом.

        Args:
            file_name (str | Path): Путь к файлу для чтения. Может быть строкой
                или объектом `Path`.
        """
        self._filename: str | Path = file_name

    def setup(self) -> None:
        """Открывает файл для бинарного чтения.

        Вызывается автоматически при входе в контекстный менеджер (`with`).

        Raises:
            FileNotFoundError: Если файл не существует.
            PermissionError: Если недостаточно прав для чтения.
            OSError: При других ошибках открытия файла.
        """
        self._bin_file = open(self._filename, 'rb')

    def cleanup(self) -> None:
        """Закрывает файл.

        Вызывается автоматически при выходе из контекстного менеджера.
        """
        self._bin_file.close()

    def read_byte(self) -> bytes:
        """Читает один байт из файла.

        Returns:
            bytes: Прочитанный байт (объект bytes длины 1).

        Raises:
            FileReadError: Если достигнут конец файла или произошла ошибка
                чтения (например, из-за проблем с диском). Оригинальное
                исключение (если есть) доступно через атрибут
                `original_exception`.
        """
        try:
            data = self._bin_file.read(1)
            if not data:
                raise FileReadError("Достигнут конец файла")
            return data
        except OSError as e:
            raise FileReadError(f"Ошибка чтения файла: {e}", original_exception=e)