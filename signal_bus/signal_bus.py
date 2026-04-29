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

    def get_subscribers(self) -> dict[Signals, list[object]]:
        """
        Возвращает текущих подписчиков всех сигналов в виде объектов-владельцев.

        Для каждого сигнала из Signals формирует список объектов, которым
        принадлежат зарегистрированные bound-методы (определяется через
        атрибут `__self__`). Если зарегистрирован чистый callable без
        привязки к объекту (например, обычная функция или лямбда),
        в список кладётся сам callable.

        Сигналы, на которые никто не подписан, попадают в результат
        с пустым списком — это удобно для отладки: видно, какие сигналы
        известны шине и ни на один из них нет подписчиков.

        Возвращается обычный `dict`, а не `defaultdict` — чтобы внешний
        код не мог случайно изменить внутреннее состояние шины через
        возвращённый объект.

        Returns:
            dict[Signals, list[object]]: Словарь {сигнал: [объекты-подписчики]}.
        """
        result: dict[Signals, list[object]] = {}
        for signal in Signals:
            handlers = self._subscribers.get(signal, [])
            owners: list[object] = []
            for handler in handlers:
                # bound-метод хранит объект-владельца в __self__;
                # для свободных функций / лямбд кладём сам callable.
                owner = getattr(handler, '__self__', handler)
                owners.append(owner)
            result[signal] = owners
        return result