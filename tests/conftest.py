import pytest
import os
from app import create_app
from config import TestingConfig

@pytest.fixture(scope="session")
def app():
    """Create test Flask application with SQLite in-memory test database."""
    os.environ["FLASK_ENV"] = "testing"
    application = create_app(TestingConfig)
    return application

@pytest.fixture(scope="session")
def db(app):
    """Initialize test database."""
    from app.extensions import db as _db
    with app.app_context():
        _db.create_all()
        yield _db
        _db.drop_all()

@pytest.fixture(scope="function")
def session(db, app):
    """Provide a clean transactional test session that rolls back after each test."""
    with app.app_context():
        connection = db.engine.connect()
        transaction = connection.begin()
        from sqlalchemy.orm import Session
        test_session = Session(bind=connection)
        old_session = db.session
        db.session = test_session
        yield test_session
        test_session.close()
        transaction.rollback()
        connection.close()
        db.session = old_session
