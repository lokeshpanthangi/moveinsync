from sqlalchemy import Column, Integer, String, Text, Time
from pydantic import Optional
from database import Base

class vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    type = Column(String, index=True)
    seats = Column(Integer, nullable=False)
    status = Column(String, index=True)
    type = Column(String, index=True)
    assigned_to_path = Column(String, nullable=True)

class routes(Base):
    __tablename__ = "routes"
    id = Column(Integer, primary_key=True, index=True)
    path_id = Column(String, nullable=False)
    name = Column(String, index=True)
    direction = Column(String, index=True)
    start_time = Column(Time, nullable=False)
    start_point = Column(String, nullable=False)
    end_point = Column(String, nullable=False)
    capacity = Column(Integer, nullable=False)
    allowed_waitlist = Column(Integer, nullable=False)

class stops(Base):
    __tablename__ = "stops"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    location = Column(String, nullable=False)
    description = Column(Text, nullable=True)

class paths(Base):
    