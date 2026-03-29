CREATE TABLE processed_agent_data (
    id SERIAL PRIMARY KEY,
    road_state VARCHAR(255) NOT NULL,
    damage_coefficient FLOAT DEFAULT 0.0,
    machine_id VARCHAR(50),
    x FLOAT,
    y FLOAT,
    z FLOAT,
    latitude FLOAT,
    longitude FLOAT,
    timestamp TIMESTAMP
);

CREATE TABLE car_wear (
    car_id VARCHAR(50) PRIMARY KEY,
    total_wear FLOAT DEFAULT 0.0,
    last_update_timestamp TIMESTAMP,
    wear_status VARCHAR(50) DEFAULT 'NORMAL'
);
