# -*- coding: utf-8 -*-
"""Модуль декодера протокола передачи данных АЦП IMU.

Содержит константы форматов пакетов и конкретную реализацию декодера
для протокола IMU, унаследованную от BaseDecoder.

Классы:
    PackageFormat: Константы форматов пакетов протокола IMU.
    ImuDecoder:  Декодер протокола IMU.
"""

# System imports
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, Callable, Optional, TypeAlias

# External imports

# User imports
from logger import app_logger
from signal_bus import bus
from decoding.base_decoder import BaseDecoder, Stage
from decoding.imu_decoding.imu_data_description import ImuData, ImuDataIndexes
from decoding.utils import bytes_to_uint32, bytes_to_triaxial

#############################################

_logger = app_logger.get_logger('App.Decoder')

# Тип сохранённого состояния автомата (см. ImuDecoder._save_state).
# Порядок полей: stage, received_bytes, data_bt_index, package_size, decode_func.
SavedState: TypeAlias = tuple[
    Stage,
    list[bytes],
    int,
    int,
    Callable[[list[bytes]], Coroutine[Any, Any, None]],
]

# ------------------------------------------


class PackageFormat:
    """Константы форматов пакетов протокола IMU."""
    ImuFormat:   bytes = b'\x01'   # Пакет с данными IMU
    CommandFormat: bytes = b'\xAB'   # Командный пакет
    MessageFormat: bytes = b'\xCD'   # Текстовое сообщение (ACK рукопожатия / heartbeat)


# ------------------------------------------


class ImuDecoder(BaseDecoder[ImuData]):
    """Декодер протокола передачи данных АЦП IMU.

    Расширяет BaseDecoder логикой IMU-протокола: добавляет заголовок,
    форматы пакетов, методы декодирования данных / команд / текстовых
    сообщений (ACK рукопожатия, heartbeat, подтверждения команды),
    а также механизм сохранения и восстановления состояния автомата
    на время обработки короткого ACK-пакета.

    Дополнительное взаимодействие с шиной (поверх базового NEW_BYTE /
    PACKAGE_READY):
        - подписка: HEARTBEAT_SENT, COMMAND_SENT (сохранить состояние);
        - подписка: COMMAND_ACK_TIMEOUT (откатить состояние при таймауте);
        - эмиссия:  HANDSHAKE_DONE, HEARTBEAT_ACK, COMMAND_ACK
                    (через _command_queue, из _bytes_to_message).

    Attributes:
        received_data (list[ImuData]): Плоский список принятых пакетов
            данных IMU в порядке поступления.

    Пример использования:
        decoder = ImuDecoder()
        async with decoder:
            await controller.start()
            await controller.stop()
    """

    _header:        list[bytes] = [b'\xc8', b'\x8c']          # Заголовок посылки (2 байта)
    _handshake_ack: str         = 'IMU_STM32_ACK'             # Ожидаемое сообщение рукопожатия
    _heartbeat_ack: str         = 'IMU_STM32_ALIVE'           # Ожидаемое сообщение heartbeat
    _command_ack:   str         = 'CONFIRM_RECEIVED_COMMAND'  # Ожидаемое подтверждение команды

    def __init__(self):
        super().__init__()
        self.received_data: list[ImuData] = []   # Список полученных пакетов в порядке поступления

        # Сохранённое состояние автомата на время обработки heartbeat / команды
        self._saved_state: Optional[SavedState] = None

        # Самостоятельная подписка на IMU-специфичные сигналы шины
        # (NEW_BYTE подписан в BaseDecoder)
        bus.heartbeat_sent.subscribe(self)
        bus.command_sent.subscribe(self)
        bus.command_ack_timeout.subscribe(self)

    # =============================================================
    # =================== Обработчики сигналов ====================
    # =============================================================

    async def on_heartbeat_sent(self) -> None:
        """Обработчик сигнала HEARTBEAT_SENT — сохраняет состояние автомата.

        Переключает декодер в WantHeader для корректного приёма ACK пакета
        heartbeat. Состояние восстанавливается в _restore_state() после ACK.
        """
        self._save_state('heartbeat')

    async def on_command_sent(self) -> None:
        """Обработчик сигнала COMMAND_SENT — сохраняет состояние автомата.

        Переключает декодер в WantHeader для корректного приёма подтверждения
        команды от МК. Состояние восстанавливается в _restore_state() после ACK
        либо после COMMAND_ACK_TIMEOUT (через on_command_ack_timeout).
        """
        self._save_state('подтверждения команды')

    async def on_command_ack_timeout(self) -> None:
        """Обработчик сигнала COMMAND_ACK_TIMEOUT — восстанавливает состояние.

        Если ACK не пришёл за отведённое время, сохранённое состояние
        нужно откатить — иначе следующий on_command_sent / on_heartbeat_sent
        перепишет _saved_state и изначальное состояние будет потеряно.
        Декодер возвращается в исходный режим работы (до отправки команды).
        """
        if self._saved_state is None:
            _logger.warning('COMMAND_ACK_TIMEOUT без предварительно сохранённого состояния')
            return
        self._restore_state()
        _logger.warning('Состояние декодера восстановлено после таймаута команды')

    # =============================================================
    # =================== Публичные методы ========================
    # =============================================================

    @property
    def data_len(self) -> int:
        """Возвращает количество накопленных пакетов данных IMU."""
        return len(self.received_data)

    def __str__(self) -> str:
        total = self._num_correct_packages + self._num_wrong_packages + self._num_unknown_packages
        return (
            f'🔍 Информация о {self.__class__.__name__}:\n'
            f'| Количество корректно принятых пакетов данных:     {self._num_correct_packages} из {total}\n'
            f'| Количество пакетов данных, полученных с ошибкой:  {self._num_wrong_packages} из {total}\n'
            f'| Количество пакетов с неизвестным форматом:        {self._num_unknown_packages} из {total}\n'
            f'| -----------------------------------------------\n'
        )

    def save_received_data(self, filepath: str | Path, sep: str = ',') -> None:
        """Сохраняет все накопленные данные декодера в CSV-файл.

        Формат: PackageNum, AccX, AccY, AccZ, GyroX, GyroY, GyroZ.
        Числа с плавающей точкой записываются с точкой как десятичным
        разделителем — поэтому разделитель полей по умолчанию ','.

        Args:
            filepath (str | Path): Путь к файлу сохранения.
            sep (str):             Разделитель полей. По умолчанию ','.

        Raises:
            ValueError: Если нет данных для сохранения.
        """
        if not self.received_data:
            raise ValueError('Нет данных для сохранения. Список received_data пуст.')

        file_path = Path(filepath)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(
                f'PackageNum{sep}'
                f'AccX{sep}AccY{sep}AccZ{sep}'
                f'GyroX{sep}GyroY{sep}GyroZ\n'
            )
            for data in self.received_data:
                file.write(
                    f'{data.package_num}{sep}'
                    f'{data.acc.x_coord}{sep}{data.acc.y_coord}{sep}{data.acc.z_coord}{sep}'
                    f'{data.gyro.x_coord}{sep}{data.gyro.y_coord}{sep}{data.gyro.z_coord}\n'
                )

    # =============================================================
    # ================= Внутренняя логика =========================
    # =============================================================

    def _get_decode_func(self, fmt: bytes) -> Optional[Callable[[list[bytes]], Coroutine[Any, Any, None]]]:
        """Возвращает функцию декодирования по байту формата пакета.

        Args:
            fmt (bytes): Байт формата из пакета.

        Returns:
            Callable или None если формат неизвестен.
        """
        if fmt == PackageFormat.ImuFormat:
            return self._bytes_to_imu_data
        elif fmt == PackageFormat.CommandFormat:
            return self._bytes_to_command
        elif fmt == PackageFormat.MessageFormat:
            return self._bytes_to_message
        return None

    def _save_state(self, reason: str) -> None:
        """Сохраняет полное состояние конечного автомата и переводит его в WantHeader.

        Вызывается перед отправкой heartbeat / команды, чтобы декодер корректно
        принял короткий ACK-пакет, а после — восстановил разбор прерванной посылки
        (через _restore_state либо через обработчик таймаута).

        Args:
            reason (str): Причина сохранения для лога (например, 'heartbeat',
                'подтверждения команды'). Используется только в DEBUG-логе.
        """
        self._saved_state = (
            self._stage,
            self._received_bytes.copy(),
            self._data_bt_index,
            self._package_size,
            self._decode_func,
        )
        self._stage          = Stage.WantHeader
        self._received_bytes = []
        self._data_bt_index  = 0
        self._package_size   = 0
        _logger.debug(f'Состояние декодера сохранено для {reason}')

    def _restore_state(self) -> None:
        """Восстанавливает состояние конечного автомата из _saved_state.

        Используется после получения ACK heartbeat / подтверждения команды,
        а также после таймаута команды. Вызывающий код логирует причину
        восстановления сам.
        """
        if self._saved_state is None:
            _logger.warning('Попытка восстановить состояние декодера без предварительного сохранения')
            return

        (self._stage,
         self._received_bytes,
         self._data_bt_index,
         self._package_size,
         self._decode_func) = self._saved_state

        self._saved_state = None
        _logger.debug('Состояние декодера восстановлено')

    async def _bytes_to_imu_data(self, byte_list: list[bytes]) -> None:
        """Декодирует список байтов в структуру ImuData.

        Сохраняет пакет в received_data и кладёт в _package_queue.

        Args:
            byte_list (list[bytes]): Список байтов всей посылки.
        """
        data = ImuData(
            package_num = bytes_to_uint32(byte_list[ImuDataIndexes.package_num : ImuDataIndexes.package_num + 4]),
            acc  = bytes_to_triaxial(byte_list[ImuDataIndexes.acc_index : ImuDataIndexes.acc_index + 12]),
            gyro = bytes_to_triaxial(byte_list[ImuDataIndexes.gyro_index : ImuDataIndexes.gyro_index + 12]),
        )
        self.received_data.append(data)
        await self._package_queue.put(data)
        _logger.debug(f'Пакет #{self._num_correct_packages} декодирован: package_num={data.package_num}')

    async def _bytes_to_command(self, byte_list: list[bytes]) -> None:
        """Заглушка для будущей обработки командных пакетов от МК.

        Args:
            byte_list (list[bytes]): Список байтов всей посылки.
        """
        _logger.debug(f'Командный пакет получен (обработчик не реализован): {byte_list}')

    async def _bytes_to_message(self, byte_list: list[bytes]) -> None:
        """Декодирует текстовое сообщение от МК.

        Различает ACK рукопожатия и ACK heartbeat по содержимому строки.
        При heartbeat ACK восстанавливает сохранённое состояние автомата.

        Args:
            byte_list (list[bytes]): Список байтов всей посылки.
        """
        # Данные начинаются с индекса 4 (2 байта заголовка + формат + длина)
        # и заканчиваются до последнего байта (контрольная сумма)
        message_bytes = b''.join(byte_list[4:-1])
        try:
            message = message_bytes.decode('ascii')
        except UnicodeDecodeError:
            _logger.warning(f'Сообщение от МК содержит невалидные ASCII байты: {message_bytes!r}')
            return

        if message == self._handshake_ack:
            await self._command_queue.put(bus.handshake_done.emit())
            _logger.info(f'ACK рукопожатия получен: "{message}"')

        elif message == self._heartbeat_ack:
            self._restore_state()
            await self._command_queue.put(bus.heartbeat_ack.emit())
            _logger.debug(f'ACK heartbeat получен: "{message}"')

        elif message == self._command_ack:
            self._restore_state()
            await self._command_queue.put(bus.command_ack.emit())
            _logger.debug(f'Подтверждение команды получено: "{message}"')

        else:
            _logger.warning(f'Неизвестное сообщение от МК: "{message}"')