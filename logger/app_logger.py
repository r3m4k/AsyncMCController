# -*- coding: utf-8 -*-
"""Модуль для настройки и использования логгера приложения.

Содержит класс `AppLogger`, который инкапсулирует настройку корневого логгера
и предоставляет методы для записи сообщений и получения дочерних логгеров.
При уровне логирования DEBUG автоматически запускается профилировщик yappi
для анализа времени выполнения корутин.

В модуле также определён глобальный экземпляр `app_logger`, который можно
импортировать и использовать во всём приложении.
"""

# System imports
import logging
import atexit
from pathlib import Path
from typing import Optional

# External imports
import yappi

# User imports
from config import config

#############################################

# Название корневого логгера приложения
_ROOT_LOGGER_NAME = 'App'

# ------------------------------------------

class AppLogger:
    """Класс для управления логгером приложения.

    Настраивает корневой логгер с файловым и/или консольным обработчиками
    согласно конфигурации. Предоставляет метод get_logger() для получения
    дочерних логгеров с явным именем для удобного анализа логов.

    При уровне логирования DEBUG автоматически запускает yappi для
    профилирования корутин asyncio. Результаты сохраняются в файл
    рядом с основным логом при завершении программы.

    Пример использования:
        # В каждом классе получаем дочерний логгер с явным именем
        logger = app_logger.get_logger('App.ComPort')
        logger.debug('Подключение к порту...')
    """

    def __init__(self):
        self._file_handler:    Optional[logging.Handler] = None
        self._console_handler: Optional[logging.Handler] = None

        # Создаём корневой логгер приложения
        self._logger = logging.getLogger(_ROOT_LOGGER_NAME)
        self._logger.setLevel(config.logger_config.log_level)

        # Настраиваем обработчики согласно конфигурации
        if config.logger_config.use_file:
            self._setup_file_handler(config.logger_config.log_dir)

        if config.logger_config.use_console:
            self._setup_console_handler()

        # Запускаем yappi в режиме DEBUG
        self._yappi_enabled = config.logger_config.log_level == logging.DEBUG
        if self._yappi_enabled:
            self._start_yappi()

    # =============================================================
    # =================== Настройка обработчиков ==================
    # =============================================================

    def _make_formatter(self) -> logging.Formatter:
        """Создаёт форматтер из текущей конфигурации."""
        return logging.Formatter(
            config.logger_config.log_format,
            config.logger_config.date_format
        )

    def _setup_file_handler(self, log_dir: Path) -> None:
        """Создаёт или заменяет файловый обработчик логгера.

        Если файл лога уже существует, переименовывает его в .bkp
        перед созданием нового.

        Args:
            log_dir (Path): Путь к директории для хранения файла лога.
        """
        log_dir  = Path(log_dir).resolve()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / config.logger_config.log_filename

        # Сохраняем предыдущий лог как резервную копию
        if log_file.exists():
            backup_file = log_dir / (log_file.name + '.bkp')
            if backup_file.exists():
                backup_file.unlink()
            log_file.rename(backup_file)

        # Удаляем старый обработчик если есть
        if self._file_handler is not None:
            self._logger.removeHandler(self._file_handler)
            self._file_handler.close()

        self._file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
        self._file_handler.setLevel(config.logger_config.log_level)
        self._file_handler.setFormatter(self._make_formatter())
        self._logger.addHandler(self._file_handler)

    def _setup_console_handler(self) -> None:
        """Создаёт или заменяет консольный обработчик логгера."""

        # Удаляем старый обработчик если есть
        if self._console_handler is not None:
            self._logger.removeHandler(self._console_handler)
            self._console_handler.close()

        self._console_handler = logging.StreamHandler()
        self._console_handler.setLevel(config.logger_config.log_level)
        self._console_handler.setFormatter(self._make_formatter())
        self._logger.addHandler(self._console_handler)

    # =============================================================
    # ===================== Управление yappi ======================
    # =============================================================

    def _start_yappi(self) -> None:
        """Запускает профилировщик yappi в режиме CPU clock.

        Используется clock_type='cpu', чтобы измерять реальное время
        выполнения корутин без учёта времени ожидания await.
        Результаты сохраняются автоматически при завершении программы.
        """
        yappi.set_clock_type('cpu')
        yappi.start(builtins=False)
        self._logger.debug('Профилировщик yappi запущен (clock_type=cpu)')

        # Регистрируем сохранение результатов при завершении программы
        atexit.register(self._save_yappi_stats)

    def _save_yappi_stats(self) -> None:
        """Останавливает yappi и сохраняет статистику в файл.

        Файл сохраняется рядом с основным логом в формате:
        <log_filename>.yappi_stats.log
        """
        yappi.stop()

        log_dir       = Path(config.logger_config.log_dir).resolve()
        yappi_logfile = log_dir / (config.logger_config.log_filename + '.yappi_stats.log')

        stats = yappi.get_func_stats()

        with open(yappi_logfile, 'w', encoding='utf-8') as f:
            # Сортируем по суммарному CPU времени — самые тяжёлые корутины наверху
            stats.sort('ttot')
            stats.print_all(out=f, columns={
                0: ('name',  80),
                1: ('ncall',  8),
                2: ('ttot',  10),
                3: ('tsub',  10),
                4: ('tavg',  10),
            })

        self._logger.debug(f'Статистика yappi сохранена: {yappi_logfile}')

    # =============================================================
    # =================== Публичные методы ========================
    # =============================================================

    def get_logger(self, name: str) -> logging.Logger:
        """Возвращает дочерний логгер с указанным именем.

        Дочерний логгер наследует уровень и обработчики корневого логгера,
        но пишет своё имя в каждую запись лога для удобной фильтрации.

        Args:
            name (str): Явное имя логгера. Рекомендуемый формат: 'App.ИмяКласса',
                        например 'App.ComPort', 'App.Decoder', 'App.Controller'.

        Returns:
            logging.Logger: Настроенный дочерний логгер.

        Пример использования:
            logger = app_logger.get_logger('App.ComPort')
            logger.info('Подключение к порту...')
        """
        return logging.getLogger(name)

    def set_log_dir(self, log_dir: Path) -> None:
        """Изменяет директорию для хранения логов.

        Пересоздаёт файловый обработчик в новой директории.
        Старый файл остаётся на диске.

        Args:
            log_dir (Path): Новая директория для хранения логов.
        """
        if config.logger_config.use_file:
            self._setup_file_handler(log_dir)

    # =============================================================
    # ================ Методы для записи сообщений ================
    # =============================================================

    def debug(self, msg: str, *args, **kwargs):
        self._logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        self._logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self._logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self._logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        self._logger.critical(msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs):
        self._logger.exception(msg, *args, **kwargs)
