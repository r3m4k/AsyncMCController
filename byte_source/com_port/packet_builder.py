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
            _TEXT_FORMAT = bytes([0x01])

            @classmethod
            def build_text(cls, text: str) -> bytes:
                return cls._build(cls._TEXT_FORMAT, text.encode('ascii'))
    """

    _HEADER:               bytes   # Заголовок пакета — определяется в наследнике
    _TEXT_COMMAND_FORMAT:  bytes   # Байт формата текстовой команды — определяется в наследнике

    @classmethod
    def build_text_command(cls, text: str, encoding: str = 'ascii') -> bytes:
        """Формирует пакет с текстовой командой.

        Args:
            text (str):      Текст команды.
            encoding (str):  Кодировка текста. По умолчанию 'ascii'.

        Returns:
            bytes: Готовый пакет в бинарном формате протокола.

        Raises:
            ValueError: Если текст не кодируется или длина тела превышает 255 байт.
        """
        return cls._build(cls._TEXT_COMMAND_FORMAT, text.encode(encoding))

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
