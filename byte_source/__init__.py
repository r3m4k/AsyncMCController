"""
Пакет для реализации различных асинхронных источников байтовых данных.

Предоставляет абстрактный базовый класс `AsyncBytesSource`, определяющий интерфейс
для чтения байтов, абстрактную фабрику `AsyncBytesSourceFactory` для создания
конкретных источников, а также реализации для COM-порта и файла.
Кроме того, содержит базовое исключение `ReadError` для унифицированной обработки
ошибок чтения.

Экспортируемые объекты:
    AsyncBytesSource         — абстрактный базовый класс для источников байтов.
    AsyncBytesSourceFactory  — абстрактная фабрика источников байтов.
    ReadError                — базовое исключение для ошибок чтения.
"""

__version__ = '1.0.0'
__author__ = 'Roman Romanovskiy'

# --------------------------------------------------------

from byte_source.bytes_source import AsyncBytesSource, AsyncBytesSourceFactory
from byte_source.read_error import ReadError

# --------------------------------------------------------

__all__ = [
    'AsyncBytesSource',
    'AsyncBytesSourceFactory',
    'ReadError',
]

# --------------------------------------------------------