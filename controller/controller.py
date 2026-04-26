# System imports
import asyncio
from typing import Any, Callable

# External imports

# User imports
from logger import app_logger
from signal_bus import bus
from byte_source.read_error import ReadError

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
                            в холостой режим. Если во время самой штатной
                            остановки выставится _force_stop (например, МК
                            не подтвердил _set_foo_stage_command), Controller
                            дополнительно эмиттит INTERRUPT_MEASURING, чтобы
                            гарантировать аварийное закрытие ресурсов.
      - аварийное завершение: один из сигналов HANDSHAKE_FAILED / DEVICE_LOST
                              / COMMAND_ACK_TIMEOUT / COMMAND_REJECTED /
                              READ_ERROR выставил флаг _force_stop;
                              эмиттит INTERRUPT_MEASURING — порт закрывается
                              без попыток послать МК завершающие команды.

    В обоих случаях соответствующий сигнал эмиттится только из stop().
    Обработчики аварийных сигналов не эмиттят STOP/INTERRUPT_MEASURING
    самостоятельно, чтобы исключить рекурсию через
    on_stop_measuring -> _send_command_with_ack -> COMMAND_ACK_TIMEOUT ->
    on_command_ack_timeout -> on_stop_measuring.

    Помимо управления, контроллер подписан на PACKAGE_READY и выводит
    в консоль номер каждого принятого пакета через `\\r`, перезаписывая
    одну строку — чтобы 5000 пакетов не растягивали вывод. Финальный
    перевод строки делает вызывающий код, не контроллер.

    Attributes:
        _check_condition (Callable): Функция-условие продолжения измерения.
                                     Возвращает True пока измерение должно продолжаться.
        _force_stop (bool):          Флаг аварийного завершения. Выставляется
                                     обработчиками аварийных сигналов и прерывает
                                     цикл ожидания в stop(); в этом случае вместо
                                     STOP_MEASURING эмиттится INTERRUPT_MEASURING.
                                     Также проверяется повторно после STOP_MEASURING —
                                     если флаг был выставлен во время штатной остановки,
                                     дополнительно эмиттится INTERRUPT_MEASURING.

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
        bus.package_ready.subscribe(self)
        bus.read_error.subscribe(self)
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

        Логика остановки:
          1. Цикл прерывается при одном из двух условий:
             - check_condition() вернул False — штатное завершение;
             - _force_stop выставлен аварийным обработчиком — аварийное завершение.
          2. Если _force_stop выставлен — эмиттит INTERRUPT_MEASURING и завершается.
          3. Если _force_stop не выставлен — эмиттит STOP_MEASURING.
          4. После STOP_MEASURING повторно проверяет _force_stop: его мог выставить
             обработчик, сработавший внутри STOP_MEASURING (например,
             COMMAND_ACK_TIMEOUT при попытке перевести МК в холостой режим).
             В этом случае дополнительно эмиттится INTERRUPT_MEASURING для
             гарантированного аварийного закрытия ресурсов.

        Управление передаётся event loop между проверками через
        asyncio.sleep(0), чтобы не блокировать другие задачи.

        Идемпотентность INTERRUPT_MEASURING на стороне ComPort обеспечивается
        в AsyncComPortImu.on_interrupt_measuring (повторные вызовы безопасны).

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
                return

            _logger.info('Условие остановки выполнено — остановка измерения')
            await bus.stop_measuring.emit()

            # Повторная проверка: _force_stop мог быть выставлен обработчиком,
            # сработавшим внутри STOP_MEASURING (например, COMMAND_ACK_TIMEOUT
            # при попытке перевести МК в холостой режим). Без этой проверки
            # семантический сигнал об аварии теряется.
            if self._force_stop:
                _logger.critical(
                    'Ошибка при штатной остановке — переход в аварийный режим'
                )
                await bus.interrupt_measuring.emit()

        except asyncio.CancelledError:
            _logger.debug('Цикл проверки условия остановлен')
            raise

    async def on_package_ready(self, data: Any) -> None:
        """Обработчик сигнала PACKAGE_READY — выводит номер пакета в консоль.

        Печать через `\\r` без перевода строки — каждый следующий вывод
        перезаписывает предыдущий, чтобы 5000 пакетов не превращались
        в 5000 строк. Финальный `\\n` после остановки — забота вызывающего
        кода.

        Args:
            data: Объект с атрибутом `package_num`. Тип не уточняется,
                чтобы Controller оставался независимым от конкретного
                декодера (утиная типизация).
        """
        print(f'\rПринят пакет #{data.package_num}', end='', flush=True)

    async def on_read_error(self, err: ReadError) -> None:
        """Обработчик сигнала READ_ERROR — выставляет _force_stop.

        Эмиттится AsyncComPort.reading_loop при перехвате ошибки чтения
        (физический обрыв соединения, сбой последовательного порта и т.п.).
        Цикл чтения уже завершился самостоятельно; дальнейшая остановка
        ресурсов произойдёт через INTERRUPT_MEASURING из stop().

        Args:
            err (ReadError): Исключение, которое привело к остановке чтения.
                             Сохраняется в логе для последующего анализа.
        """
        _logger.critical(f'Ошибка чтения из источника: {err} — аварийная остановка')
        self._force_stop = True

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
        _logger.critical('МК не распознал команду — программная ошибка ПК↔МК, аварийная остановка')
        self._force_stop = True