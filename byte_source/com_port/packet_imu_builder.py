# System imports

# External imports

# User imports
from byte_source.com_port.packet_builder import BasePacketBuilder

#########################


class PacketImuBuilder(BasePacketBuilder):
    """Построитель пакетов протокола IMU COM-порта.

    Определяет заголовок и форматы пакетов конкретного протокола IMU.
    Заголовок намеренно независим от заголовка декодера — в данном
    проекте они совпадают, но могут отличаться в других реализациях.

    Пример использования:
        packet = PacketImuBuilder.build_text_command('CALIBRATE')
        self._port_writer.write(packet)
    """

    # Заголовок пакета (независим от заголовка декодера)
    _HEADER: bytes = bytes([0xC8, 0x8C])

    # Форматы пакетов протокола IMU
    _TEXT_COMMAND_FORMAT: bytes = bytes([0xAB])
