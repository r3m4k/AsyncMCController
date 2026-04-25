# System imports
import asyncio
from typing import Callable

# External imports

# User imports
from logger import app_logger
from signal_bus import bus

#########################

_logger = app_logger.get_logger('App.Controller')

# ------------------------------------------


class Controller:
    """Контроллер приложения — управляет жизненным циклом измерения.

    Запускает измерение через сигнал START_MEASURING и останавливает
    через сигнал STOP_MEASURING в одной из двух ситуаций:
      - штатное завершение: check_condition() вернул False
                            (например, собрано достаточно пакетов данных);
      - аварийное завершение: один из сигналов HANDSHAKE_FAILED / DEVICE_LOST
                              / COMMAND_ACK_TIMEOUT выставил флаг _force_stop.

    В обоих случаях STOP_MEASURING эмиттится ровно один раз — после цикла
    проверки в методе stop(). Обработчики аварийных сигналов не эмиттят
    STOP_MEASURING самостоятельно, чтобы исключить рекурсию через
    on_stop_measuring -> _send_command_with_ack -> COMMAND_ACK_TIMEOUT ->
    on_command_ack_timeout -> on_stop_measuring.

    Attributes:
        _check_condition (Callable): Функция-условие продолжения измерения.
                                     Возвращает True пока измерение должно продолжаться.
        _force_stop (bool):          Флаг аварийного завершения. Выставляется
                                     обработчиками аварийных сигналов и прерывает
                                     цикл ожидания в stop().

    Пример использования:
        N = 5000
        controller = Controller(
            check_condition = lambda: decoder.data_len < N
        )
        async with com_port, decoder:
            await controller.start()
            await controller.stop()
    """

    def __init__(self, check_condition: Callable[[], bool]):
        self._check_condition: Callable[[], bool] = check_condition
        self._force_stop:      bool               = False

        # Самостоятельная подписка на события шины
        bus.handshake_failed.subscribe(self)
        bus.device_lost.subscribe(self)
        bus.command_ack_timeout.subscribe(self)

    async def start(self) -> None:
        """Запускает измерение через сигнал START_MEASURING.

        Raises:
            asyncio.CancelledError: При внешней отмене задачи.
        """
        _logger.info('Запуск измерения')
        await bus.start_measuring.emit()

    async def stop(self) -> None:
        """Ожидает условия остановки и эмиттит STOP_MEASURING.

        Цикл прерывается при одном из двух условий:
          - check_condition() вернул False (штатное завершение);
          - _force_stop выставлен аварийным обработчиком.

        Управление передаётся event loop между проверками через
        asyncio.sleep(0), чтобы не блокировать другие задачи.

        Raises:
            asyncio.CancelledError: При внешней отмене задачи.
        """
        _logger.debug('Запуск цикла проверки условия остановки')
        try:
            while self._check_condition() and not self._force_stop:
                await asyncio.sleep(0)

            if self._force_stop:
                _logger.info('Аварийная остановка измерения')
            else:
                _logger.info('Условие остановки выполнено — остановка измерения')

            await bus.stop_measuring.emit()

        except asyncio.CancelledError:
            _logger.debug('Цикл проверки условия остановлен')
            raise

    async def on_handshake_failed(self) -> None:
        """Обработчик сигнала HANDSHAKE_FAILED — выставляет _force_stop.

        Вызывается когда рукопожатие с МК не выполнено за отведённое время.
        STOP_MEASURING будет эмиттирован из stop() после выхода из цикла.
        """
        _logger.critical('Рукопожатие с МК не выполнено — аварийная остановка')
        self._force_stop = True

    async def on_device_lost(self) -> None:
        """Обработчик сигнала DEVICE_LOST — выставляет _force_stop.

        Вызывается когда МК не ответил на heartbeat за отведённое время.
        STOP_MEASURING будет эмиттирован из stop() после выхода из цикла.
        """
        _logger.critical('Устройство не отвечает — аварийная остановка')
        self._force_stop = True

    async def on_command_ack_timeout(self) -> None:
        """Обработчик сигнала COMMAND_ACK_TIMEOUT — выставляет _force_stop.

        Вызывается когда МК не подтвердил выполнение отправленной команды
        за отведённое время. Трактуется как некорректное поведение устройства.
        STOP_MEASURING будет эмиттирован из stop() после выхода из цикла.
        """
        _logger.critical('МК не подтвердил команду — аварийная остановка')
        self._force_stop = True