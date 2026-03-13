import asyncio
import csv
import json
import websockets
from datetime import datetime
from kivy.logger import Logger
from pydantic import BaseModel, field_validator
from config import STORE_HOST, STORE_PORT

# --- Моделі даних для Store ---
class ProcessedAgentData(BaseModel):
    road_state: str
    user_id: int
    x: float
    y: float
    z: float
    latitude: float
    longitude: float
    timestamp: datetime

    @classmethod
    @field_validator("timestamp", mode="before")
    def check_timestamp(cls, value):
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            raise ValueError("Invalid timestamp format.")

# --- Джерело 1: Дані з серверу (WebSockets) ---
class Datasource:
    def __init__(self, user_id: int):
        self.index = 0
        self.user_id = user_id
        self.connection_status = None
        self._new_points = []
        asyncio.ensure_future(self.connect_to_server())

    def get_new_points(self):
        points = self._new_points
        self._new_points = []
        return points

    async def connect_to_server(self):
        uri = f"ws://{STORE_HOST}:{STORE_PORT}/ws/{self.user_id}"
        while True:
            Logger.debug("CONNECT TO SERVER")
            try:
                async with websockets.connect(uri) as websocket:
                    self.connection_status = "Connected"
                    while True:
                        data = await websocket.recv()
                        parsed_data = json.loads(data)
                        self.handle_received_data(parsed_data)
            except websockets.ConnectionClosedOK:
                self.connection_status = "Disconnected"
                Logger.debug("SERVER DISCONNECT")
            except Exception as e:
                Logger.error(f"WebSocket Connection Error: {e}")
                await asyncio.sleep(2) # Затримка перед повторною спробою

    def handle_received_data(self, data):
        Logger.debug(f"Received data: {data}")
        print(f"MAP RECEIVED DATA: {data}")
        processed_agent_data_list = sorted(
            [ProcessedAgentData(**item) for item in data],
            key=lambda v: v.timestamp,
        )
        new_points = [
            (p.latitude, p.longitude, p.road_state)
            for p in processed_agent_data_list
        ]
        self._new_points.extend(new_points)

# --- Джерело 2: Дані з CSV файлу (Для Кроку 1) ---
class FileDatasource:
    def __init__(self, filename: str):
        self.filename = filename
        self._new_points = []
        asyncio.ensure_future(self.read_file_data())

    def get_new_points(self):
        points = self._new_points
        self._new_points = []
        return points

    async def read_file_data(self):
        current_lat = 50.4501
        current_lon = 30.5234
        try:
            with open(self.filename, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    await asyncio.sleep(1)
                    z_val = int(row.get('Z', 0))
                    road_state = "bump" if abs(z_val - 16500) > 40 else "normal"
                    self._new_points.append((current_lat, current_lon, road_state))
                    current_lat += 0.0002
                    current_lon += 0.0002
        except Exception as e:
            Logger.error(f"FileDatasource: Помилка: {e}")