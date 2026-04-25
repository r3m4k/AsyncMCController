"""
Пакет асинхронной сигнальной шины
"""

__version__ = '1.0.0'
__author__ = 'Tamirlan Galeev'

# --------------------------------------------------------

from .signals import Signals
from .signal_bus import SignalBus, Subscriber, Publisher
from .subscribers import (
    NewByteSubscriber,
    PackageReadySubscriber,
    ImuHandshakeSuccessSubscriber,
    StartMeasuringSubscriber,
    StopMeasuringSubscriber,
    HandshakeDoneSubscriber,
    HeartbeatSentSubscriber,
    HeartbeatAckSubscriber,
    HandshakeFailedSubscriber,
    DeviceLostSubscriber,
    CommandSentSubscriber,
    CommandAckSubscriber,
    CommandAckTimeoutSubscriber,
)
from .app_bus import AppBus

# Глобальный экземпляр шины для использования во всём приложении
bus = AppBus()

# --------------------------------------------------------

__all__ = [
    # Универсальный механизм
    'SignalBus',
    'Subscriber',
    'Signals',

    # Типизированная обёртка и глобальный экземпляр
    'AppBus',
    'bus',

    # Протоколы подписчиков
    'NewByteSubscriber',
    'PackageReadySubscriber',
    'ImuHandshakeSuccessSubscriber',
    'StartMeasuringSubscriber',
    'StopMeasuringSubscriber',
    'HandshakeDoneSubscriber',
    'HeartbeatSentSubscriber',
    'HeartbeatAckSubscriber',
    'HandshakeFailedSubscriber',
    'DeviceLostSubscriber',
    'CommandSentSubscriber',
    'CommandAckSubscriber',
    'CommandAckTimeoutSubscriber',
]

# --------------------------------------------------------
