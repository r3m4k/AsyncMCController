# System imports
import asyncio
import logging
from pprint import pformat

# External imports

# User imports
from logger import app_logger
from signal_bus import bus
from byte_source.com_port import AsyncComPortSetting
from decoding.imu_decoding import ImuDecoder
from controller.controller import Controller

#########################

# Количество пакетов данных для сбора
N = 5000


async def main() -> None:

    # app_logger.set_log_level(logging.DEBUG)

    # Инициализация источника данных
    setting = AsyncComPortSetting()
    setting.configure_source()              # сбор параметров: из кэша или через консоль
    com_port = setting.get_bytes_source()   # подписывается на START/STOP_MEASURING

    # Инициализация декодера
    decoder = ImuDecoder()

    # Инициализация контроллера
    controller = Controller(               # подписывается на HANDSHAKE_FAILED, DEVICE_LOST
        check_condition = lambda: decoder.data_len < N
    )

    app_logger.debug(f'Список подписчиков сигнальной шины:'
                     f'{pformat(bus.get_subscribers())}')

    # ------------------------------------------
    # Запуск
    # ------------------------------------------
    async with com_port, decoder:
        await controller.start()
        await controller.stop()

    print(decoder)


if __name__ == '__main__':
    asyncio.run(main())
