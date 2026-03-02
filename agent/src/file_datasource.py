from csv import reader
from datetime import datetime
from domain.accelerometer import Accelerometer
from domain.gps import Gps
from domain.aggregated_data import AggregatedData
import config


class FileDatasource:
    def __init__(
        self,
        accelerometer_filename: str,
        gps_filename: str,
    ) -> None:
        self.accelerometer_filename = accelerometer_filename
        self.gps_filename = gps_filename
        self.accelerometer_file = None
        self.gps_file = None
        self.accelerometer_reader = None
        self.gps_reader = None


    def read(self) -> AggregatedData:
        """Метод повертає дані отримані з датчиків"""
        try:
            accelerometer_line = next(self.accelerometer_reader)
            gps_line = next(self.gps_reader)
        except StopIteration:
            # Нескінченний цикл читання з файлу
            self.stopReading()
            self.startReading()
            accelerometer_line = next(self.accelerometer_reader)
            gps_line = next(self.gps_reader)

        return AggregatedData(
            Accelerometer(
                x=int(accelerometer_line[0]),
                y=int(accelerometer_line[1]),
                z=int(accelerometer_line[2]),
            ),
            Gps(
                longitude=float(gps_line[0]),
                latitude=float(gps_line[1]),
            ),
            datetime.now(),
            config.USER_ID,
        )

    def startReading(self):
        """Метод повинен викликатись перед початком читання даних"""
        self.accelerometer_file = open(self.accelerometer_filename, "r")
        self.gps_file = open(self.gps_filename, "r")
        self.accelerometer_reader = reader(self.accelerometer_file)
        self.gps_reader = reader(self.gps_file)
        next(self.accelerometer_reader)
        next(self.gps_reader)

    def stopReading(self):
        """Метод повинен викликатись для закінчення читання даних"""
        if self.accelerometer_file:
            self.accelerometer_file.close()
            self.accelerometer_file = None
        if self.gps_file:
            self.gps_file.close()
            self.gps_file = None
