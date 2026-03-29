from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, DateTime
from config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
)

DATABASE_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
engine = create_engine(DATABASE_URL)
metadata = MetaData()

# Define the ProcessedAgentData table
processed_agent_data = Table(
    "processed_agent_data",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("road_state", String),
    Column("damage_coefficient", Float),
    Column("machine_id", String),
    Column("x", Float),
    Column("y", Float),
    Column("z", Float),
    Column("latitude", Float),
    Column("longitude", Float),
    Column("timestamp", DateTime),
)

# Define the CarWear table
car_wear = Table(
    "car_wear",
    metadata,
    Column("car_id", String, primary_key=True),
    Column("total_wear", Float, default=0.0),
    Column("last_update_timestamp", DateTime),
    Column("wear_status", String, default="NORMAL"),
)

# Drop and recreate tables
metadata.drop_all(engine)
metadata.create_all(engine)

print("Tables recreated successfully.")