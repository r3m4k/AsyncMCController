# System imports
import asyncio
import logging
from pprint import pformat
import multiprocessing as mp
from threading import Thread
from typing import Optional

# External imports
import numpy as np

# User imports
from logger import app_logger
from signal_bus import bus
from byte_source.com_port import AsyncComPortSetting, AsyncComPortImu
from decoding.imu_decoding import ImuDecoder, ImuData
from controller.controller import Controller
from controller.mp_controller import MpController


#########################


def run_in_subprocess(com_port_info, command_queue: mp.Queue, response_queue: mp.Queue) -> None:
    com_port = AsyncComPortImu(*com_port_info)
    decoder = ImuDecoder()
    controller = MpController(command_queue, response_queue)

    async def run_mc_coro():
        async with com_port, decoder, controller:
            await controller.wait_until_stop()

    asyncio.run(run_mc_coro())


received_data: list[ImuData] = []


class GuiProcess:
    def __init__(self) -> None:
        self._process: Optional[mp.Process] = None

        self._command_queue: mp.Queue = mp.Queue()
        self._response_queue: mp.Queue = mp.Queue()

        self._stop_flag = False

        self._com_port: Optional[AsyncComPortImu] = None
        self._reading_thread: Optional[Thread] = None

    def launch_mc(self):
        settings = AsyncComPortSetting()
        settings.configure_source()
        com_port_info = settings.get_port_info()

        self._process = mp.Process(target=run_in_subprocess,
                                   args=(com_port_info, self._command_queue, self._response_queue),
                                   daemon=True)

        self._reading_thread = Thread(target=self._start_collecting_data, daemon=True)

        self._process.start()
        self._reading_thread.start()

    def wait_for_stop(self):
        if self._process is not None:
            self._process.join()
            self._reading_thread.join()
        else:
            raise RuntimeError('Для начала запустите процесс!')

    def _start_collecting_data(self) -> None:
        self._command_queue.put("START_MEASURING")

        while not self._stop_flag:
            data: ImuData = self._response_queue.get()
            received_data.append(data)
            if data.package_num > 1000:
                self._stop_flag = True

        self._command_queue.put("STOP_MEASURING")

        print(f'len(received_data) = {len(received_data)}\n\n'
              f'Acc_X = {np.mean([data.acc.x_coord for data in received_data])}\n'
              f'Acc_Y = {np.mean([data.acc.y_coord for data in received_data])}\n'
              f'Acc_Z = {np.mean([data.acc.z_coord for data in received_data])}\n\n'
              f'Gyro_X = {np.mean([data.gyro.x_coord for data in received_data])}\n'
              f'Gyro_Y = {np.mean([data.gyro.y_coord for data in received_data])}\n'
              f'Gyro_Z = {np.mean([data.gyro.z_coord for data in received_data])}\n')


if __name__ == "__main__":
    gui_process = GuiProcess()
    gui_process.wait_for_stop()