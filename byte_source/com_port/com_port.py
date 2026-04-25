# System imports
import asyncio
import logging
from typing import Callable, Optional

# External imports
import serial_asyncio
from serial import SerialException

# User imports
from logger import app_logger
from byte_source.bytes_source import AsyncBytesSource
from byte_source.com_port.com_port_error import ComPortReadError
from signal_bus import bus

#########################


class AsyncComPort(AsyncBytesSource):
    """Асинхронный класс для работы с COM-портом.

    Использует pyserial-asyncio для нативного асинхронного чтения байтов,
    не блокируя event loop. При получении каждого байта эмиттит сигнал
    NEW_BYTE в сигнальную шину.

    Атрибут класса `_logger` доступен наследникам — они пишут свои логи
    под тем же именем 'App.ComPort', что упрощает анализ логов.

    Attributes:
        _logger (Logger):                   Логгер класса, доступен наследникам.
        _port_name (str):                   Имя используемого COM-порта.
        _baudrate (int):                    Скорость работы порта.
        _printing_func (Callable):          Функция для вывода сообщений пользователю.
        _port_reader (StreamReader | None): Поток чтения из порта.
        _port_writer (StreamWriter | None): Поток записи в порт.

    Пример использования:
        async with AsyncComPort('COM3', 115200) as port:
            await port.reading_loop()
    """

    _logger: logging.Logger = app_logger.get_logger('App.ComPort')

    def __init__(self, port_name: str, baudrate: int,
                 printing_func: Callable[..., None] = print):
        self._port_name: str = port_name    # Имя используемого COM-порта
        self._baudrate: int = baudrate      # Скорость работы порта
        self._printing_func: Callable = printing_func               # Функция для вывода сообщений
        self._port_reader: Optional[asyncio.StreamReader] = None    # Поток чтения
        self._port_writer: Optional[asyncio.StreamWriter] = None    # Поток записи
        self._reading_task: Optional[asyncio.Task] = None           # Задача цикла чтения

        # Самостоятельная подписка на события шины
        bus.start_measuring.subscribe(self)
        bus.stop_measuring.subscribe(self)

    async def setup(self) -> None:
        """Открытие COM-порта и создание потоков чтения/записи.

        Raises:
            ComPortReadError: Если не удалось открыть порт.
        """
        self._printing_func(f'\nПодключение к порту {self._port_name}...')
        self._logger.info(f'Подключение к порту {self._port_name} ({self._baudrate} бод)')
        try:
            self._port_reader, self._port_writer = await serial_asyncio.open_serial_connection(
                url=self._port_name,
                baudrate=self._baudrate
            )
            self._printing_func('✅ Успешно')
            self._logger.info(f'Успешное подключение к порту {self._port_name}')
        except SerialException as err:
            self._printing_func('❌ Ошибка подключения. Подробная информация:')
            self._printing_func(err)
            self._logger.error(f'Ошибка подключения к порту {self._port_name}: {err}')
            raise ComPortReadError(f'Ошибка последовательного порта: {err}', original_exception=err)

    async def cleanup(self) -> None:
        """Закрытие COM-порта и освобождение потоков."""
        try:
            if self._port_writer is not None:
                self._port_writer.close()
                await self._port_writer.wait_closed()
                self._logger.info(f'Порт {self._port_name} закрыт')
        except Exception as err:
            self._logger.warning(f'Ошибка при закрытии порта {self._port_name}: {err}')

    async def read_byte(self) -> bytes:
        """Асинхронное чтение одного байта из COM-порта.

        Returns:
            bytes: Один прочитанный байт.

        Raises:
            ComPortReadError: При ошибке чтения или потере соединения.
        """
        try:
            data = await self._port_reader.read(1)
            if not data:
                raise ComPortReadError('Соединение с COM-портом разорвано')
            return data
        except SerialException as err:
            self._logger.error(f'Ошибка чтения из порта {self._port_name}: {err}')
            raise ComPortReadError(f'Ошибка последовательного порта: {err}', original_exception=err)

    async def on_start_measuring(self) -> None:
        """Обработчик сигнала START_MEASURING — запускает цикл чтения."""
        if self._reading_task is None or self._reading_task.done():
            self._logger.debug(f'Запуск чтения из порта {self._port_name}')
            self._reading_task = asyncio.create_task(self.reading_loop())

    async def on_stop_measuring(self) -> None:
        """Обработчик сигнала STOP_MEASURING — останавливает цикл чтения."""
        if self._reading_task is not None and not self._reading_task.done():
            self._logger.debug(f'Остановка чтения из порта {self._port_name}')
            self._reading_task.cancel()
            try:
                await self._reading_task
            except asyncio.CancelledError:
                pass
            self._reading_task = None

    async def reading_loop(self) -> None:
        """Основной цикл чтения байтов из COM-порта.

        Читает байты в бесконечном цикле и эмиттит сигнал NEW_BYTE
        в шину для каждого полученного байта.

        Raises:
            ComPortReadError: При ошибке чтения из порта.
        """
        self._logger.debug(f'Запуск цикла чтения из порта {self._port_name}')
        while True:
            bt = await self.read_byte()
            await bus.new_byte.emit(bt)
