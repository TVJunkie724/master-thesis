"""
Unit tests for SQLAlchemy models.

Tests model behavior including:
- Default values
- Relationships
- State enum
"""

import pytest
from datetime import datetime


class TestTwinModel:
    """Tests for DigitalTwin model."""

    def test_twin_state_enum_values(self):
        """TwinState enum has expected values."""
        from src.models.twin import TwinState
        
        assert TwinState.DRAFT.value == "draft"
        assert TwinState.CONFIGURED.value == "configured"
        assert TwinState.DEPLOYED.value == "deployed"
        assert TwinState.DESTROYED.value == "destroyed"
        assert TwinState.ERROR.value == "error"
        assert TwinState.INACTIVE.value == "inactive"

    def test_twin_default_state(self, db_session):
        """New twin has draft state by default."""
        from src.models.twin import DigitalTwin, TwinState
        from src.models.user import User
        
        # Create user first (needed for relationship)
        user = User(id="user-123", email="test@example.com")
        db_session.add(user)
        db_session.commit()
        
        # Create twin
        twin = DigitalTwin(name="Test Twin", user_id=user.id)
        db_session.add(twin)
        db_session.commit()
        
        assert twin.state == TwinState.DRAFT

    def test_twin_auto_generates_id(self, db_session):
        """Twin ID is auto-generated if not provided."""
        from src.models.twin import DigitalTwin
        from src.models.user import User
        
        user = User(id="user-456", email="test2@example.com")
        db_session.add(user)
        db_session.commit()
        
        twin = DigitalTwin(name="Test", user_id=user.id)
        db_session.add(twin)
        db_session.commit()
        
        assert twin.id is not None
        assert len(twin.id) == 36  # UUID format

    def test_twin_timestamps(self, db_session):
        """Twin has created_at and updated_at timestamps."""
        from src.models.twin import DigitalTwin
        from src.models.user import User
        
        user = User(id="user-789", email="test3@example.com")
        db_session.add(user)
        db_session.commit()
        
        twin = DigitalTwin(name="Test", user_id=user.id)
        db_session.add(twin)
        db_session.commit()
        
        assert twin.created_at is not None
        assert twin.updated_at is not None
        assert isinstance(twin.created_at, datetime)


class TestTwinConfigModel:
    """Tests for TwinConfiguration model."""

    def test_config_creates_with_defaults(self, db_session):
        """TwinConfiguration has sensible defaults."""
        from src.models.twin import DigitalTwin
        from src.models.twin_config import TwinConfiguration
        from src.models.user import User
        
        user = User(id="user-config-1", email="config@example.com")
        db_session.add(user)
        db_session.commit()
        
        twin = DigitalTwin(name="Test", user_id=user.id)
        db_session.add(twin)
        db_session.commit()
        
        config = TwinConfiguration(twin_id=twin.id)
        db_session.add(config)
        db_session.commit()
        
        assert config.debug_mode == False


class TestOptimizerConfigModel:
    """Tests for OptimizerConfiguration model."""

    def test_optimizer_config_starts_empty(self, db_session):
        """OptimizerConfiguration starts with null fields."""
        from src.models.twin import DigitalTwin
        from src.models.optimizer_config import OptimizerConfiguration
        from src.models.user import User
        
        user = User(id="user-opt-1", email="opt@example.com")
        db_session.add(user)
        db_session.commit()
        
        twin = DigitalTwin(name="Test", user_id=user.id)
        db_session.add(twin)
        db_session.commit()
        
        opt_config = OptimizerConfiguration(twin_id=twin.id)
        db_session.add(opt_config)
        db_session.commit()
        
        assert opt_config.params is None
        assert opt_config.result_json is None


class TestUserModel:
    """Tests for User model."""

    def test_user_creation(self, db_session):
        """User can be created with email."""
        from src.models.user import User
        
        user = User(id="user-creation-1", email="new@example.com")
        db_session.add(user)
        db_session.commit()
        
        assert user.email == "new@example.com"
        assert user.id == "user-creation-1"
