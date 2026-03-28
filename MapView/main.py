import asyncio
from pathlib import Path
from kivy.app import App
from kivy_garden.mapview import MapMarker, MapView
from kivy.clock import Clock
from lineMapLayer import LineMapLayer
from datasource import Datasource, FileDatasource
from config import ENABLE_CSV_FALLBACK

class MapViewApp(App):
    def __init__(self, **kwargs):
        super().__init__()
        # Ініціалізуємо змінні
        self.car_marker = None
        self.primary_ds = None
        self.fallback_ds = None
        self.current_ds = None
        self.path_layer = None
        self.no_data_counter = 0

    def build(self):
        """
        Ініціалізує мапу MapView(zoom, lat, lon)
        """
        # Встановлюємо початкові координати (наприклад, центр Києва, як у нашому FileDatasource)
        self.mapview = MapView(zoom=16, lat=50.4501, lon=30.5234)
        
        # Ініціалізуємо шар для малювання лінії маршруту і додаємо на мапу
        self.path_layer = LineMapLayer(color=[0, 0, 1, 1], width=2) # Синя лінія
        self.mapview.add_layer(self.path_layer)
        
        return self.mapview

    def on_start(self):
        """
        Встановлює необхідні маркери, викликає функцію для оновлення мапи
        """
        # Підключаємо джерело даних: websocket основне, CSV fallback для тесту/розробки
        self.primary_ds = Datasource(user_id=1)
        if ENABLE_CSV_FALLBACK:
            csv_path = Path(__file__).resolve().parent / "data" / "data.csv"
            self.fallback_ds = FileDatasource(str(csv_path))
            print(f"MAP STATUS: CSV fallback enabled, file {csv_path}")
        else:
            self.fallback_ds = None
            print("MAP STATUS: CSV fallback disabled")
        self.current_ds = self.primary_ds

        # Запускаємо функцію update кожну 1 секунду
        Clock.schedule_interval(self.update, 1.0)

    def update(self, *args):
        """
        Викликається регулярно для оновлення мапи
        """
        print(f"MAP STATUS: Primary DS connected={self.primary_ds.is_connected()}, stale={self.primary_ds.is_stale()}")
        if self.primary_ds.is_connected() and not self.primary_ds.is_stale():
            ws_points = self.primary_ds.get_new_points()
            if ws_points:
                self.current_ds = self.primary_ds
                source = "websocket"
            else:
                source = "websocket-empty"
        else:
            source = "websocket-stale"
            ws_points = []

        if source in ("websocket-empty", "websocket-stale"):
            if self.fallback_ds is not None:
                csv_points = self.fallback_ds.get_new_points()
                if csv_points:
                    self.current_ds = self.fallback_ds
                    source = "csv-fallback"
                    new_points = csv_points
                else:
                    new_points = []
            else:
                new_points = []
        else:
            new_points = ws_points

        if not new_points:
            self.no_data_counter += 1
            print(f"MAP STATUS: no points from {source} (count={self.no_data_counter})")
            return

        self.no_data_counter = 0
        print(f"MAP STATUS: receiving from {source}, points={len(new_points)}")

        for point in new_points:
            lat, lon, road_state = point
            self.update_car_marker((lat, lon))
            self.path_layer.add_point((lat, lon))
            if road_state == "bump":
                self.set_bump_marker((lat, lon))
            elif road_state == "pothole":
                self.set_pothole_marker((lat, lon))
            self.mapview.center_on(lat, lon)

    def update_car_marker(self, point):
        """
        Оновлює відображення маркера машини на мапі
        """
        lat, lon = point
        if self.car_marker is None:
            # Створюємо маркер машини (бажано додати source='car_icon.png', якщо є картинка)
            self.car_marker = MapMarker(lat=lat, lon=lon)
            self.mapview.add_marker(self.car_marker)
        else:
            # Якщо маркер вже є, просто оновлюємо його координати
            self.car_marker.lat = lat
            self.car_marker.lon = lon

    def set_pothole_marker(self, point):
        """
        Встановлює маркер для ями
        """
        lat, lon = point
        # Створюємо маркер для ями. (Якщо є картинка, додайте source='pothole.png')
        pothole_marker = MapMarker(lat=lat, lon=lon)
        self.mapview.add_marker(pothole_marker)

    def set_bump_marker(self, point):
        """
        Встановлює маркер для нерівності / лежачого поліцейського
        """
        lat, lon = point
        # Створюємо маркер для нерівності. (Якщо є картинка, додайте source='bump.png')
        bump_marker = MapMarker(lat=lat, lon=lon)
        self.mapview.add_marker(bump_marker)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(MapViewApp().async_run(async_lib="asyncio"))
    loop.close()