# System imports
import asyncio
from typing import Any, Callable, Optional
from multiprocessing import Queue

# External imports

# User imports
from async_mc_controller.logger import mc_logger
from async_mc_controller.byte_source.read_error import ReadError
from async_mc_controller.controller.controller import Controller

#########################

_logger = mc_logger.get_logger('MC.Controller.MpController')

# ------------------------------------------

class MpController(Controller):
    """
    Контроллер для взаимодействия с МК в дочернем процессе.
    Для взаимодействия с родительским процессом используются две очереди:
        - command_queue:    очередь для отправки команд из родительского процесса.
                            Чтение происходит в фоновом неблокирующем потоке через asyncio.to_thread.
        - response_queue:   очередь для отправки статусных сообщений и принятых пакетов данных.
    """

    def __init__(self, command_queue: Queue, response_queue: Queue):
        # Зададим остановку чтение данных по флагу
        self._stop_flag: bool = False
        super().__init__(check_condition = lambda: not self._stop_flag)

        # Сохраним переданные очереди для межпроцессорного взаимодействия
        self._command_queue = command_queue
        self._response_queue = response_queue

        # Таска по чтению очереди команд от родительского процесса
        self._reading_cmd_queue_task: Optional[asyncio.Task] = None

    # =============================================================
    # ======= Методы для работы в контекстном менеджере ===========
    # =============================================================

    async def __aenter__(self) -> 'MpController':
        """Запуск фоновой задачи по чтению self._command_queue."""
        await super().__aenter__()
        self._reading_cmd_queue_task = asyncio.create_task(self._reading_command_queue())
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Остановка всех фоновых задач контроллера."""
        _logger.debug('Остановка задач мультипроцессорного контроллера')
        for task in (self._reading_cmd_queue_task, ):
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        await super().__aexit__(exc_type, exc_val, exc_tb)
        return False

    # =============================================================
    # ================= Внутренняя логика =========================
    # =============================================================

    async def _reading_command_queue(self):
        """Неблокирующее чтение данных из self._command_queue"""

        # Блокирующее получение команды из self._command_queue
        def get_input_command(command_queue: Queue[str]) -> str:
            return command_queue.get()

        while not self._stop_flag:
            cmd: str = await asyncio.to_thread(get_input_command, self._command_queue)

            match cmd:
                case "START_MEASURING":
                    _logger.debug('Выполнение команды START_MEASURING')
                    await self.start_measuring()

                case "STOP_MEASURING":
                    _logger.debug('Выполнение команды STOP_MEASURING')
                    self._stop_flag = True

                case _:
                    _logger.error(f'Отработка команды {cmd} не предусмотрено!')

    # =============================================================
    # =================== Обработчики сигналов ====================
    # =============================================================

    async def on_package_ready(self, data: Any) -> None:
        """Обработчик сигнала PACKAGE_READY.

        Выводит номер пакета в консоль без перевода строки.

        Args:
            data: Объект с атрибутом `package_num`. Тип не уточняется,
                чтобы Controller оставался независимым от конкретного
                декодера (утиная типизация).
        """
        print(f'\rПринят пакет #{data.package_num}', end='', flush=True)

    async def on_read_error(self, err: ReadError) -> None:
        """Обработчик сигнала READ_ERROR.

        Эмиттится AsyncComPort.reading_loop при перехвате ошибки чтения
        (физический обрыв соединения, сбой последовательного порта и т.п.).

        Args:
            err (ReadError): Исключение, которое привело к остановке чтения.
                             Сохраняется в логе для последующего анализа.
        """
        _logger.critical(f'Ошибка чтения из источника: {err} — аварийная остановка')
        self._force_stop = True

    async def on_handshake_failed(self) -> None:
        """Обработчик сигнала HANDSHAKE_FAILED.

        Вызывается когда рукопожатие с МК не выполнено за отведённое время.
        """
        _logger.critical('Рукопожатие с МК не выполнено — аварийная остановка')
        self._force_stop = True

    async def on_device_lost(self) -> None:
        """Обработчик сигнала DEVICE_LOST.

        Вызывается когда МК не ответил на heartbeat за отведённое время.
        STOP_MEASURING будет эмиттирован из stop() после выхода из цикла.
        """
        _logger.critical('Устройство не отвечает — аварийная остановка')
        self._force_stop = True

    async def on_command_ack_timeout(self) -> None:
        """Обработчик сигнала COMMAND_ACK_TIMEOUT.

        Вызывается когда МК не подтвердил выполнение отправленной команды
        за отведённое время.
        """
        _logger.critical('МК не подтвердил команду — аварийная остановка')
        self._force_stop = True

    async def on_command_rejected(self) -> None:
        """Обработчик сигнала COMMAND_REJECTED — выставляет _force_stop.

        Вызывается когда МК ответил, но не распознал отправленную команду
        (прислал 'UNKNOWN_COMMAND').
        """
        _logger.critical('МК не распознал команду — программная ошибка ПК↔МК, аварийная остановка')
        self._force_stop = True