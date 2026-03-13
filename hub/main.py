import logging
import json
import requests
from typing import List
from datetime import datetime
from fastapi import FastAPI
from redis import Redis
import paho.mqtt.client as mqtt

from app.entities.processed_agent_data import ProcessedAgentData
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

# MQTT Client
client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Connected to MQTT broker")
        client.subscribe(MQTT_TOPIC)
    else:
        logging.info(f"Failed to connect to MQTT broker with code: {rc}")

def on_message(client, userdata, msg):
    try:
        payload: str = msg.payload.decode("utf-8", errors="ignore")
        agent_data_raw = json.loads(payload)

        # Детекція вибоїн
        z_axis = agent_data_raw.get("accelerometer", {}).get("z", 16000)
        road_state = "normal"
        if z_axis > 17500 or z_axis < 15000:
            road_state = "bump"
            logging.info(f"BUMP DETECTED! Z-axis: {z_axis}")

        # Очистка часу
        timestamp = agent_data_raw.get("timestamp")
        if not isinstance(timestamp, str):
            timestamp = datetime.now().isoformat()

        processed_agent_data = ProcessedAgentData(
            road_state=road_state,
            agent_data=agent_data_raw,
            user_id=int(agent_data_raw.get("user_id", 1)),
            timestamp=timestamp
        )

        redis_client.lpush("processed_agent_data", processed_agent_data.model_dump_json())

        if redis_client.llen("processed_agent_data") >= BATCH_SIZE:
            logging.info(f"Batch size {BATCH_SIZE} reached. Sending...")

            # Створюємо список, який раніше "загубився"
            processed_agent_data_batch = []

            for _ in range(BATCH_SIZE):
                raw_item = redis_client.lpop("processed_agent_data")
                if raw_item:
                    item_str = raw_item.decode("utf-8", errors="ignore")
                    item_dict = json.loads(item_str)
                    processed_agent_data_batch.append(ProcessedAgentData(**item_dict))

            # ПРЯМА ВІДПРАВКА (Стандартна)
            try:
                safe_batch_list = [json.loads(item.model_dump_json()) for item in processed_agent_data_batch]
                url = f"{STORE_API_BASE_URL}/processed_agent_data/"

                # Бібліотека requests сама все ідеально запакує
                response = requests.post(url, json=safe_batch_list)

                if response.status_code in (200, 201):
                    logging.info("✅ SUCCESS! Дані залетіли в базу!")
                else:
                    logging.error(f"Store rejected data: {response.status_code} - {response.text}")
            except Exception as e:
                logging.error(f"Request failed: {e}")

    except Exception as e:
        logging.error(f"HUB ERROR: {e}")

client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)

if __name__ == "__main__":
    logging.info("Starting Hub MQTT loop...")
    client.loop_forever()