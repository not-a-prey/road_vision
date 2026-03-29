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
        # Parse ProcessedAgentData from Edge (includes road_state, damage_coefficient, agent_data)
        processed_agent_data = ProcessedAgentData.model_validate_json(payload)
        logging.info(f"Received: road_state={processed_agent_data.road_state}, damage={processed_agent_data.damage_coefficient}")

        redis_client.lpush("processed_agent_data", processed_agent_data.model_dump_json())

        if redis_client.llen("processed_agent_data") >= BATCH_SIZE:
            logging.info(f"Batch size {BATCH_SIZE} reached. Sending...")

            processed_agent_data_batch = []
            for _ in range(BATCH_SIZE):
                raw_item = redis_client.lpop("processed_agent_data")
                if raw_item:
                    processed_agent_data_batch.append(
                        ProcessedAgentData.model_validate_json(raw_item)
                    )

            try:
                url = f"{STORE_API_BASE_URL}/processed_agent_data/"
                batch_json = [json.loads(item.model_dump_json()) for item in processed_agent_data_batch]
                response = requests.post(url, json=batch_json)

                if response.status_code in (200, 201):
                    logging.info(f"Data saved successfully: {len(processed_agent_data_batch)} records")
                else:
                    logging.error(f"Store rejected data: {response.status_code} - {response.text}")
            except Exception as e:
                logging.error(f"Request failed: {e}")

    except Exception as e:
        logging.error(f"HUB ERROR: {e}")

client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
client.loop_start()

app = FastAPI()