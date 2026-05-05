# System imports
import asyncio
from typing import Any, Callable, Optional
from multiprocessing import Queue

# External imports

# User imports
from logger import app_logger
from byte_source.read_error import ReadError
from controller.controller import Controller

#########################

_logger = app_logger.get_logger('App.Controller.MpController')

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

        return False

    # =============================================================
    # ================= Внутренняя логика =========================
    # =============================================================

    async def wait_until_stop(self):
        await self.stop_measuring()

    async def _reading_command_queue(self):
        """Неблокирующее чтение данных из self._command_queue"""

        # Блокирующее получение команды из self._command_queue
        def get_input_command(command_queue: Queue[str]) -> str:
            return command_queue.get()

        while not self._stop_flag and not self._force_stop:
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
        try:
            await asyncio.to_thread(self._response_queue.put, data)
        except Exception as e:
            _logger.error(f"Не удалось отправить пакет в response_queue: {e}")
