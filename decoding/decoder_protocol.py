# -*- coding: utf-8 -*-
"""Протокол, определяющий интерфейс декодера данных.

Содержит класс `DecoderProtocol`, задающий минимальный набор атрибутов
и методов, которыми должен обладать любой декодер в проекте. Это позволяет
единообразно работать с разными декодерами в рамках статической типизации (duck typing).
"""

# System imports
from typing import Protocol, TypeVar
from pathlib import Path

# External imports

# User imports
from decoding.command import Command

#########################

T = TypeVar('T', covariant=True)
"""Тип данных, которые накапливает декодер в `received_data`."""


class DecoderProtocol(Protocol[T]):
    """Протокол, описывающий любой декодер, который принимает байты
    и накапливает декодированные объекты типа T.

    Attributes:
        received_data (T): Накопленные декодированные данные.
            Тип T определяется конкретной реализацией (например,
            `dict[int, list[ImuData]]`).
        input_command (list[Command]): Список принятых команд.
    """

    received_data: T
    input_command: list[Command]

    @property
    def data_len(self) -> int:
        """Возвращает количество накопленных пакетов данных.

        Конкретная семантика может различаться (общее число пакетов,
        максимальное среди датчиков и т.п.), но результат должен быть
        целым числом.
        """
        ...

    def byte_processing(self, bt: bytes) -> None:
        """Обработка очередного входящего байта.

        Args:
            bt (bytes): Один байт для обработки.
        """
        ...

    def __str__(self) -> str:
        """Строковое представление состояния декодера.
        Returns:
            str: Многострочная строка с информацией о декодере.
        """
        ...

    def save_received_data(self, filename: str | Path, sep: str = ',') -> None:
        """Сохранение всех накопленных данных в файл.

        Args:
            filename (str | Path): Имя файла для сохранения.
            sep (str): Разделитель полей в файле (по умолчанию ',').
        """
        ...