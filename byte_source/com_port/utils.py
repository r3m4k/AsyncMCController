# -*- coding: utf-8 -*-
"""Утилиты для работы с COM-портами.

Содержит функцию `get_ComPorts()`, которая собирает информацию о всех
доступных COM-портах системы с помощью библиотеки pyserial. Результат
возвращается в виде словаря, удобного для дальнейшей обработки.
"""

# System imports
import os

# External imports
if os.name == 'nt':  # sys.platform == 'win32':
    from serial.tools.list_ports_windows import comports
elif os.name == 'posix':
    from serial.tools.list_ports_posix import comports

# User imports

##########################################################


def get_ComPorts() -> dict[str, dict[str, str]]:
    """
    Возвращает информацию о всех подключённых COM-портах.

    Функция использует `serial.tools.list_ports.comports()` для получения
    списка доступных портов и преобразует его в словарь, где ключом
    является имя порта (например, "COM3" или "/dev/ttyUSB0"), а значением —
    словарь с описанием и аппаратным идентификатором.

    Returns:
        dict[str, dict]: Словарь вида:
            {
                "COM1": {
                    "desc": "Описание порта",
                    "hwid": "Аппаратный идентификатор"
                },
                ...
            }
        Если порты отсутствуют, возвращается пустой словарь.
    """
    iterator = comports(include_links=False)
    res = {}
    for n, (_port, desc, hwid) in enumerate(iterator, 1):
        res[_port] = {"desc": desc, "hwid": hwid}
    return res
