import json
import logging
from typing import List

import pydantic_core
import requests

from app.entities.processed_agent_data import ProcessedAgentData
from app.interfaces.store_gateway import StoreGateway


class StoreApiAdapter(StoreGateway):
    def __init__(self, api_base_url):
        self.api_base_url = api_base_url

    def save_data(self, processed_agent_data_batch: List[ProcessedAgentData]) -> bool:
        """
        Save the processed road data to the Store API.
        Parameters:
            processed_agent_data_batch (List[ProcessedAgentData]): Processed road data to be saved.
        Returns:
            bool: True if the data is successfully saved, False otherwise.
        """
        try:
            response = requests.post(
                f"{self.api_base_url}/processed_agent_data/",
                data=json.dumps(
                    [item.model_dump(mode="json") for item in processed_agent_data_batch]
                ),
                headers={"Content-Type": "application/json"},
            )
            if response.status_code == 200:
                logging.info(f"Data saved successfully: {len(processed_agent_data_batch)} records")
                return True
            else:
                logging.error(f"Failed to save data. Status: {response.status_code}, Response: {response.text}")
                return False
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Connection error to Store API: {e}")
            return False
        except Exception as e:
            logging.error(f"Error saving data to Store API: {e}")
            return False
