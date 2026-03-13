import asyncio
from kivy.app import App
from kivy_garden.mapview import MapMarker, MapView
from kivy.clock import Clock
from lineMapLayer import LineMapLayer
from datasource import Datasource, FileDatasource

class MapViewApp(App):
    def __init__(self, **kwargs):
        super().__init__()
        # Ініціалізуємо змінні
        self.car_marker = None
        self.datasource = None
        self.path_layer = None

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
        # Підключаємо джерело даних (CSV файл)
        self.datasource = Datasource(user_id=1)
        
        # Запускаємо функцію update кожну 1 секунду
        Clock.schedule_interval(self.update, 1.0)

    def update(self, *args):
        """
        Викликається регулярно для оновлення мапи
        """
        # Отримуємо нові точки з нашого джерела даних
        new_points = self.datasource.get_new_points()
        
        for point in new_points:
            lat, lon, road_state = point
            
            # 1. Оновлюємо позицію машини
            self.update_car_marker((lat, lon))
            
            # 2. Додаємо точку до лінії маршруту
            self.path_layer.add_point((lat, lon))
            
            # 3. Перевіряємо стан дороги і ставимо відповідні маркери
            if road_state == "bump":
                self.set_bump_marker((lat, lon))
            elif road_state == "pothole":
                self.set_pothole_marker((lat, lon))
            
            # Центруємо мапу на машинці
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