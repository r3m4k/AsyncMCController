# -*- coding: utf-8 -*-
"""Пакет для декодирования данных от IMU.

Пакет предоставляет набор классов для приёма байтового потока, выделения пакетов,
проверки контрольной суммы и преобразования сырых данных в структурированные объекты
(данные IMU или команды).

Доступные модули и классы:
    - decoder_protocol.DecoderProtocol: Протокол декодера.
    - base_decoder.BaseDecoder:         Базовый класс декодера.
    - imu_decoder.ImuDecoder:           Основной класс-декодер с конечным автоматом.
    - imu_data_description.ImuData:     Класс для хранения распакованных данных датчика.
"""

__version__ = '1.0.0'
__author__ = 'Tamirlan Galeev'

# --------------------------------------------------------

from decoding.decoder_protocol import DecoderProtocol
from decoding.command import Command
from decoding.base_decoder import BaseDecoder
from decoding.imu_decoding import ImuDecoder, ImuData

# --------------------------------------------------------

__all__ = [
    'DecoderProtocol',
    'Command',
    'BaseDecoder',
    'ImuDecoder',
    'ImuData'
]

# --------------------------------------------------------
