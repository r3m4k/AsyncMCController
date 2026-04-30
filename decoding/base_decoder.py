# -*- coding: utf-8 -*-
"""Модуль базового асинхронного декодера байтового потока.

Содержит универсальный конечный автомат для разбора байтового потока,
проверки контрольной суммы и инфраструктуру из двух очередей и двух
фоновых задач. Не привязан к конкретному протоколу или типу данных.

Классы:
    Stage:       Перечисление состояний конечного автомата.
    BaseDecoder: Базовый класс декодера.
"""

# System imports
import asyncio
from abc import ABC, abstractmethod
from collections.abc import Coroutine
from enum import Enum
from typing import Any, Callable, Generic, Optional, TypeVar

# External imports

# User imports
from logger import app_logger
from signal_bus import bus

#############################################

_logger = app_logger.get_logger('App.BaseDecoder')

T = TypeVar('T')   # Тип декодированного пакета данных

# ------------------------------------------

class Stage(Enum):
    """Возможные состояния конечного автомата декодера."""
    WantHeader = 1      # Ожидание заголовка посылки
    WantFormat = 2      # Ожидание байта формата посылки
    WantLength = 3      # Ожидание байта длины данных
    WantData = 4        # Ожидание данных посылки
    WantControlSum = 5  # Ожидание контрольной суммы

# ------------------------------------------

class BaseDecoder(ABC, Generic[T]):
    """Базовый асинхронный декодер байтового потока.

    Реализует универсальную инфраструктуру для разбора байтового потока:
    две очереди, две фоновые задачи и конечный автомат с проверкой CRC.
    Не привязан к конкретному протоколу — наследники определяют заголовок,
    форматы пакетов и методы декодирования.

    Параметр T задаёт тип декодированного пакета данных, хранящегося в _package_queue.

    Взаимодействие с шиной:
        - подписка: NEW_BYTE (входящий байт → _byte_queue);
        - эмиссия:  PACKAGE_READY (готовый пакет) — из _package_emitting_loop.

    Протоколо-специфичные сигналы (рукопожатие, heartbeat, ACK и т.п.)
    обрабатываются в наследниках — по аналогии с AsyncComPort / AsyncComPortImu.

    Инфраструктура:
        _byte_queue:    входящие байты → _processing_loop
        _package_queue: декодированные пакеты типа T → _package_emitting_loop

    Пример наследования:
        class MyDecoder(BaseDecoder[MyData]):
            _header = [b'\\xAA', b'\\xBB']

            def __init__(self):
                super().__init__()
                # подписаться на свои протокольные сигналы, если нужно

            def _get_decode_func(self, fmt: bytes): ...
    """

    _header: list[bytes]   # Заголовок посылки — определяется в наследнике

    def __init__(self):
        self._byte_queue: asyncio.Queue[bytes] = asyncio.Queue()    # Очередь входящих байтов
        self._package_queue: asyncio.Queue[T] = asyncio.Queue()     # Очередь готовых пакетов

        # Функция декодирования текущего пакета (переключается в Stage.WantFormat)
        self._decode_func: Callable[[list[bytes]], Coroutine[Any, Any, None]] = self._default_decode_func

        self._stage: Stage = Stage.WantHeader   # Текущая стадия декодера
        self._received_bytes: list[bytes] = []  # Буфер текущей посылки

        self._data_bt_index: int = 0   # Индекс байта данных в посылке
        self._package_size:  int = 0   # Количество байт данных в посылке

        self._num_correct_packages: int = 0   # Количество пакетов, полученных без ошибок
        self._num_wrong_packages:   int = 0   # Количество пакетов, полученных с ошибками
        self._num_unknown_packages: int = 0   # Количество пакетов с неизвестным форматом

        self._processing_task: Optional[asyncio.Task] = None        # Задача обработки байтов
        self._package_emitting_task: Optional[asyncio.Task] = None  # Задача эмиссии пакетов

        # Самостоятельная подписка на базовые сигналы шины
        bus.new_byte.subscribe(self)

    # =============================================================
    # ======= Методы для работы в контекстном менеджере ===========
    # =============================================================

    async def __aenter__(self) -> 'BaseDecoder':
        """Сбрасывает состояние и запускает две фоновые задачи декодера."""
        self._reset()
        _logger.debug('Запуск задач декодера')
        self._processing_task = asyncio.create_task(self._processing_loop())
        self._package_emitting_task = asyncio.create_task(self._package_emitting_loop())
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Останавливает все фоновые задачи декодера."""
        _logger.debug('Остановка задач декодера')
        for task in (self._processing_task, self._package_emitting_task):
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        return False

    # =============================================================
    # =================== Обработчики сигналов ====================
    # =============================================================

    async def on_byte_received(self, bt: bytes) -> None:
        """Обработчик сигнала NEW_BYTE — кладёт байт во внутреннюю очередь.

        Args:
            bt (bytes): Один полученный байт.
        """
        await self._byte_queue.put(bt)

    # =============================================================
    # ================= Абстрактные методы ========================
    # =============================================================

    @abstractmethod
    def _get_decode_func(self, fmt: bytes) -> Optional[Callable[[list[bytes]], Coroutine[Any, Any, None]]]:
        """Возвращает функцию декодирования по байту формата пакета.

        Синхронный — сам по себе ничего не ждёт; возвращаемая функция асинхронная.
        Вызывается в Stage.WantFormat. Если формат неизвестен — вернуть None.

        Args:
            fmt (bytes): Байт формата из пакета.

        Returns:
            Callable или None если формат неизвестен.
        """
        ...

    # =============================================================
    # ================= Внутренняя логика =========================
    # =============================================================

    def _clear(self) -> None:
        """Сбрасывает FSM, буфер посылки и счётчики.

        Шаблонный метод — наследники переопределяют для очистки своих полей,
        вызывая super()._clear() в начале реализации. Используется как из
        обработчика HANDSHAKE_INIT, так и из _reset() при старте контекстного
        менеджера.

        Очереди и фоновые задачи здесь не трогаются — это безопасно вызывать
        из обработчика сигнала, не ломая активные задачи.
        """
        # FSM
        self._stage = Stage.WantHeader
        self._received_bytes = []
        self._data_bt_index = 0
        self._package_size = 0
        self._decode_func = self._default_decode_func

        # Счётчики
        self._num_correct_packages = 0
        self._num_wrong_packages   = 0
        self._num_unknown_packages = 0

        _logger.debug('FSM и счётчики BaseDecoder сброшены')

    def _reset(self) -> None:
        """Полный сброс состояния декодера: FSM, счётчики и очереди.

        Вызывается из __aenter__ перед запуском фоновых задач.
        """
        self._clear()

        # Пересоздадим очереди
        self._byte_queue = asyncio.Queue()
        self._package_queue = asyncio.Queue()

        _logger.debug('Состояние BaseDecoder сброшено')

    async def _processing_loop(self) -> None:
        """Фоновый цикл чтения байтов и обработки конечным автоматом."""
        _logger.debug('Запуск цикла обработки байтов')
        try:
            while True:
                bt = await self._byte_queue.get()
                await self._byte_processing(bt)
        except asyncio.CancelledError:
            _logger.debug('Цикл обработки байтов остановлен')
            raise   # TODO: разобраться, зачем тут raise

    async def _package_emitting_loop(self) -> None:
        """Фоновый цикл эмиссии пакетов из _package_queue в шину."""
        _logger.debug('Запуск цикла эмиссии пакетов')
        try:
            while True:
                data = await self._package_queue.get()
                await bus.package_ready.emit(data)
                # _logger.debug(f'Пакет эмиттирован в шину')
        except asyncio.CancelledError:
            _logger.debug('Цикл эмиссии пакетов остановлен')
            raise

    async def _byte_processing(self, bt: bytes) -> None:
        """Обработка одного байта конечным автоматом.

        Args:
            bt (bytes): Байт для обработки.
        """
        self._received_bytes.append(bt)

        match self._stage:
            case Stage.WantHeader:
                if self._received_bytes[-2:] == self._header:
                    self._stage = Stage.WantFormat
                    self._received_bytes = self._header.copy()
                    self._data_bt_index = 0

            case Stage.WantFormat:
                decode_func = self._get_decode_func(bt)
                if decode_func is not None:
                    self._decode_func = decode_func
                    self._stage = Stage.WantLength
                else:
                    self._stage = Stage.WantHeader
                    self._num_unknown_packages += 1
                    _logger.warning(f'Неизвестный формат пакета: {bt}')

            case Stage.WantLength:
                self._package_size = int.from_bytes(bt, 'big')
                self._stage = Stage.WantData

            case Stage.WantData:
                if self._data_bt_index < self._package_size - 1:
                    self._data_bt_index += 1
                else:
                    self._stage = Stage.WantControlSum

            case Stage.WantControlSum:
                if bt == self._count_control_sum(self._received_bytes):
                    await self._decode_func(self._received_bytes)
                    self._num_correct_packages += 1
                else:
                    self._num_wrong_packages += 1
                    _logger.warning(
                        f'Ошибка контрольной суммы пакета '
                        f'#{self._num_correct_packages + self._num_wrong_packages}'
                    )

                self._stage = Stage.WantHeader
                self._received_bytes = []
                self._data_bt_index = 0

    @staticmethod
    def _count_control_sum(data_bytes: list[bytes]) -> bytes:
        """Вычисляет контрольную сумму пакета (сумма байтов без последнего).

        Args:
            data_bytes (list[bytes]): Список байтов всей посылки (включая CRC).

        Returns:
            bytes: Один байт — вычисленная контрольная сумма.
        """
        total = 0
        for b in data_bytes[:-1]:
            total += int.from_bytes(b, 'big')
        return bytes([total & 0xFF])

    async def _default_decode_func(self, byte_list: list[bytes]) -> None:
        """Заглушка по умолчанию для _decode_func до первого WantFormat."""
        _logger.warning(f'_decode_func не установлена, пакет проигнорирован: {byte_list}')