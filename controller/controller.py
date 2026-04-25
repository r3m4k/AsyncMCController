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
    в одной из двух ситуаций:
      - штатное завершение: check_condition() вернул False
                            (например, собрано достаточно пакетов данных);
                            эмиттит STOP_MEASURING — порт штатно переводит МК
                            в холостой режим.
      - аварийное завершение: один из сигналов HANDSHAKE_FAILED / DEVICE_LOST
                              / COMMAND_ACK_TIMEOUT / COMMAND_REJECTED
                              выставил флаг _force_stop;
                              эмиттит INTERRUPT_MEASURING — порт закрывается
                              без попыток послать МК завершающие команды.

    В обоих случаях соответствующий сигнал эмиттится ровно один раз — после
    цикла проверки в методе stop(). Обработчики аварийных сигналов не эмиттят
    STOP/INTERRUPT_MEASURING самостоятельно, чтобы исключить рекурсию через
    on_stop_measuring -> _send_command_with_ack -> COMMAND_ACK_TIMEOUT ->
    on_command_ack_timeout -> on_stop_measuring.

    Attributes:
        _check_condition (Callable): Функция-условие продолжения измерения.
                                     Возвращает True пока измерение должно продолжаться.
        _force_stop (bool):          Флаг аварийного завершения. Выставляется
                                     обработчиками аварийных сигналов и прерывает
                                     цикл ожидания в stop(); в этом случае вместо
                                     STOP_MEASURING эмиттится INTERRUPT_MEASURING.

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
        bus.command_rejected.subscribe(self)

    async def start(self) -> None:
        """Запускает измерение через сигнал START_MEASURING.

        Raises:
            asyncio.CancelledError: При внешней отмене задачи.
        """
        _logger.info('Запуск измерения')
        await bus.start_measuring.emit()

    async def stop(self) -> None:
        """Ожидает условия остановки и эмиттит STOP_MEASURING или INTERRUPT_MEASURING.

        Цикл прерывается при одном из двух условий:
          - check_condition() вернул False — штатное завершение, эмиттится
            STOP_MEASURING (порт штатно переводит МК в холостой режим);
          - _force_stop выставлен аварийным обработчиком — эмиттится
            INTERRUPT_MEASURING (порт закрывается без команд МК).

        Управление передаётся event loop между проверками через
        asyncio.sleep(0), чтобы не блокировать другие задачи.

        TODO: пограничный случай — _force_stop может быть выставлен внутри
            on_stop_measuring (из-за COMMAND_ACK_TIMEOUT при попытке перевести
            МК в холостой). В этой ветке мы уже вышли из цикла и
            INTERRUPT_MEASURING не эмиттим. Сейчас ничего не ломается —
            ресурсы корректно закрываются через async with в main(),
            но сигнал об аварии теряется. Если упрёмся в реальной отладке,
            добавим повторную проверку _force_stop после STOP_MEASURING.

        Raises:
            asyncio.CancelledError: При внешней отмене задачи.
        """
        _logger.debug('Запуск цикла проверки условия остановки')
        try:
            while self._check_condition() and not self._force_stop:
                await asyncio.sleep(0)

            if self._force_stop:
                _logger.info('Аварийная остановка измерения')
                await bus.interrupt_measuring.emit()
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

    async def on_command_rejected(self) -> None:
        """Обработчик сигнала COMMAND_REJECTED — выставляет _force_stop.

        Вызывается когда МК ответил, но не распознал отправленную команду
        (прислал 'UNKNOWN_COMMAND'). Это программная ошибка контракта
        ПК↔МК — продолжение работы небезопасно. INTERRUPT_MEASURING будет
        эмиттирован из stop() после выхода из цикла.
        """
        _logger.critical('🛑 МК отверг команду — программная ошибка ПК↔МК, аварийная остановка')
        self._force_stop = True