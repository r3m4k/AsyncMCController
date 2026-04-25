"""
Пакет для декодирования данных от IMU (акселерометр + гироскоп).

Предоставляет класс `ImuDecoder`, реализующий конечный автомат для разбора
байтового потока от микроконтроллера, а также структуры данных:
`ImuData` для хранения одного пакета, `ImuGain` для представления
коэффициентов усиления, и `ImuDataIndexes` со смещениями полей в бинарном пакете.

Экспортируемые объекты:
    ImuDecoder      — основной класс декодера.
    ImuData         — структура одного пакета данных.
    ImuDataIndexes  — константы смещений полей внутри пакета.
    ImuGain         — перечисление коэффициентов усиления и каналов.
"""

__version__ = '1.0.0'
__author__ = 'Roman Romanovskiy'

# --------------------------------------------------------

from decoding.imu_decoding.imu_decoder import ImuDecoder
from decoding.imu_decoding.imu_data_description import (
    ImuData,
    ImuDataIndexes,
    TriaxialData
)

# --------------------------------------------------------

__all__ = [
    'ImuDecoder',
    'ImuData',
    'ImuDataIndexes',
    'TriaxialData'
]

# --------------------------------------------------------