# System imports
import logging
import sys
from typing import Any

# External imports

# User imports
from logger import app_logger
from config import config
from .signals import Signals
from .signal_bus import SignalBus
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

#########################

_bus:    SignalBus = SignalBus()
_logger            = app_logger.get_logger('App.Bus')

# Сигналы, эмиссия которых логируется на уровне DEBUG.
# Высокочастотные сигналы (NEW_BYTE, PACKAGE_READY) намеренно исключены.
_logged_signals: set[Signals] = {
    Signals.START_MEASURING,
    Signals.STOP_MEASURING,
    Signals.HANDSHAKE_DONE,
    Signals.HANDSHAKE_FAILED,
    Signals.IMU_HANDSHAKE_SUCCESS,
    Signals.HEARTBEAT_SENT,
    Signals.HEARTBEAT_ACK,
    Signals.DEVICE_LOST,
    Signals.COMMAND_SENT,
    Signals.COMMAND_ACK,
    Signals.COMMAND_ACK_TIMEOUT,
}


async def _emit(signal: Signals, *args: Any, **kwargs: Any) -> None:
    """Внутренняя обёртка над _bus.emit с опциональным логированием.

    Логирует эмиссию сигнала если он входит в _logged_signals
    и уровень логирования равен DEBUG. Отправитель определяется
    через sys._getframe() — только при необходимости логирования.
    Используется всеми дескрипторами AppBus вместо прямого вызова _bus.emit.
    """
    if signal in _logged_signals and config.logger_config.log_level == logging.DEBUG:
        frame  = sys._getframe(2)   # 0=_emit, 1=дескриптор emit, 2=реальный вызывающий код
        caller = frame.f_locals.get('self', None)
        sender = caller.__name__ if caller else frame.f_code.co_name
        _logger.debug(f'[{sender}] → {signal.value}')
    await _bus.emit(signal, *args, **kwargs)

# ------------------------------------------


class AppBus:
    """Типизированная обёртка над SignalBus для конкретного приложения.

    Каждый сигнал представлен отдельным вложенным классом-дескриптором,
    который инкапсулирует методы subscribe, unsubscribe и emit.
    Все вложенные классы обращаются к модульному синглтону `_bus`
    в момент вызова метода — это позволяет подменять `_bus` в тестах
    через unittest.mock.patch('signal_bus.app_bus._bus', new=TestBus()).

    Пример использования:
        bus = AppBus()

        class Decoder:
            async def on_byte_received(self, bt: bytes) -> None:
                self._queue.put_nowait(bt)

        decoder = Decoder()
        bus.new_byte.subscribe(decoder)
        await bus.new_byte.emit(b'\\xff')
    """

    # =============================================================
    # ===================== Передача данных =======================
    # =============================================================

    class NewByteSignal:
        """Эмиттится ComPort при получении байта."""

        @staticmethod
        def subscribe(subscriber: NewByteSubscriber) -> None:
            _bus.subscribe(Signals.NEW_BYTE, subscriber.on_byte_received)

        @staticmethod
        def unsubscribe(subscriber: NewByteSubscriber) -> None:
            _bus.unsubscribe(Signals.NEW_BYTE, subscriber.on_byte_received)

        @staticmethod
        async def emit(bt: bytes) -> None:
            await _emit(Signals.NEW_BYTE, bt)

    # ------------------------------------------

    class PackageReadySignal:
        """Эмиттится Decoder при успешной сборке пакета."""

        @staticmethod
        def subscribe(subscriber: PackageReadySubscriber) -> None:
            _bus.subscribe(Signals.PACKAGE_READY, subscriber.on_package_ready)

        @staticmethod
        def unsubscribe(subscriber: PackageReadySubscriber) -> None:
            _bus.unsubscribe(Signals.PACKAGE_READY, subscriber.on_package_ready)

        @staticmethod
        async def emit(data) -> None:
            await _emit(Signals.PACKAGE_READY, data)

    # =============================================================
    # =================== Управление измерением ===================
    # =============================================================

    class StartMeasuringSignal:
        """Эмиттится Controller для запуска чтения."""

        @staticmethod
        def subscribe(subscriber: StartMeasuringSubscriber) -> None:
            _bus.subscribe(Signals.START_MEASURING, subscriber.on_start_measuring)

        @staticmethod
        def unsubscribe(subscriber: StartMeasuringSubscriber) -> None:
            _bus.unsubscribe(Signals.START_MEASURING, subscriber.on_start_measuring)

        @staticmethod
        async def emit() -> None:
            await _emit(Signals.START_MEASURING)

    # ------------------------------------------

    class StopMeasuringSignal:
        """Эмиттится Controller для остановки чтения."""

        @staticmethod
        def subscribe(subscriber: StopMeasuringSubscriber) -> None:
            _bus.subscribe(Signals.STOP_MEASURING, subscriber.on_stop_measuring)

        @staticmethod
        def unsubscribe(subscriber: StopMeasuringSubscriber) -> None:
            _bus.unsubscribe(Signals.STOP_MEASURING, subscriber.on_stop_measuring)

        @staticmethod
        async def emit() -> None:
            await _emit(Signals.STOP_MEASURING)

    # =============================================================
    # ====================== Рукопожатие =========================
    # =============================================================

    class HandshakeDoneSignal:
        """Эмиттится Decoder при получении ACK рукопожатия."""

        @staticmethod
        def subscribe(subscriber: HandshakeDoneSubscriber) -> None:
            _bus.subscribe(Signals.HANDSHAKE_DONE, subscriber.on_handshake_done)

        @staticmethod
        def unsubscribe(subscriber: HandshakeDoneSubscriber) -> None:
            _bus.unsubscribe(Signals.HANDSHAKE_DONE, subscriber.on_handshake_done)

        @staticmethod
        async def emit() -> None:
            await _emit(Signals.HANDSHAKE_DONE)

    # ------------------------------------------

    class HandshakeFailedSignal:
        """Эмиттится AsyncComPortImu при таймауте рукопожатия."""

        @staticmethod
        def subscribe(subscriber: HandshakeFailedSubscriber) -> None:
            _bus.subscribe(Signals.HANDSHAKE_FAILED, subscriber.on_handshake_failed)

        @staticmethod
        def unsubscribe(subscriber: HandshakeFailedSubscriber) -> None:
            _bus.unsubscribe(Signals.HANDSHAKE_FAILED, subscriber.on_handshake_failed)

        @staticmethod
        async def emit() -> None:
            await _emit(Signals.HANDSHAKE_FAILED)

    # ------------------------------------------

    class ImuHandshakeSuccessSignal:
        """Эмиттится AsyncComPortImu после успешного рукопожатия."""

        @staticmethod
        def subscribe(subscriber: ImuHandshakeSuccessSubscriber) -> None:
            _bus.subscribe(Signals.IMU_HANDSHAKE_SUCCESS, subscriber.on_imu_handshake_success)

        @staticmethod
        def unsubscribe(subscriber: ImuHandshakeSuccessSubscriber) -> None:
            _bus.unsubscribe(Signals.IMU_HANDSHAKE_SUCCESS, subscriber.on_imu_handshake_success)

        @staticmethod
        async def emit() -> None:
            await _emit(Signals.IMU_HANDSHAKE_SUCCESS)

    # =============================================================
    # ======================== Heartbeat ==========================
    # =============================================================

    class HeartbeatSentSignal:
        """Эмиттится AsyncComPortImu перед отправкой heartbeat."""

        @staticmethod
        def subscribe(subscriber: HeartbeatSentSubscriber) -> None:
            _bus.subscribe(Signals.HEARTBEAT_SENT, subscriber.on_heartbeat_sent)

        @staticmethod
        def unsubscribe(subscriber: HeartbeatSentSubscriber) -> None:
            _bus.unsubscribe(Signals.HEARTBEAT_SENT, subscriber.on_heartbeat_sent)

        @staticmethod
        async def emit() -> None:
            await _emit(Signals.HEARTBEAT_SENT)

    # ------------------------------------------

    class HeartbeatAckSignal:
        """Эмиттится Decoder при получении heartbeat ACK от МК."""

        @staticmethod
        def subscribe(subscriber: HeartbeatAckSubscriber) -> None:
            _bus.subscribe(Signals.HEARTBEAT_ACK, subscriber.on_heartbeat_ack)

        @staticmethod
        def unsubscribe(subscriber: HeartbeatAckSubscriber) -> None:
            _bus.unsubscribe(Signals.HEARTBEAT_ACK, subscriber.on_heartbeat_ack)

        @staticmethod
        async def emit() -> None:
            await _emit(Signals.HEARTBEAT_ACK)

    # ------------------------------------------

    class DeviceLostSignal:
        """Эмиттится AsyncComPortImu при таймауте heartbeat."""

        @staticmethod
        def subscribe(subscriber: DeviceLostSubscriber) -> None:
            _bus.subscribe(Signals.DEVICE_LOST, subscriber.on_device_lost)

        @staticmethod
        def unsubscribe(subscriber: DeviceLostSubscriber) -> None:
            _bus.unsubscribe(Signals.DEVICE_LOST, subscriber.on_device_lost)

        @staticmethod
        async def emit() -> None:
            await _emit(Signals.DEVICE_LOST)

    # =============================================================
    # ==================== Подтверждение команд ===================
    # =============================================================

    class CommandSentSignal:
        """Эмиттится AsyncComPortImu перед отправкой команды с подтверждением."""

        @staticmethod
        def subscribe(subscriber: CommandSentSubscriber) -> None:
            _bus.subscribe(Signals.COMMAND_SENT, subscriber.on_command_sent)

        @staticmethod
        def unsubscribe(subscriber: CommandSentSubscriber) -> None:
            _bus.unsubscribe(Signals.COMMAND_SENT, subscriber.on_command_sent)

        @staticmethod
        async def emit() -> None:
            await _emit(Signals.COMMAND_SENT)

    # ------------------------------------------

    class CommandAckSignal:
        """Эмиттится Decoder при получении подтверждения команды от МК."""

        @staticmethod
        def subscribe(subscriber: CommandAckSubscriber) -> None:
            _bus.subscribe(Signals.COMMAND_ACK, subscriber.on_command_ack)

        @staticmethod
        def unsubscribe(subscriber: CommandAckSubscriber) -> None:
            _bus.unsubscribe(Signals.COMMAND_ACK, subscriber.on_command_ack)

        @staticmethod
        async def emit() -> None:
            await _emit(Signals.COMMAND_ACK)

    # ------------------------------------------

    class CommandAckTimeoutSignal:
        """Эмиттится AsyncComPortImu при таймауте подтверждения команды."""

        @staticmethod
        def subscribe(subscriber: CommandAckTimeoutSubscriber) -> None:
            _bus.subscribe(Signals.COMMAND_ACK_TIMEOUT, subscriber.on_command_ack_timeout)

        @staticmethod
        def unsubscribe(subscriber: CommandAckTimeoutSubscriber) -> None:
            _bus.unsubscribe(Signals.COMMAND_ACK_TIMEOUT, subscriber.on_command_ack_timeout)

        @staticmethod
        async def emit() -> None:
            await _emit(Signals.COMMAND_ACK_TIMEOUT)

    # =============================================================

    def __init__(self):
        # Передача данных
        self.new_byte                = AppBus.NewByteSignal()
        self.package_ready           = AppBus.PackageReadySignal()
        # Управление измерением
        self.start_measuring         = AppBus.StartMeasuringSignal()
        self.stop_measuring          = AppBus.StopMeasuringSignal()
        # Рукопожатие
        self.handshake_done          = AppBus.HandshakeDoneSignal()
        self.handshake_failed        = AppBus.HandshakeFailedSignal()
        self.imu_handshake_success = AppBus.ImuHandshakeSuccessSignal()
        # Heartbeat
        self.heartbeat_sent          = AppBus.HeartbeatSentSignal()
        self.heartbeat_ack           = AppBus.HeartbeatAckSignal()
        self.device_lost             = AppBus.DeviceLostSignal()
        # Подтверждение команд
        self.command_sent            = AppBus.CommandSentSignal()
        self.command_ack             = AppBus.CommandAckSignal()
        self.command_ack_timeout     = AppBus.CommandAckTimeoutSignal()
