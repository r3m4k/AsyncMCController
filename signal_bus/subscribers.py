# -*- coding: utf-8 -*-
"""Модуль протоколов подписчиков сигнальной шины.

Каждый протокол описывает контракт объекта, который может быть подписан
на конкретный сигнал через AppBus. Протокол фиксирует имя метода и его
сигнатуру — линтер проверяет соответствие при передаче объекта в AppBus.

Соглашение об именовании:
    - Протокол: <ИмяСигнала>Subscriber
    - Метод:    on_<имя_сигнала_в_snake_case>

Добавление нового сигнала:
    1. Добавить значение в Signals (signals.py)
    2. Добавить протокол в этот файл
    3. Добавить методы subscribe/unsubscribe/emit в AppBus (app_bus.py)
    4. Экспортировать протокол в __init__.py
"""

# System imports
from typing import Protocol

# External imports

# User imports

#########################


class NewByteSubscriber(Protocol):
    """Протокол подписчика сигнала Signals.NEW_BYTE.

    Любой объект, реализующий метод on_byte_received, может быть
    передан в AppBus.new_byte.subscribe().

    Пример реализации:
        class Decoder:
            async def on_byte_received(self, bt: bytes) -> None:
                self._queue.put_nowait(bt)
    """
    async def on_byte_received(self, bt: bytes) -> None: ...


# ------------------------------------------

class PackageReadySubscriber(Protocol):
    """Протокол подписчика сигнала Signals.PACKAGE_READY.

    Любой объект, реализующий метод on_package_ready, может быть
    передан в AppBus.package_ready.subscribe().

    Пример реализации:
        class Controller:
            async def on_package_ready(self, data: ImuData) -> None:
                self._received_data.append(data)
    """
    async def on_package_ready(self, data) -> None: ...


# ------------------------------------------

class ImuHandshakeSuccessSubscriber(Protocol):
    """Протокол подписчика сигнала Signals.IMU_HANDSHAKE_SUCCESS.

    Любой объект, реализующий метод on_imu_handshake_success, может быть
    передан в AppBus.imu_handshake_success.subscribe().

    Пример реализации:
        class Controller:
            async def on_imu_handshake_success(self) -> None:
                self._logger.info('Рукопожатие с Imu выполнено успешно')
    """
    async def on_imu_handshake_success(self) -> None: ...


# ------------------------------------------

class StartMeasuringSubscriber(Protocol):
    """Протокол подписчика сигнала Signals.START_MEASURING.

    Любой объект, реализующий метод on_start_measuring, может быть
    передан в AppBus.start_measuring.subscribe().

    Пример реализации:
        class AsyncComPort:
            async def on_start_measuring(self) -> None:
                self._reading_task = asyncio.create_task(self.reading_loop())
    """
    async def on_start_measuring(self) -> None: ...


# ------------------------------------------

class StopMeasuringSubscriber(Protocol):
    """Протокол подписчика сигнала Signals.STOP_MEASURING.

    Любой объект, реализующий метод on_stop_measuring, может быть
    передан в AppBus.stop_measuring.subscribe().

    Пример реализации:
        class AsyncComPort:
            async def on_stop_measuring(self) -> None:
                self._reading_task.cancel()
    """
    async def on_stop_measuring(self) -> None: ...


# ------------------------------------------

class InterruptMeasuringSubscriber(Protocol):
    """Протокол подписчика сигнала Signals.INTERRUPT_MEASURING.

    Эмиттится Controller при аварийном завершении работы (HANDSHAKE_FAILED,
    DEVICE_LOST, COMMAND_ACK_TIMEOUT, COMMAND_REJECTED). В отличие от
    STOP_MEASURING, означает «связь с МК нарушена — никаких команд ему
    больше не посылать»: получатель должен закрыть свои ресурсы напрямую,
    минуя протокольное взаимодействие с устройством.

    Пример реализации:
        class AsyncComPortImu:
            async def on_interrupt_measuring(self) -> None:
                # отменяем heartbeat, прерываем ожидание ACK,
                # останавливаем чтение — без команд МК
                ...
    """
    async def on_interrupt_measuring(self) -> None: ...


# ------------------------------------------

class HandshakeDoneSubscriber(Protocol):
    """Протокол подписчика сигнала Signals.HANDSHAKE_DONE.

    Любой объект, реализующий метод on_handshake_done, может быть
    передан в AppBus.handshake_done.subscribe().

    Пример реализации:
        class AsyncComPortImu:
            async def on_handshake_done(self) -> None:
                self._handshake_event.set()
    """
    async def on_handshake_done(self) -> None: ...


# ------------------------------------------

class HeartbeatSentSubscriber(Protocol):
    """Протокол подписчика сигнала Signals.HEARTBEAT_SENT."""
    async def on_heartbeat_sent(self) -> None: ...


# ------------------------------------------

class CommandSentSubscriber(Protocol):
    """Протокол подписчика сигнала Signals.COMMAND_SENT.

    Пример реализации:
        class ImuDecoder:
            async def on_command_sent(self) -> None:
                self._saved_state = (...)
                self._stage = Stage.WantHeader
    """
    async def on_command_sent(self) -> None: ...


# ------------------------------------------

class CommandAckSubscriber(Protocol):
    """Протокол подписчика сигнала Signals.COMMAND_ACK.

    Пример реализации:
        class AsyncComPortImu:
            async def on_command_ack(self) -> None:
                self._command_ack_event.set()
    """
    async def on_command_ack(self) -> None: ...


# ------------------------------------------

class HeartbeatAckSubscriber(Protocol):
    """Протокол подписчика сигнала Signals.HEARTBEAT_ACK.

    Любой объект, реализующий метод on_heartbeat_ack, может быть
    передан в AppBus.heartbeat_ack.subscribe().

    Пример реализации:
        class AsyncComPortImu:
            async def on_heartbeat_ack(self) -> None:
                self._heartbeat_event.set()
    """
    async def on_heartbeat_ack(self) -> None: ...


# ------------------------------------------

class DeviceLostSubscriber(Protocol):
    """Протокол подписчика сигнала Signals.DEVICE_LOST.

    Любой объект, реализующий метод on_device_lost, может быть
    передан в AppBus.device_lost.subscribe().

    Пример реализации:
        class Controller:
            async def on_device_lost(self) -> None:
                self._logger.critical('Устройство не отвечает')
    """
    async def on_device_lost(self) -> None: ...


# ------------------------------------------

class HandshakeFailedSubscriber(Protocol):
    """Протокол подписчика сигнала Signals.HANDSHAKE_FAILED.

    Любой объект, реализующий метод on_handshake_failed, может быть
    передан в AppBus.handshake_failed.subscribe().

    Пример реализации:
        class Controller:
            async def on_handshake_failed(self) -> None:
                self._logger.error('Рукопожатие не выполнено — завершение программы')
    """
    async def on_handshake_failed(self) -> None: ...


# ------------------------------------------

class CommandAckTimeoutSubscriber(Protocol):
    """Протокол подписчика сигнала Signals.COMMAND_ACK_TIMEOUT.

    Эмиттится AsyncComPortImu когда МК не прислал подтверждение команды
    за отведённое время. В отличие от HEARTBEAT_SENT/ACK, потеря одного
    подтверждения команды не обязательно означает потерю устройства —
    подписчик решает сам, как на это реагировать.

    Пример реализации:
        class Controller:
            async def on_command_ack_timeout(self) -> None:
                self._logger.error('МК не подтвердил команду — остановка')
                self._force_stop = True
    """
    async def on_command_ack_timeout(self) -> None: ...


# ------------------------------------------

class CommandRejectedSubscriber(Protocol):
    """Протокол подписчика сигнала Signals.COMMAND_REJECTED.

    Эмиттится ImuDecoder при получении от МК сообщения 'UNKNOWN_COMMAND' —
    МК не распознал отправленную ПК команду. Семантически это третий исход
    команды (наряду с COMMAND_ACK и COMMAND_ACK_TIMEOUT) — «программная
    ошибка контракта ПК↔МК». В проде такой ситуации быть не должно,
    но для отладки сигнал критически важен.

    Пример реализации:
        class Controller:
            async def on_command_rejected(self) -> None:
                self._logger.critical('МК отверг команду — аварийная остановка')
                self._force_stop = True
    """
    async def on_command_rejected(self) -> None: ...