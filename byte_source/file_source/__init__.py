"""
Пакет для работы с файлом в качестве источника байтовых данных.

Предоставляет классы для настройки и чтения данных из бинарного файла,
а также исключение, специфичное для ошибок чтения из файла.

Экспортируемые объекты:
    FileSource              — класс для чтения байтов из файла (реализует AsyncBytesSource).
    AsyncFileSourceSetting  — фабрика для интерактивного выбора файла и сохранения пути в конфиг.
    FileReadError           — исключение, возникающее при ошибках чтения из файла.
"""

__version__ = '1.0.0'
__author__ = 'Roman Romanovskiy'

# --------------------------------------------------------

from byte_source.file_source.file_source import FileSource
from byte_source.file_source.file_source_error import FileReadError
from byte_source.file_source.file_source_setting import AsyncFileSourceSetting

# --------------------------------------------------------

__all__ = [
    'FileSource',
    'AsyncFileSourceSetting',
    'FileReadError',
]

# --------------------------------------------------------