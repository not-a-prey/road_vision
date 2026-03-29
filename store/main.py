import asyncio
import json
import traceback
from fastapi.middleware.cors import CORSMiddleware
from typing import Set, Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Body
from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    text,
    func,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import select
from datetime import datetime
from pydantic import BaseModel, field_validator
from config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
)
# FastAPI app setup
app = FastAPI()

# Налаштування CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Дозволяє запити з будь-якого домену (для розробки - ок)
    allow_credentials=True,
    allow_methods=["*"],  # Дозволяє всі методи (GET, POST, і т.д.)
    allow_headers=["*"],  # Дозволяє всі заголовки
)
# SQLAlchemy setup
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

SessionLocal = sessionmaker(bind=engine)


# SQLAlchemy model
class ProcessedAgentDataInDB(BaseModel):
    id: int
    road_state: str
    damage_coefficient: float
    machine_id: str
    x: float
    y: float
    z: float
    latitude: float
    longitude: float
    timestamp: datetime


# FastAPI models
class AccelerometerData(BaseModel):
    x: float
    y: float
    z: float


class GpsData(BaseModel):
    latitude: float
    longitude: float


class AgentData(BaseModel):
    user_id: int
    accelerometer: AccelerometerData
    gps: GpsData
    timestamp: datetime

    @classmethod
    @field_validator("timestamp", mode="before")
    def check_timestamp(cls, value):
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            raise ValueError(
                "Invalid timestamp format. Expected ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)."
            )


class ProcessedAgentData(BaseModel):
    road_state: str
    damage_coefficient: float = 0.0
    agent_data: AgentData


class CarWearResponse(BaseModel):
    car_id: str
    total_wear: float
    wear_status: str
    last_update_timestamp: Optional[datetime]


class UpdateCarWearResponse(CarWearResponse):
    added_this_time: float


# WebSocket subscriptions
subscriptions: Dict[int, Set[WebSocket]] = {}


# FastAPI WebSocket endpoint
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await websocket.accept()
    print(f"STORE WS: Client connected for user_id={user_id}")
    if user_id not in subscriptions:
        subscriptions[user_id] = set()
    subscriptions[user_id].add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        print(f"STORE WS: Client disconnected for user_id={user_id}")
        subscriptions[user_id].remove(websocket)


# Function to send data to subscribed users
def complex_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)

async def send_data_to_subscribers(user_id: int, data):
    print(f"STORE WS: Preparing to broadcast to user_id={user_id}")
    
    try:
        # 1. Turn WHATEVER data is (List or Dict) into a clean JSON string
        clean_json = json.dumps(data, default=complex_serializer)
        
        if user_id in subscriptions:
            # Create a copy of the set to avoid "Set changed size during iteration" errors
            active_sockets = list(subscriptions[user_id])
            
            for websocket in active_sockets:
                try:
                    # 2. Use send_text since we manually stringified it
                    await websocket.send_text(clean_json)
                except Exception as e:
                    print(f"STORE WS: Socket error, removing subscriber: {e}")
                    subscriptions[user_id].remove(websocket)
        else:
            print(f"STORE WS: No active subscribers for user_id={user_id}")

    except Exception as e:
        print("STORE WS: CRITICAL SERIALIZATION ERROR")
        traceback.print_exc() # This will tell us the EXACT line that failed


# FastAPI CRUDL endpoints


@app.post("/processed_agent_data/", response_model=list[ProcessedAgentDataInDB])
async def create_processed_agent_data(data: List[ProcessedAgentData]):
    # Insert data to database and notify websocket subscribers
    session = SessionLocal()
    created: List[ProcessedAgentDataInDB] = []
    try:
        # insert each record and stream update
        for item in data:
            row = {
                "road_state": item.road_state,
                "damage_coefficient": item.damage_coefficient,
                "machine_id": str(item.agent_data.user_id),
                "x": item.agent_data.accelerometer.x,
                "y": item.agent_data.accelerometer.y,
                "z": item.agent_data.accelerometer.z,
                "latitude": item.agent_data.gps.latitude,
                "longitude": item.agent_data.gps.longitude,
                "timestamp": item.agent_data.timestamp,
            }
            result = session.execute(
                processed_agent_data.insert().values(**row).returning(*processed_agent_data.c)
            )
            inserted = result.fetchone()
            # commit after each insert so we get the id filled and avoid partial states
            session.commit()
            record = ProcessedAgentDataInDB(**inserted._mapping)
            created.append(record)
            # notify subscribers for this user
            try:
                print(f"STORE WS: Notifying subscribers for user_id={item.agent_data.user_id}")
                await send_data_to_subscribers(item.agent_data.user_id, record.dict())
            except Exception:
                # swallow errors from websocket so that db insert is not affected
                print("STORE WS: Error broadcasting to WebSocket")
                pass
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        session.close()

    return created


@app.get(
    "/processed_agent_data/{processed_agent_data_id}",
    response_model=ProcessedAgentDataInDB,
)
def read_processed_agent_data(processed_agent_data_id: int):
    # Get data by id
    session = SessionLocal()
    stmt = select(processed_agent_data).where(
        processed_agent_data.c.id == processed_agent_data_id
    )
    result = session.execute(stmt).first()
    session.close()

    if result is None:
        raise HTTPException(status_code=404, detail="ProcessedAgentData not found")
    return ProcessedAgentDataInDB(**result._mapping)


@app.get("/processed_agent_data/", response_model=list[ProcessedAgentDataInDB])
def list_processed_agent_data():
    # Get list of data
    session = SessionLocal()
    stmt = select(processed_agent_data)
    results = session.execute(stmt).all()
    session.close()
    return [ProcessedAgentDataInDB(**row._mapping) for row in results]


@app.put(
    "/processed_agent_data/{processed_agent_data_id}",
    response_model=ProcessedAgentDataInDB,
)
def update_processed_agent_data(processed_agent_data_id: int, data: ProcessedAgentData):
    # Update data
    session = SessionLocal()
    stmt = select(processed_agent_data).where(
        processed_agent_data.c.id == processed_agent_data_id
    )
    existing = session.execute(stmt).first()
    if existing is None:
        session.close()
        raise HTTPException(status_code=404, detail="ProcessedAgentData not found")

    update_values = {
        "road_state": data.road_state,
        "damage_coefficient": data.damage_coefficient,
        "machine_id": str(data.agent_data.user_id),
        "x": data.agent_data.accelerometer.x,
        "y": data.agent_data.accelerometer.y,
        "z": data.agent_data.accelerometer.z,
        "latitude": data.agent_data.gps.latitude,
        "longitude": data.agent_data.gps.longitude,
        "timestamp": data.agent_data.timestamp,
    }
    session.execute(
        processed_agent_data.update()
        .where(processed_agent_data.c.id == processed_agent_data_id)
        .values(**update_values)
    )
    session.commit()

    # fetch updated row
    updated = session.execute(stmt).first()
    session.close()
    return ProcessedAgentDataInDB(**updated._mapping)


@app.delete(
    "/processed_agent_data/{processed_agent_data_id}",
    response_model=ProcessedAgentDataInDB,
)
def delete_processed_agent_data(processed_agent_data_id: int):
    # Delete by id
    session = SessionLocal()
    stmt = select(processed_agent_data).where(
        processed_agent_data.c.id == processed_agent_data_id
    )
    existing = session.execute(stmt).first()
    if existing is None:
        session.close()
        raise HTTPException(status_code=404, detail="ProcessedAgentData not found")

    to_return = ProcessedAgentDataInDB(**existing._mapping)
    session.execute(
        processed_agent_data.delete().where(
            processed_agent_data.c.id == processed_agent_data_id
        )
    )
    session.commit()
    session.close()
    return to_return


# Car Wear endpoints

WEAR_STATUS_NORMAL = "NORMAL"
WEAR_STATUS_WARNING = "WARNING"
WEAR_STATUS_REPAIR_NEEDED = "REPAIR_NEEDED"
WEAR_STATUS_CRITICAL = "CRITICAL"

WEAR_THRESHOLD_WARNING = 50
WEAR_THRESHOLD_REPAIR = 120
WEAR_THRESHOLD_CRITICAL = 250


def calculate_wear_status(total_wear: float) -> str:
    if total_wear > WEAR_THRESHOLD_CRITICAL:
        return WEAR_STATUS_CRITICAL
    if total_wear > WEAR_THRESHOLD_REPAIR:
        return WEAR_STATUS_REPAIR_NEEDED
    if total_wear > WEAR_THRESHOLD_WARNING:
        return WEAR_STATUS_WARNING
    return WEAR_STATUS_NORMAL


@app.post("/update_car_wear/{car_id}", response_model=UpdateCarWearResponse)
def update_car_wear(car_id: str):
    session = SessionLocal()
    try:
        current = session.execute(
            select(car_wear).where(car_wear.c.car_id == car_id)
        ).first()

        last_ts = current.last_update_timestamp if current else None
        current_total = current.total_wear if current else 0.0

        damage_query = select(func.coalesce(func.sum(processed_agent_data.c.damage_coefficient), 0.0)).where(
            processed_agent_data.c.machine_id == car_id
        )
        if last_ts:
            damage_query = damage_query.where(processed_agent_data.c.timestamp > last_ts)

        delta = session.execute(damage_query).scalar() or 0.0
        new_total = current_total + delta
        status = calculate_wear_status(new_total)
        now = datetime.utcnow()

        if current:
            session.execute(
                car_wear.update()
                .where(car_wear.c.car_id == car_id)
                .values(total_wear=new_total, last_update_timestamp=now, wear_status=status)
            )
        else:
            session.execute(
                car_wear.insert().values(
                    car_id=car_id, total_wear=new_total, last_update_timestamp=now, wear_status=status
                )
            )
        session.commit()

        return UpdateCarWearResponse(
            car_id=car_id,
            total_wear=round(new_total, 2),
            wear_status=status,
            last_update_timestamp=now,
            added_this_time=round(delta, 2),
        )
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        session.close()


@app.post("/reset_car_wear/{car_id}", response_model=CarWearResponse)
def reset_car_wear(car_id: str):
    session = SessionLocal()
    try:
        now = datetime.utcnow()
        existing = session.execute(
            select(car_wear).where(car_wear.c.car_id == car_id)
        ).first()

        if existing:
            session.execute(
                car_wear.update()
                .where(car_wear.c.car_id == car_id)
                .values(total_wear=0.0, last_update_timestamp=now, wear_status=WEAR_STATUS_NORMAL)
            )
        else:
            session.execute(
                car_wear.insert().values(
                    car_id=car_id, total_wear=0.0, last_update_timestamp=now, wear_status=WEAR_STATUS_NORMAL
                )
            )
        session.commit()

        return CarWearResponse(
            car_id=car_id,
            total_wear=0.0,
            wear_status=WEAR_STATUS_NORMAL,
            last_update_timestamp=now,
        )
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        session.close()


@app.get("/car_wear/", response_model=list[CarWearResponse])
def list_car_wear():
    session = SessionLocal()
    results = session.execute(select(car_wear)).all()
    session.close()
    return [CarWearResponse(**row._mapping) for row in results]


@app.get("/car_wear/{car_id}", response_model=CarWearResponse)
def get_car_wear(car_id: str):
    session = SessionLocal()
    result = session.execute(
        select(car_wear).where(car_wear.c.car_id == car_id)
    ).first()
    session.close()
    if result is None:
        raise HTTPException(status_code=404, detail="Car wear record not found")
    return CarWearResponse(**result._mapping)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
