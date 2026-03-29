from app.entities.agent_data import AgentData
from app.entities.processed_agent_data import ProcessedAgentData


Z_AXIS_BASELINE = 16525
Z_AXIS_POTHOLE_THRESHOLD = 16600
Z_AXIS_BUMP_THRESHOLD = 16450
DAMAGE_COEFFICIENT_SCALE = 100.0


def process_agent_data(
    agent_data: AgentData,
) -> ProcessedAgentData:
    """
    Process agent data and classify the state of the road surface.
    Parameters:
        agent_data (AgentData): Agent data that containing accelerometer, GPS, and timestamp.
    Returns:
        processed_data_batch (ProcessedAgentData): Processed data containing the classified state of the road surface and agent data.
    """
    z_acceleration = agent_data.accelerometer.z
    if z_acceleration > Z_AXIS_POTHOLE_THRESHOLD:
        road_state = "pothole"
    elif z_acceleration < Z_AXIS_BUMP_THRESHOLD:
        road_state = "bump"
    else:
        road_state = "good"

    damage_coefficient = abs(z_acceleration - Z_AXIS_BASELINE) / DAMAGE_COEFFICIENT_SCALE

    return ProcessedAgentData(
        road_state=road_state,
        damage_coefficient=round(damage_coefficient, 2),
        agent_data=agent_data,
    )
