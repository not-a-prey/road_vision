from abc import ABC, abstractmethod
from app.entities.processed_agent_data import ProcessedAgentData


class HubGateway(ABC):
    """
    Abstract class representing the Hub Gateway interface.
    All hub gateway adapters must implement these methods.
    """

    @abstractmethod
    def save_data(self, processed_data_batch: list[ProcessedAgentData]) -> bool:
        """
        Method to save the processed agent data batch via the hub.
        Parameters:
            processed_data_batch (List[ProcessedAgentData]): The processed agent data to be saved.
        Returns:
            bool: True if the data is successfully saved, False otherwise.
        """
        pass
