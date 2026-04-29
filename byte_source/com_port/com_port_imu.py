# System imports
import asyncio
from typing import Callable, Optional
import logging

# External imports

# User imports
from byte_source.com_port.com_port import AsyncComPort
from byte_source.com_port.packet_builders import PacketBuilderImuText, PacketBuilderImuBytes
from signal_bus import bus
from logger import app_logger

#########################

_logger: logging.Logger = app_logger.get_logger('App.ComPort.ComPortImu')

_RESPONSE_TIMEOUT: float = 2.0    # Таймаут ответа на рукопожатие и heartbeat (сек)
_HEARTBEAT_PERIOD: float = 10.0   # Период отправки heartbeat (сек)


class AsyncComPortImu(AsyncComPort):
    """Асинхронный класс для работы с платой МК с АЦП IMU.

    Расширяет AsyncComPort процедурой рукопожатия, heartbeat и управлением
    режимами работы платы:
    - При START_MEASURING эмиттит HANDSHAKE_INIT (декодер чистит состояние),
      отправляет команду рукопожатия и ждёт ACK через Event.
    - При HANDSHAKE_DONE устанавливает событие рукопожатия, переводит плату
      в режим измерения и запускает heartbeat loop.
    - Heartbeat loop периодически отправляет команду и ждёт ACK через Event.
    - При таймауте рукопожатия эмиттит HANDSHAKE_FAILED.
    - При таймауте heartbeat эмиттит DEVICE_LOST.

    Логи пишутся через унаследованный `_logger` ('App.ComPort').

    Команды на МК собираются через билдеры протокола IMU
    (PacketBuilderImuText / PacketBuilderImuBytes) — заголовок и CRC
    пакета вычисляются единообразно, без дублирования логики в этом классе.

    Attributes:
        _set_foo_stage_command (bytes):      Команда перевода в холостой режим.
        _set_measure_stage_command (bytes):  Команда перевода в режим измерения.
        _init_handshake_command (bytes):     Команда инициализации рукопожатия.
        _heartbeat_command (bytes):          Команда проверки на зависание.
    """

    _set_foo_stage_command:     bytes = PacketBuilderImuBytes.build_byte_command(bytes([0xAA, 0x01]))
    _set_measure_stage_command: bytes = PacketBuilderImuBytes.build_byte_command(bytes([0xAA, 0x02]))
    _init_handshake_command:    bytes = PacketBuilderImuText.build_text_command('HANDSHAKE_REQ')
    _heartbeat_command:         bytes = PacketBuilderImuText.build_text_command('HEARTBEAT_REQ')

    def __init__(self, port_name: str, baudrate: int,
                 printing_func: Callable[..., None] = print):
        super().__init__(port_name, baudrate, printing_func)
        self._handshake_event:     asyncio.Event          = asyncio.Event()   # Событие получения ACK рукопожатия
        self._heartbeat_ack_event: asyncio.Event          = asyncio.Event()   # Событие получения ACK heartbeat
        self._command_ack_event:   asyncio.Event          = asyncio.Event()   # Событие получения подтверждения команды
        self._heartbeat_task:      Optional[asyncio.Task] = None              # Задача heartbeat loop
        self._stopped:             bool                   = False             # Флаг «остановка уже выполнена»

        # Самостоятельная подписка на события шины
        bus.handshake_done.subscribe(self)
        bus.heartbeat_ack.subscribe(self)
        bus.command_ack.subscribe(self)
        bus.command_rejected.subscribe(self)
        bus.interrupt_measuring.subscribe(self)

    # =============================================================
    # =================== Обработчики сигналов ====================
    # =============================================================

    async def on_start_measuring(self) -> None:
        """Обработчик сигнала START_MEASURING.

        Эмиттит HANDSHAKE_INIT (декодер чистит накопленное состояние перед
        работой с неизвестным МК), отправляет команду рукопожатия,
        запускает чтение данных и ждёт ACK. При таймауте эмиттит
        HANDSHAKE_FAILED.
        """
        self._logger.debug(f'Инициализация рукопожатия по порту {self._port_name}')
        await bus.handshake_init.emit()
        await self._send_command(self._init_handshake_command)
        await super().on_start_measuring()

        self._handshake_event.clear()
        try:
            await asyncio.wait_for(
                self._handshake_event.wait(),
                timeout=_RESPONSE_TIMEOUT
            )
        except asyncio.TimeoutError:
            self._logger.error(
                f'Таймаут рукопожатия по порту {self._port_name} '
                f'({_RESPONSE_TIMEOUT} сек) — рукопожатие не выполнено'
            )
            await bus.handshake_failed.emit()

    async def on_stop_measuring(self) -> None:
        """Обработчик сигнала STOP_MEASURING.

        Останавливает heartbeat, переводит плату в холостой режим
        и останавливает чтение.

        Идемпотентен: повторный вызов после уже выполненной остановки
        (через STOP_MEASURING или INTERRUPT_MEASURING) — no-op. Это нужно,
        чтобы повторная эмиссия INTERRUPT_MEASURING после провалившейся
        штатной остановки (Controller.stop) не пыталась посылать МК
        команды второй раз.
        """
        if self._stopped:
            self._logger.debug(
                f'STOP_MEASURING для порта {self._port_name} проигнорирован: '
                f'остановка уже выполнена'
            )
            return
        self._stopped = True
        await self._cancel_task(self._heartbeat_task)
        self._heartbeat_task = None
        await self._send_command_with_ack(self._set_foo_stage_command)
        await super().on_stop_measuring()

    async def on_handshake_done(self) -> None:
        """Обработчик сигнала HANDSHAKE_DONE от декодера.

        Устанавливает событие рукопожатия, переводит плату в режим измерения
        и запускает heartbeat loop.
        """
        self._handshake_event.set()

        self._logger.info(f'Рукопожатие с Imu по порту {self._port_name} выполнено успешно')
        await self._send_command_with_ack(self._set_measure_stage_command)

        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def on_heartbeat_ack(self) -> None:
        """Обработчик сигнала HEARTBEAT_ACK от декодера."""
        self._heartbeat_ack_event.set()
        self._logger.debug(f'ACK heartbeat получен по порту {self._port_name}')

    async def on_command_ack(self) -> None:
        """Обработчик сигнала COMMAND_ACK от декодера.

        Устанавливает событие подтверждения команды, снимая ожидание
        в _send_command_with_ack.
        """
        self._command_ack_event.set()
        self._logger.debug(f'Подтверждение команды получено по порту {self._port_name}')

    async def on_command_rejected(self) -> None:
        """Обработчик сигнала COMMAND_REJECTED от декодера.

        МК ответил, но команду не распознал. Снимает ожидание в
        _send_command_with_ack тем же _command_ack_event — самой эмиссии
        исхода наружу здесь не делаем (её уже сделал декодер). Логику
        аварийной остановки выполняет Controller, подписанный на тот же
        сигнал.
        """
        self._command_ack_event.set()
        self._logger.debug(
            f'Ожидание ACK команды прервано по порту {self._port_name}: МК отверг команду'
        )

    async def on_interrupt_measuring(self) -> None:
        """Обработчик сигнала INTERRUPT_MEASURING.

        Аварийная остановка: связь с МК нарушена, протокольное
        взаимодействие невозможно. В отличие от on_stop_measuring:
          - не отправляем _set_foo_stage_command (МК либо не отвечает,
            либо нарушил контракт);
          - снимаем _command_ack_event, чтобы _send_command_with_ack,
            если он сейчас в ожидании, мгновенно вышел без ложного
            COMMAND_ACK_TIMEOUT (исход уже доставлен наружу аварийным
            сигналом, который и привёл к interrupt).
        Heartbeat останавливается через _cancel_task — CancelledError
        чисто прервёт его внутренний wait_for, без ложного DEVICE_LOST.
        Чтение прерывается через super().on_stop_measuring().

        Идемпотентен: повторный вызов после уже выполненной остановки
        (через STOP_MEASURING или INTERRUPT_MEASURING) — no-op. Это нужно
        для случая «штатная остановка → сбой команды → повторный
        INTERRUPT_MEASURING из Controller.stop()»: ресурсы уже освобождены
        в on_stop_measuring, повторный проход тут не должен ничего ломать.
        """
        if self._stopped:
            self._logger.debug(
                f'INTERRUPT_MEASURING для порта {self._port_name} проигнорирован: '
                f'остановка уже выполнена'
            )
            return
        self._stopped = True
        self._logger.warning(f'Аварийная остановка работы с портом {self._port_name}')
        await self._cancel_task(self._heartbeat_task)
        self._heartbeat_task = None
        self._command_ack_event.set()
        await super().on_stop_measuring()

    # =============================================================
    # =================== Внутренняя логика =======================
    # =============================================================

    async def setup(self) -> None:
        """Открытие COM-порта и сброс флага остановки.

        Сбрасывает _stopped перед каждым входом в контекстный менеджер,
        чтобы объект можно было переиспользовать во втором `async with`
        без ручного reset'а.
        """
        self._stopped = False
        await super().setup()

    async def cleanup(self) -> None:
        """Завершение работы порта.

        Отменяет все активные задачи и закрывает порт.
        """
        await self._cancel_task(self._heartbeat_task)
        self._heartbeat_task = None
        await super().cleanup()

    async def _heartbeat_loop(self) -> None:
        """Периодическая отправка heartbeat команды и ожидание ACK.

        Каждые _HEARTBEAT_PERIOD секунд отправляет команду на МК
        и ждёт ACK через asyncio.Event в течение _RESPONSE_TIMEOUT секунд.
        При таймауте эмиттит DEVICE_LOST.
        Завершается корректно при отмене (asyncio.CancelledError).
        """
        self._logger.debug(f'Запуск heartbeat loop по порту {self._port_name}')
        try:
            while True:
                await asyncio.sleep(_HEARTBEAT_PERIOD)

                self._logger.debug(f'Отправка heartbeat по порту {self._port_name}')
                self._heartbeat_ack_event.clear()
                await bus.heartbeat_sent.emit()
                await self._send_command(self._heartbeat_command)
                try:
                    await asyncio.wait_for(
                        self._heartbeat_ack_event.wait(),
                        timeout=_RESPONSE_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    self._logger.error(
                        f'Таймаут heartbeat по порту {self._port_name} '
                        f'({_RESPONSE_TIMEOUT} сек) — устройство не отвечает'
                    )
                    await bus.device_lost.emit()
                    return

        except asyncio.CancelledError:
            self._logger.debug(f'Heartbeat loop остановлен по порту {self._port_name}')
            raise

    @staticmethod
    async def _cancel_task(task: Optional[asyncio.Task]) -> None:
        """Отменяет задачу и ожидает её завершения.

        Args:
            task: Задача для отмены. Если None или завершена — ничего не делает.
        """
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _send_command(self, command: bytes) -> None:
        """Отправка команды по COM-порту без ожидания подтверждения.

        Args:
            command (bytes): Команда для отправки на плату МК.
        """
        self._logger.debug(f'Отправка команды {command}')
        self._port_writer.write(command)
        await self._port_writer.drain()

    async def _send_command_with_ack(self, command: bytes) -> None:
        """Отправка команды с ожиданием подтверждения от МК.

        Эмиттит COMMAND_SENT (декодер сохраняет состояние),
        отправляет команду и ждёт пока _command_ack_event будет выставлен.
        Событие может быть выставлено тремя путями:
          1. on_command_ack          — штатный ACK (декодер уже эмиттнул COMMAND_ACK);
          2. on_command_rejected     — МК отверг команду (декодер уже эмиттнул COMMAND_REJECTED);
          3. on_interrupt_measuring  — аварийная остановка (контроллер уже эмиттнул INTERRUPT_MEASURING).

        Во всех трёх случаях исход доставлен наружу другим путём — здесь
        ничего не эмиттим. Эмиссия делается только если истёк таймаут:
        COMMAND_ACK_TIMEOUT означает «МК не ответил вообще никак».

        Args:
            command (bytes): Команда для отправки на плату МК.
        """
        self._command_ack_event.clear()
        await bus.command_sent.emit()
        self._logger.debug(f'Отправка команды с подтверждением {command}')
        self._port_writer.write(command)
        await self._port_writer.drain()
        try:
            await asyncio.wait_for(
                self._command_ack_event.wait(),
                timeout=_RESPONSE_TIMEOUT
            )
        except asyncio.TimeoutError:
            self._logger.error(
                f'Таймаут подтверждения команды по порту {self._port_name} '
                f'({_RESPONSE_TIMEOUT} сек)'
            )
            await bus.command_ack_timeout.emit()

    async def send_text_command(self, text: str) -> None:
        """Формирует текстовую команду в пакет протокола и отправляет на МК.

        Упаковывает текст через PacketBuilderImuText и отправляет с ожиданием
        подтверждения CONFIRM_RECEIVED_COMMAND от МК.

        Args:
            text (str): Текст команды для отправки.

        Raises:
            ValueError: Если текст не кодируется в ASCII или превышает 255 байт.
        """
        packet = PacketBuilderImuText.build_text_command(text)
        self._logger.debug(f'Отправка текстовой команды: "{text}"')
        await self._send_command_with_ack(packet)