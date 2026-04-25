# -*- coding: utf-8 -*-
"""Модуль для работы с асинхронными источниками байтовых данных.

Предоставляет два абстрактных базовых класса:
    AsyncBytesSource        — интерфейс самого источника с поддержкой
                              асинхронного контекстного менеджера.
    AsyncBytesSourceFactory — интерфейс фабрики, отделяющей этап настройки
                              параметров источника от этапа его создания.
"""

# System imports
from abc import ABC, abstractmethod

# External imports

# User imports

#########################


class AsyncBytesSource(ABC):
    """Абстрактный базовый класс для асинхронного источника байтов.

    Определяет интерфейс для чтения байтов и гарантирует корректную
    инициализацию и освобождение ресурсов через протокол асинхронного
    контекстного менеджера.

    Методы:
        setup():              Подготовка ресурсов (открытие порта, файла и т.д.).
        cleanup():            Освобождение ресурсов (закрытие порта, файла).
        read_byte() -> bytes: Асинхронное чтение одного байта.

    Пример использования:
        async with AsyncComPort('COM3', 115200) as source:
            byte = await source.read_byte()
    """

    @abstractmethod
    async def setup(self) -> None:
        """Выполняет подготовку ресурсов перед чтением.

        Вызывается автоматически при входе в асинхронный контекстный менеджер.
        Должен быть реализован в наследнике.
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Освобождает ресурсы после завершения работы.

        Вызывается автоматически при выходе из асинхронного контекстного менеджера.
        Должен быть реализован в наследнике.
        """
        pass

    @abstractmethod
    async def read_byte(self) -> bytes:
        """Асинхронно читает один байт из источника.

        Returns:
            bytes: Прочитанный байт (объект bytes длины 1).

        Raises:
            ReadError: Если произошла ошибка чтения (таймаут, потеря соединения,
                достигнут конец файла и т.п.). Наследники могут выбрасывать
                более специфичные исключения, унаследованные от `ReadError`.
        """
        pass

    async def __aenter__(self) -> 'AsyncBytesSource':
        """Вход в асинхронный контекстный менеджер.

        Вызывает `setup()` и возвращает экземпляр источника.
        """
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Выход из асинхронного контекстного менеджера.

        Вызывает `cleanup()`. Возвращает `False`, чтобы исключения,
        возникшие внутри блока `async with`, пробрасывались дальше.
        """
        await self.cleanup()
        return False


# ------------------------------------------


class AsyncBytesSourceFactory(ABC):
    """Абстрактная фабрика для создания асинхронных источников байтов.

    Разделяет жизненный цикл источника на два этапа:
        1. `configure_source()` — сбор и валидация параметров (из кэша конфига,
           через интерактивный ввод, из аргументов командной строки и т.п.).
        2. `get_bytes_source()` — создание и возврат готового источника.

    Такое разделение позволяет настраивать источник в одном месте
    (например, на старте приложения) и создавать его в другом — с гарантией,
    что параметры уже собраны и валидны.

    Пример наследования:
        class AsyncComPortSetting(AsyncBytesSourceFactory):
            def configure_source(self) -> None:
                self._port_name = ...
                self._baudrate  = ...

            def get_bytes_source(self) -> AsyncBytesSource:
                return AsyncComPort(self._port_name, self._baudrate)
    """

    @abstractmethod
    def configure_source(self) -> None:
        """Собирает и валидирует параметры источника.

        Реализация определяет, откуда брать параметры — из конфига,
        консоли, аргументов, и т.п. Метод синхронный: настройка обычно
        выполняется до запуска event loop и не требует await.
        """
        pass

    @abstractmethod
    def get_bytes_source(self) -> AsyncBytesSource:
        """Создаёт и возвращает асинхронный источник байтов.

        Если метод вызван до `configure_source()`, реализация должна
        самостоятельно вызвать `configure_source()` — чтобы клиент мог
        использовать фабрику как одну точку входа:

            source = MyFactory().get_bytes_source()

        Returns:
            AsyncBytesSource: Готовый к использованию источник.

        Raises:
            RuntimeError: Если после настройки не удалось получить
                валидные параметры для создания источника.
        """
        pass


# ------------------------------------------


class AsyncBytesSourceFactory(ABC):
    """Абстрактная фабрика асинхронных источников байтов.

    Единый интерфейс для фабрик, создающих конкретные реализации
    `AsyncBytesSource` (COM-порт, файл, сетевое соединение и т.д.).
    Параметры источника собираются в `configure_source()` и применяются
    при создании объекта в `get_bytes_source()`.

    Если к моменту вызова `get_bytes_source()` источник ещё не настроен,
    `configure_source()` вызывается автоматически (ленивая настройка).

    Методы:
        configure_source():                    Интерактивный или автоматический сбор параметров.
        get_bytes_source() -> AsyncBytesSource: Создание настроенного источника.

    Пример наследования:
        class MyFactory(AsyncBytesSourceFactory):
            def configure_source(self) -> None:
                self._param = input('Введите параметр: ')

            def get_bytes_source(self) -> AsyncBytesSource:
                if self._param is None:
                    self.configure_source()
                return MySource(self._param)
    """

    @abstractmethod
    def configure_source(self) -> None:
        """Собирает параметры источника (из конфига, консоли, окружения и т.д.).

        Вызывается либо явно пользователем фабрики, либо автоматически
        из `get_bytes_source()` при отсутствии заданных параметров.
        """
        pass

    @abstractmethod
    def get_bytes_source(self) -> AsyncBytesSource:
        """Возвращает настроенный экземпляр источника байтов.

        Если источник не был настроен — вызывает `configure_source()`
        самостоятельно перед созданием объекта.

        Returns:
            AsyncBytesSource: Готовый к использованию источник байтов.
        """
        pass
