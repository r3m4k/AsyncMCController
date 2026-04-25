# System imports
from typing import Any, TypeAlias, Callable, Awaitable
from collections import defaultdict

# External imports

# User imports
from .signals import Signals


#########################


# Тип асинхронного обработчика сигнала: любая корутинная функция, возвращающая None.
Subscriber: TypeAlias = Callable[..., Awaitable[None]]

# ------------------------------------------

class SignalBus:
    """
    Универсальная асинхронная сигнальная шина для слабосвязанного
    взаимодействия между объектами.

    Обеспечивает механизм подписки и публикации сигналов (publish-subscribe).
    Обработчики одного сигнала вызываются последовательно в порядке подписки.
    Исключение в любом из обработчиков прерывает дальнейшую доставку сигнала.

    Для типизированного интерфейса конкретного приложения используйте AppBus.

    Пример использования:
        bus = SignalBus()

        async def on_new_byte(bt: bytes) -> None:
            print(f'Получен байт: {bt}')

        bus.subscribe(Signals.NEW_BYTE, on_new_byte)
        await bus.emit(Signals.NEW_BYTE, b'\\xff')
    """

    def __init__(self):
        self._subscribers: dict[Signals, list[Subscriber]] = defaultdict(list)

    def subscribe(self, signal: Signals, handler: Subscriber) -> None:
        """
        Подписать обработчик на сигнал.

        Args:
            signal:  Сигнал из перечисления Signals.
            handler: Асинхронный обработчик, вызываемый при получении сигнала.
        """
        self._subscribers[signal].append(handler)

    def unsubscribe(self, signal: Signals, handler: Subscriber) -> None:
        """
        Отписать обработчик от сигнала.

        Args:
            signal:  Сигнал из перечисления Signals.
            handler: Ранее зарегистрированный обработчик.

        Raises:
            ValueError: Если обработчик не найден среди подписчиков данного сигнала.
        """
        try:
            self._subscribers[signal].remove(handler)
        except ValueError:
            raise ValueError(f"Обработчик '{handler}' не найден среди подписчиков сигнала '{signal}'")

    async def emit(self, signal: Signals, *args: Any, **kwargs: Any) -> None:
        """
        Отправить сигнал всем подписчикам последовательно.

        Args:
            signal:   Сигнал из перечисления Signals.
            *args:    Позиционные аргументы, передаваемые обработчикам.
            **kwargs: Именованные аргументы, передаваемые обработчикам.
        """
        for handler in self._subscribers[signal]:
            await handler(*args, **kwargs)
