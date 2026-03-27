import logging
import paho.mqtt.client as mqtt
from app.interfaces.agent_gateway import AgentGateway
from app.entities.agent_data import AgentData, GpsData
from app.usecases.data_processing import process_agent_data
from app.interfaces.hub_gateway import HubGateway


class AgentMQTTAdapter(AgentGateway):
    def __init__(
        self,
        broker_host,
        broker_port,
        topic,
        hub_gateway: HubGateway,
        batch_size=10,
    ):
        self.batch_size = batch_size
        # MQTT
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic = topic
        self.client = mqtt.Client()
        # Hub
        self.hub_gateway = hub_gateway
        self._buffer = []

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info("Connected to MQTT broker")
            self.client.subscribe(self.topic)
        else:
            logging.info(f"Failed to connect to MQTT broker with code: {rc}")

    def on_message(self, client, userdata, msg):
        """Processing agent data and sending it through the hub gateway"""
        try:
            payload: str = msg.payload.decode("utf-8")
            agent_data = AgentData.model_validate_json(payload, strict=True)
            processed_data = process_agent_data(agent_data)
            logging.info(f"Processed data: {processed_data}")
            self._buffer.append(processed_data)
            if len(self._buffer) >= self.batch_size:
                success = self.hub_gateway.save_data(self._buffer)
                if success:
                    logging.info(f"Sent {len(self._buffer)} messages to HubGateway")
                    self._buffer.clear()
                else:
                    logging.error("Hub is not available, keeping data in buffer")

        except Exception as e:
            logging.info(f"Error processing MQTT message: {e}")

    def connect(self):
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.broker_host, self.broker_port, 60)

    def start(self):
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()


# Usage example:
if __name__ == "__main__":
    from app.adapters.hub_mqtt_adapter import HubMqttAdapter

    broker_host = "localhost"
    broker_port = 1883
    topic = "agent_data_topic"

    hub_gateway = HubMqttAdapter(broker=broker_host, port=broker_port, topic="processed_agent_data_topic")
    adapter = AgentMQTTAdapter(broker_host, broker_port, topic, hub_gateway, batch_size=10)

    adapter.connect()
    adapter.start()
    try:
        while True:
            pass
    except KeyboardInterrupt:
        adapter.stop()
        logging.info("Adapter stopped.")
