# System imports
from enum import Enum

# External imports

# User imports

#########################


class Signals(Enum):
    """
    Перечисление всех сигналов, используемых в сигнальной шине.
    Централизованное хранение исключает опечатки при подписке и публикации.

    Пример использования:
        bus.subscribe(Signals.NEW_BYTE, handler)
        await bus.emit(Signals.NEW_BYTE, bt)
    """

    # ComPort → Decoder
    NEW_BYTE = 'NewByte'

    # Decoder → Controller
    PACKAGE_READY = 'PackageReady'

    # Controller → ComPort
    START_MEASURING     = 'StartMeasuring'
    STOP_MEASURING      = 'StopMeasuring'
    INTERRUPT_MEASURING = 'InterruptMeasuring'

    # ComPort → Controller
    READ_ERROR = 'ReadError'

    # Decoder → ImuComPort, Controller
    HANDSHAKE_DONE   = 'HandshakeDone'
    HEARTBEAT_ACK    = 'HeartbeatAck'
    COMMAND_ACK      = 'CommandAck'
    COMMAND_REJECTED = 'CommandRejected'

    # ImuComPort → Decoder
    HEARTBEAT_SENT = 'HeartbeatSent'
    COMMAND_SENT   = 'CommandSent'

    # ImuComPort → Controller, Decoder
    HANDSHAKE_FAILED      = 'HandshakeFailed'
    DEVICE_LOST           = 'DeviceLost'
    COMMAND_ACK_TIMEOUT   = 'CommandAckTimeout'
    IMU_HANDSHAKE_SUCCESS = 'ImuHandshakeSuccess'