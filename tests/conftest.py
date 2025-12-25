"""Test configuration and fixtures."""
import pytest
import asyncio
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from core.database import Base, get_db_session
from api.main import app

# Test database URL
TEST_DATABASE_URL = "sqlite:///./test.db"

# Create test engine
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Override the dependency before any tests run
app.dependency_overrides[get_db_session] = override_get_db


@pytest.fixture(scope="function", autouse=True)
def setup_test_database():
    """Create tables before each test and drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client():
    """Create test client with database dependency override."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
