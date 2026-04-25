# -*- coding: utf-8 -*-
"""Построители бинарных пакетов протокола.

Содержит иерархию классов для формирования пакетов:
    BasePacketBuilder        — универсальный движок (заголовок + формат + длина + тело + CRC).
    PacketBuilderImu         — абстрактный наследник с заголовком IMU и обязательным
                               методом _packet_format().
    PacketBuilderImuText     — построитель пакетов с текстовой командой (формат 0xAB).
    PacketBuilderImuBytes    — построитель пакетов с байтовой командой (формат 0xAB).

Контрольная сумма во всех пакетах — сумма всех байтов посылки
(включая заголовок, формат, длину и тело) по модулю 256.
"""

# System imports
from abc import ABC, abstractmethod

# External imports

# User imports

#########################


class BasePacketBuilder(ABC):
    """Базовый утилитарный класс для формирования бинарных пакетов.

    Реализует универсальную логику сборки пакета:
        [заголовок] [формат] [длина тела] [тело] [CRC]

    Контрольная сумма вычисляется как сумма всех байтов посылки
    (включая заголовок, формат, длину и тело) по модулю 256.

    Наследники определяют заголовок, форматы пакетов и публичные
    методы сборки под конкретный протокол.

    Пример наследования:
        class MyPacketBuilder(BasePacketBuilder):
            _HEADER = bytes([0xAA, 0xBB])

            @classmethod
            def build_command(cls, body: bytes) -> bytes:
                return cls._build(bytes([0x01]), body)
    """

    _HEADER: bytes   # Заголовок пакета — определяется в наследнике

    @classmethod
    def _build(cls, fmt: bytes, body: bytes) -> bytes:
        """Формирует пакет из байта формата и тела.

        Args:
            fmt (bytes):  Байт формата пакета.
            body (bytes): Тело пакета.

        Returns:
            bytes: Готовый пакет с заголовком, форматом, длиной, телом и CRC.

        Raises:
            ValueError: Если длина тела превышает 255 байт.
        """
        if len(body) > 255:
            raise ValueError(
                f'Длина тела пакета ({len(body)} байт) превышает максимум (255 байт)'
            )

        length = bytes([len(body)])
        packet_without_crc = cls._HEADER + fmt + length + body
        crc = cls._compute_crc(packet_without_crc)
        return packet_without_crc + crc

    @staticmethod
    def _compute_crc(data: bytes) -> bytes:
        """Вычисляет контрольную сумму пакета.

        Контрольная сумма — сумма всех байтов посылки по модулю 256.

        Args:
            data (bytes): Байты посылки без контрольной суммы.

        Returns:
            bytes: Один байт контрольной суммы.
        """
        return bytes([sum(data) & 0xFF])


# ------------------------------------------


class PacketBuilderImu(BasePacketBuilder):
    """Абстрактный построитель пакетов протокола IMU COM-порта.

    Задаёт заголовок IMU-протокола и обязывает наследников вернуть байт
    формата собранного пакета через абстрактный classmethod `_packet_format`.

    Наследники определяют:
      - конкретный байт формата (через `_packet_format`);
      - публичный build-метод (`build_text_command`, `build_byte_command`, ...),
        внутри которого вызывают `cls._build(cls._packet_format(), body)`.

    Класс не предназначен для прямого использования — экземпляры не создаются,
    публичные build-методы определяются только в конкретных наследниках.

    Пример наследования:
        class PacketBuilderImuFoo(PacketBuilderImu):
            @classmethod
            def _packet_format(cls) -> bytes:
                return bytes([0xAB])

            @classmethod
            def build_foo_command(cls, body: bytes) -> bytes:
                return cls._build(cls._packet_format(), body)
    """

    # Заголовок IMU-протокола (общий для всех наследников)
    _HEADER: bytes = bytes([0xC8, 0x8C])

    @classmethod
    @abstractmethod
    def _packet_format(cls) -> bytes:
        """Возвращает байт формата пакета.

        Каждый конкретный наследник обязан вернуть свой однобайтовый формат
        (например, `bytes([0xAB])` для команды). Используется внутри публичных
        build-методов как первый аргумент `cls._build(fmt, body)`.

        Returns:
            bytes: Один байт формата пакета.
        """
        ...


# ------------------------------------------


class PacketBuilderImuText(PacketBuilderImu):
    """Построитель пакетов IMU с текстовой командой.

    Упаковывает строковый текст команды в пакет протокола IMU с форматом
    `0xAB` (CommandFormat). Используется для отправки на МК команд вида
    'HANDSHAKE_REQ', 'HEARTBEAT_REQ' и т.п.

    Пример использования:
        packet = PacketBuilderImuText.build_text_command('HANDSHAKE_REQ')
        self._port_writer.write(packet)
    """

    @classmethod
    def _packet_format(cls) -> bytes:
        """Возвращает байт формата текстовой команды (CommandFormat = 0xAB)."""
        return bytes([0xAB])

    @classmethod
    def build_text_command(cls, text: str, encoding: str = 'ascii') -> bytes:
        """Формирует пакет с текстовой командой.

        Args:
            text (str):      Текст команды.
            encoding (str):  Кодировка текста. По умолчанию 'ascii'.

        Returns:
            bytes: Готовый пакет в бинарном формате протокола.

        Raises:
            ValueError: Если текст не кодируется в указанной кодировке
                или длина закодированного тела превышает 255 байт.
        """
        return cls._build(cls._packet_format(), text.encode(encoding))


# ------------------------------------------


class PacketBuilderImuBytes(PacketBuilderImu):
    """Построитель пакетов IMU с байтовой командой.

    Упаковывает готовую последовательность байтов в пакет протокола IMU
    с форматом `0xAB` (CommandFormat). Используется для отправки на МК
    команд вида `bytes([0xAA, 0x01])` (перевод в холостой режим),
    `bytes([0xAA, 0x02])` (перевод в режим измерения) и т.п.

    Отличается от PacketBuilderImuText только семантикой тела:
    raw bytes вместо ASCII-строки. Байт формата тот же — 0xAB.

    Пример использования:
        packet = PacketBuilderImuBytes.build_byte_command(bytes([0xAA, 0x01]))
        self._port_writer.write(packet)
    """

    @classmethod
    def _packet_format(cls) -> bytes:
        """Возвращает байт формата байтовой команды (CommandFormat = 0xAB)."""
        return bytes([0xAB])

    @classmethod
    def build_byte_command(cls, body: bytes) -> bytes:
        """Формирует пакет с байтовой командой.

        Args:
            body (bytes): Готовая последовательность байтов команды.

        Returns:
            bytes: Готовый пакет в бинарном формате протокола.

        Raises:
            ValueError: Если длина тела превышает 255 байт.
        """
        return cls._build(cls._packet_format(), body)
