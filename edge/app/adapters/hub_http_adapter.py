import logging

import requests as requests

from app.entities.processed_agent_data import ProcessedAgentData
from app.interfaces.hub_gateway import HubGateway


class HubHttpAdapter(HubGateway):
    def __init__(self, api_base_url):
        self.api_base_url = api_base_url

    def save_data(self, processed_data_batch: list[ProcessedAgentData]):
        """
        Save the processed road data batch to the Hub.
        Parameters:
            processed_data_batch (List[ProcessedAgentData]): Processed road data to be saved.
        Returns:
            bool: True if the data is successfully saved, False otherwise.
        """
        url = f"{self.api_base_url}/processed_agent_data/"

        response = requests.post(
            url,
            json=[item.model_dump(mode="json") for item in processed_data_batch],
            headers={"Content-Type": "application/json"},
        )

        if response.status_code not in (200, 201):
            logging.error(
                f"Invalid Hub response\nData: {[item.model_dump_json() for item in processed_data_batch]}\nResponse: {response.status_code} {response.text}"
            )
            return False
        return True
