# System imports
import asyncio

# External imports

# User imports
from byte_source.com_port import AsyncComPortSetting
from decoding.imu_decoding import ImuDecoder
from controller.controller import Controller

#########################

# Количество пакетов данных для сбора
N = 5000


async def main() -> None:
    # ------------------------------------------
    # Инициализация источника данных
    # ------------------------------------------
    setting = AsyncComPortSetting()
    setting.configure_source()              # сбор параметров: из кэша или через консоль
    com_port = setting.get_bytes_source()   # подписывается на START/STOP_MEASURING

    # ------------------------------------------
    # Инициализация декодера
    # ------------------------------------------
    decoder = ImuDecoder()               # подписывается на NEW_BYTE, HEARTBEAT_SENT, COMMAND_SENT

    # ------------------------------------------
    # Инициализация контроллера
    # ------------------------------------------
    controller = Controller(               # подписывается на HANDSHAKE_FAILED, DEVICE_LOST
        check_condition = lambda: decoder.data_len < N
    )

    # ------------------------------------------
    # Запуск
    # ------------------------------------------
    async with com_port, decoder:
        await controller.start()
        await controller.stop()


if __name__ == '__main__':
    asyncio.run(main())
