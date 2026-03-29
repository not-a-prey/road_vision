# Road Vision Project

A multi-service IoT application for road vision data processing and visualization.

## Project Overview

This project consists of several microservices that work together to collect, process, and visualize road vision data from agents (sensors) through an edge processing layer to a central hub and storage system, with a frontend for visualization.

### Services

- **Agent**: Data collection service that simulates or reads sensor data (accelerometer, GPS).
- **Edge**: Edge processing service that receives data from agents via MQTT and processes it.
- **Hub**: Central hub that aggregates data from edge services and stores it.
- **Store**: Data storage service with database for persistent storage.
- **Frontend**: Web interface for visualizing the collected data.
- **MapView**: Mapping service for GPS data visualization.

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- Git

## Quick Start

### Using Docker Compose (Recommended)

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd road_vision
   ```

2. Launch all services:
   ```bash
   # From the ./hub/docker directory
   docker-compose up --build
   ```

3. Access the services:
   - Frontend: http://localhost:3000
   

### Local Development

1. Install dependencies for each service:
   ```bash
   # For each service directory
   pip install -r requirements.txt
   ```

2. Configure environment variables (see Configuration section)

3. Run services individually:
   ```bash
   # Agent
   cd agent && python src/main.py

   # Edge
   cd edge && python main.py

   # Hub
   cd hub && python main.py

   # Store
   cd store && python main.py

   # Frontend
   cd frontend && python main.py

   # MapView
   cd MapView && python main.py
   ```

## Configuration

### MQTT Configuration

Each service uses MQTT for communication. Configure `mosquitto.conf` in the respective docker/mosquitto/config/ directories.

Default configuration allows anonymous connections on port 1883.

### Database Setup

For the Store service, initialize the database:

```bash
cd store
python recreate_tables.py
```

Or use the Docker container which should handle this automatically.

## Service Details

### Agent
- Collects accelerometer and GPS data
- Publishes data to MQTT topics
- Supports CSV data sources and simulated data

### Edge
- Subscribes to agent data via MQTT
- Processes and aggregates data
- Forwards processed data to Hub

### Hub
- Receives processed data from Edge services
- Stores data temporarily
- Provides API for data access

### Store
- Persistent storage using PostgreSQL
- REST API for data retrieval
- Schema defined in `docker/db/structure.sql`

### Frontend
- Web dashboard built with HTML/CSS/JavaScript
- Displays real-time data visualizations
- Connects to Hub and MapView APIs

### MapView
- Specialized mapping service
- Visualizes GPS tracks
- Provides map layers and overlays

## Development

### Project Structure
```
road_vision/
├── agent/          # Data collection agent
├── edge/           # Edge processing service
├── hub/            # Central hub service
├── store/          # Data storage service
├── frontend/       # Web frontend
├── MapView/        # Mapping visualization
├── cache/          # Caching layer
└── tests/          # Test suites
```

### Adding New Services

1. Create a new directory with the service name
2. Add `Dockerfile` and `requirements.txt`
3. Create `docker-compose.yaml` in a `docker/` subdirectory
4. Update this README with service details

### Testing

Run tests for individual services:
```bash
cd <service-directory>
python -m pytest tests/
```

## Troubleshooting

### Common Issues

1. **Port conflicts**: Ensure ports 1883 (MQTT), 8080 (frontend), 5000 (hub), 5001 (store) are available.

2. **MQTT connection issues**: Check that Mosquitto is running and accessible.

3. **Database connection**: Verify PostgreSQL container is running and credentials are correct.

4. **Service dependencies**: Start services in order: Store → Hub → Edge → Agent → Frontend.

### Logs

Check logs for each service:
```bash
docker-compose logs <service-name>
```

Or for local runs, check console output.

### Resetting Data

To reset all data:
```bash
# Stop all services
docker-compose down

# Remove volumes
docker volume prune

# Restart
docker-compose up --build
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and test
4. Submit a pull request

## License

[Add license information here]