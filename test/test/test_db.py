import logging
import os
import pytest
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.db import get_db,get_redis_db, Base
from app.main import bat_app as fast_api_app
from app.bat.app_seed_parsers.parse_all_app_data import process_app_excel_data
from app.bpm_seed_parsers.parse_all_sheets import process_excel
from dotenv import find_dotenv, load_dotenv
from typing import Callable
from test.config import APP_SEED_DATA, BPM_SEED_DATA, TEST_DATABASE_URL


# Logging setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
env_file = find_dotenv(f".env{os.getenv('ENV', '')}")
logger.info("Fetching env_file %s", env_file)
load_dotenv(env_file)


# Database engine and session setup
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Database Fixture
@pytest.fixture(scope="module")
def db_session():
    """
    Setup the test database with seed data and teardown after tests.
    """
    # Create tables
    Base.metadata.create_all(bind=engine)
    db = TestSessionLocal()

    # Feed seed data into all tables
    try:
        
        logger.info(f"Processing seed data from {APP_SEED_DATA}")
        process_app_excel_data(APP_SEED_DATA, db)
        logger.info(f"Processing seed data from {BPM_SEED_DATA}")
        process_excel(BPM_SEED_DATA, db)
        db.commit()
        logger.info("Seed data loaded successfully.")
    except Exception as e:
        logger.error(f"Error loading seed data: {e}")
        db.rollback()
    try:
        yield db
        db.commit() # Provide the database session to tests
    finally:
        logger.info("Dropping tables and closing session")
        #Base.metadata.drop_all(bind=engine)
        db.close()

# Mock Redis client for testing
class MockRedis:
    def __init__(self):
        self.store = {}

    async def set(self, key, value, ex= None):
        self.store[key] = value
        if ex:
            self.store[key + "_expiry"] = ex

    async def setex(self, key, expiry, value):
        self.store[key] = value

    async def get(self, key):
        return self.store.get(key)

    async def delete(self, key):
        if key in self.store:
            del self.store[key]

    async def exists(self, key):
        return key in self.store

@pytest.fixture(scope="module")
def mock_redis():
    """Fixture to provide a mock Redis instance."""
    return MockRedis()

@pytest.fixture(scope="module")
def client(db_session, mock_redis):
    """Fixture for setting up TestClient with overridden dependencies."""
    def override_get_db():
        yield db_session

    def override_get_redis_db():
        yield mock_redis

    fast_api_app.dependency_overrides[get_db] = override_get_db
    fast_api_app.dependency_overrides[get_redis_db] = override_get_redis_db

    client = TestClient(fast_api_app)
    yield client

    fast_api_app.dependency_overrides.clear()


test_step_registry = {}

def test_step(step_id: str, name: str, operation: str):
    """
    Decorator for registering test steps in the test step registry.

    Args:
        step_id (str): Identifier for the test step.
        name (str): A human-readable name for the test step.
        operation (str): The type of operation (e.g., "fetch", "process", "upload").
    """
    def decorator(func: Callable):
        key = f"{step_id}-{operation}"
        if key in test_step_registry:
            raise ValueError(f"Test step {key} is already registered")
        test_step_registry[key] = {"name": name, "function": func}  # Store function in the dictionary
        logger.debug("Registered test step: %s", key)
        return func
    return decorator
