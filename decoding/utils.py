# -*- coding: utf-8 -*-
"""Утилиты для преобразования байтовых последовательностей в числа.

Содержит вспомогательные функции для объединения списка байтов в одну
байтовую строку и последующего преобразования в различные числовые типы
(int, float) с использованием порядка байт little-endian.
"""

# System imports
import struct

# External imports

# User imports
from decoding.imu_decoding.imu_data_description import TriaxialData

#############################################

def _join_bytes(byte_list: list[bytes]) -> bytes:
    """Объединяет список байтов в одну байтовую строку.
    Args:
        byte_list (list[bytes]): Список байтов (каждый элемент — байт длины 1).
    Returns:
        bytes: Конкатенированная последовательность байтов.
    """
    return b''.join(byte_list)


def bytes_to_float(byte_list: list[bytes]) -> float:
    """Преобразует 4 байта (little-endian) в число с плавающей запятой.
    Args:
        byte_list (list[bytes]): Список из 4 байтов.
    Returns:
        float: Распакованное значение.
    Raises:
        ValueError: Если длина списка не равна 4.
    """
    if len(byte_list) != 4:
        raise ValueError(f"Ожидается ровно 4 байта, получено {len(byte_list)}")
    data_bytes = _join_bytes(byte_list)
    return struct.unpack('<f', data_bytes)[0]


def bytes_to_uint32(byte_list: list[bytes]) -> int:
    """Преобразует 4 байта (little-endian) в беззнаковое 32-битное целое.
    Args:
        byte_list (list[bytes]): Список из 4 байтов.
    Returns:
        int: Беззнаковое целое число.
    Raises:
        ValueError: Если длина списка не равна 4.
    """
    if len(byte_list) != 4:
        raise ValueError(f"Ожидается ровно 4 байта, получено {len(byte_list)}")
    data_bytes = _join_bytes(byte_list)
    return struct.unpack('<I', data_bytes)[0]


def bytes_to_int32(byte_list: list[bytes]) -> int:
    """Преобразует 4 байта (little-endian) в знаковое 32-битное целое.
    Args:
        byte_list (list[bytes]): Список из 4 байтов.
    Returns:
        int: Знаковое целое число (может быть отрицательным).
    Raises:
        ValueError: Если длина списка не равна 4.
    """
    if len(byte_list) != 4:
        raise ValueError(f"Ожидается ровно 4 байта, получено {len(byte_list)}")
    data_bytes = _join_bytes(byte_list)
    return struct.unpack('<i', data_bytes)[0]


def bytes_to_uint8(byte_list: list[bytes]) -> int:
    """Преобразует 1 байт (uint8_t) в целое число.
    Args:
        byte_list (list[bytes]): Список из 1 байта.
    Returns:
        int: Значение байта как целое число в диапазоне 0–255.
    Raises:
        ValueError: Если длина списка не равна 1.
    """
    if len(byte_list) != 1:
        raise ValueError(f"Ожидается ровно 1 байт, получено {len(byte_list)}")
    return byte_list[0][0]

def bytes_to_triaxial(byte_list: list[bytes]) -> TriaxialData:
    """ Перевод списка байтов в TriaxialData """

    if len(byte_list) != 12:
        raise RuntimeError('The length of the byte_list must be 12 to convert to TriaxialData')

    return TriaxialData(
        x_coord=bytes_to_float(byte_list[0:4]),
        y_coord=bytes_to_float(byte_list[4:8]),
        z_coord=bytes_to_float(byte_list[8:12])
    )
