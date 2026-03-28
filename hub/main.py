import logging
import json
from typing import List
from datetime import datetime
from fastapi import FastAPI
from redis import Redis
import paho.mqtt.client as mqtt

from app.entities.processed_agent_data import ProcessedAgentData
from app.interfaces.store_gateway import StoreGateway
from app.adapters.store_api_adapter import StoreApiAdapter
from config import (
    STORE_API_BASE_URL,
    REDIS_HOST,
    REDIS_PORT,
    BATCH_SIZE,
    MQTT_TOPIC,
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
)

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("app.log")],
)

redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT)
app = FastAPI()

hub_gateway = None  # Global variable to hold the gateway instance

@app.on_event("startup")
async def startup_event():
    global hub_gateway
    store_gateway = StoreApiAdapter(api_base_url=STORE_API_BASE_URL)
    hub_gateway = HubGateway(
        broker_host=MQTT_BROKER_HOST,
        broker_port=MQTT_BROKER_PORT,
        topic=MQTT_TOPIC,
        store_gateway=store_gateway,
        batch_size=BATCH_SIZE,
    )
    hub_gateway.connect()
    logging.info("Starting HubGateway MQTT loop...")
    hub_gateway.start()

@app.on_event("shutdown")
async def shutdown_event():
    if hub_gateway:
        hub_gateway.stop()
        logging.info("HubGateway stopped.")


class HubGateway:
    """Gateway that listens to edge MQTT data and forwards batches to the Store service."""

    def __init__(
        self,
        broker_host: str,
        broker_port: int,
        topic: str,
        store_gateway: StoreGateway,
        batch_size: int = 10,
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic = topic
        self.batch_size = batch_size
        self.store_gateway = store_gateway
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info("HubGateway connected to MQTT broker")
            client.subscribe(self.topic)
        else:
            logging.error(f"HubGateway failed to connect to MQTT broker with code: {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload: str = msg.payload.decode("utf-8", errors="ignore")
            agent_data_raw = json.loads(payload)

            road_state = agent_data_raw.get("road_state", "normal")
            agent = agent_data_raw.get("agent_data", {})
            z_axis = agent.get("z_axis", 16000)

            if z_axis > 17500 or z_axis < 15000:
                road_state = "bump"
                logging.info(f"BUMP DETECTED! Z-axis: {z_axis}")

            timestamp = agent_data_raw.get("timestamp")
            if not isinstance(timestamp, str):
                timestamp = datetime.now().isoformat()

            processed_agent_data = ProcessedAgentData(
                road_state=road_state,
                agent_data=agent,
                user_id=int(agent_data_raw.get("user_id", 1)),
                timestamp=timestamp,
            )

            redis_client.lpush("processed_agent_data", processed_agent_data.model_dump_json())

            if redis_client.llen("processed_agent_data") >= self.batch_size:
                self._flush_batch()

        except Exception as e:
            logging.error(f"HUB GATEWAY ERROR: {e}")

    def _flush_batch(self):
        processed_agent_data_batch = []
        for _ in range(self.batch_size):
            raw_item = redis_client.lpop("processed_agent_data")
            if isinstance(raw_item, bytes):
                item_str = raw_item.decode("utf-8", errors="ignore")
                item_dict = json.loads(item_str)
                processed_agent_data_batch.append(ProcessedAgentData(**item_dict))

        if processed_agent_data_batch:
            success = self.store_gateway.save_data(processed_agent_data_batch)
            if success:
                logging.info(f"✅ HubGateway forwarded {len(processed_agent_data_batch)} items to Store")
            else:
                logging.error("HubGateway failed to send processed data batch to Store")
                for item in processed_agent_data_batch:
                    redis_client.rpush("processed_agent_data", item.model_dump_json())

    def connect(self):
        self.client.connect(self.broker_host, self.broker_port)

    def start(self):
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()


