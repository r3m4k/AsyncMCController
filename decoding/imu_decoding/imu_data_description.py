# System imports
from typing import NamedTuple

# External imports

# User imports

#############################################

class TriaxialData(NamedTuple):
    x_coord: float = 0.0
    y_coord: float = 0.0
    z_coord: float = 0.0

# ------------------------------------------

class ImuData(NamedTuple):
    package_num: int
    acc: TriaxialData
    gyro: TriaxialData

    def __str__(self):
        return (f'PackageNum: {self.package_num}\n\n'

                f'Acc:  {self.acc.x_coord}\n'
                f'      {self.acc.y_coord}\n'
                f'      {self.acc.z_coord}\n\n'

                f'Gyro: {self.gyro.x_coord}\n'
                f'      {self.gyro.y_coord}\n'
                f'      {self.gyro.z_coord}\n')

# ------------------------------------------

# Описание начала индексов данных внутри посылки
class ImuDataIndexes:
    """Смещения начала полей данных внутри бинарного пакета.
    Индексы отсчитываются от начала всей посылки, включая заголовок.
    """
    package_num = 4
    acc_index = 8
    gyro_index = 20
