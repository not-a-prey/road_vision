from pathlib import Path

from paho.mqtt import client as mqtt_client
import json
import time
from schema.aggregated_data_schema import AggregatedDataSchema
from file_datasource import FileDatasource
import config
import threading
connected_event = threading.Event()

def connect_mqtt(broker, port):
    """Create MQTT client"""
    print(f"CONNECT TO {broker}:{port}")

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            connected_event.set()
            print(f"Connected to MQTT Broker ({broker}:{port})!")
        else:
            print("Failed to connect {broker}:{port}, return code %d\n", rc)
            exit(rc)  # Stop execution

    client = mqtt_client.Client()
    client.on_connect = on_connect
    client.connect(broker, port)
    client.loop_start()
    return client


def publish(client, topic, datasource, delay):
    datasource.startReading()
    while True:
        time.sleep(delay)
        data = datasource.read()
        msg = AggregatedDataSchema().dumps(data)
        result = client.publish(topic, msg)
        status = result[0]
        if status == 0:
            print(f"--- AGENT: Дані відправлено в топік {topic} ---")
        else:
            print(f"Failed to send message to topic {topic}")


def run():
    try:
        client = connect_mqtt(
            config.MQTT_BROKER_HOST,
            config.MQTT_BROKER_PORT
        )

        connected_event.wait()
        csv_path = Path(__file__).resolve().parent
        datasource = FileDatasource(
           str( csv_path / "data" / "accelerometer.csv"),
            str( csv_path / "data" / "gps.csv")
        )

        publish(
            client,
            config.MQTT_TOPIC,
            datasource,
            config.DELAY
        )

    except Exception as e:
        print(f"FATAL ERROR: {e}")

        while True:
            time.sleep(5)


if __name__ == "__main__":
    run()
