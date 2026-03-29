from pydantic import BaseModel
from app.entities.agent_data import AgentData


class ProcessedAgentData(BaseModel):
    road_state: str
    damage_coefficient: float = 0.0
    agent_data: AgentData
