"""Tests for Recipe API endpoints (CRUD, activate/deactivate, clone, templates).

Tests cover:
- GET /recipes (list user recipes)
- POST /recipes (create recipe)
- GET /recipes/{id} (get single recipe)
- PUT /recipes/{id} (update recipe)
- DELETE /recipes/{id} (delete recipe)
- POST /recipes/{id}/activate (activate recipe)
- POST /recipes/{id}/deactivate (deactivate recipe)
- POST /recipes/{id}/clone (clone a recipe)
- GET /recipes/templates (list template recipes)
"""

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet as _Fernet

# Set test environment before importing app
_test_fernet_key = _Fernet.generate_key().decode()
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-e2e")
os.environ.setdefault("ENCRYPTION_KEY", _test_fernet_key)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://able:able_secret@localhost:15432/able")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://able:able_secret@localhost:15432/able")
os.environ.setdefault("REDIS_URL", "redis://localhost:16379/1")

from app.models.user import User
from app.models.trading_recipe import TradingRecipe
from app.schemas.recipe import RecipeCreate, RecipeUpdate


# ─── Mock DB Helpers ──────────────────────────────────────────


class MockScalarResult:
    """Mock for scalars().all() and scalar_one_or_none()."""

    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


class MockResult:
    """Mock for db.execute() result."""

    def __init__(self, items=None):
        self._items = items or []

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalars(self):
        return MockScalarResult(self._items)


def make_mock_db(execute_side_effects=None):
    """Create a mock async DB session."""
    db = AsyncMock()
    if execute_side_effects:
        db.execute = AsyncMock(side_effect=execute_side_effects)
    else:
        db.execute = AsyncMock(return_value=MockResult())
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    return db


# ─── Factory Helpers ──────────────────────────────────────────


def _make_user(user_id=None, email="test@example.com"):
    """Create a mock User instance."""
    u = MagicMock(spec=User)
    u.id = uuid.UUID(user_id) if user_id else uuid.uuid4()
    u.email = email
    u.display_name = "Tester"
    u.is_active = True
    return u


def _make_recipe(
    user_id,
    name="RSI 골든크로스",
    recipe_id=None,
    is_active=False,
    is_template=False,
    description="테스트 레시피",
):
    """Create a mock TradingRecipe instance."""
    r = MagicMock(spec=TradingRecipe)
    r.id = uuid.UUID(recipe_id) if recipe_id else uuid.uuid4()
    r.user_id = user_id
    r.name = name
    r.description = description
    r.signal_config = {
        "combinator": "AND",
        "signals": [
            {"type": "recommended", "strategy_type": "sma_crossover", "weight": 1.0}
        ],
    }
    r.custom_filters = {"volume_min": 1000000}
    r.stock_codes = ["005930", "000660"]
    r.risk_config = {"stop_loss": 3, "take_profit": 5, "position_size": 0.1}
    r.is_active = is_active
    r.is_template = is_template
    r.created_at = datetime.now(timezone.utc)
    r.updated_at = datetime.now(timezone.utc)
    return r


# ─── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def test_user():
    return _make_user()


@pytest.fixture
def mock_db():
    return make_mock_db()


# ─── Recipe List Tests ────────────────────────────────────────


class TestListRecipes:
    """Test GET /recipes (list user's recipes)."""

    @pytest.mark.asyncio
    async def test_list_recipes_empty(self, test_user, mock_db):
        """Listing recipes when user has none returns empty list."""
        from app.api.v1.recipes import list_recipes

        mock_db.execute = AsyncMock(return_value=MockResult([]))

        result = await list_recipes(db=mock_db, user=test_user)

        assert result == []
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_recipes_returns_user_recipes(self, test_user, mock_db):
        """Listing recipes returns all recipes belonging to the user."""
        from app.api.v1.recipes import list_recipes

        r1 = _make_recipe(test_user.id, name="Recipe A")
        r2 = _make_recipe(test_user.id, name="Recipe B")
        mock_db.execute = AsyncMock(return_value=MockResult([r1, r2]))

        result = await list_recipes(db=mock_db, user=test_user)

        assert len(result) == 2
        assert result[0].name == "Recipe A"
        assert result[1].name == "Recipe B"


# ─── Recipe Create Tests ─────────────────────────────────────


class TestCreateRecipe:
    """Test POST /recipes (create recipe)."""

    @pytest.mark.asyncio
    async def test_create_recipe(self, test_user, mock_db):
        """Creating a recipe adds it to the DB and returns the response."""
        from app.api.v1.recipes import create_recipe

        req = RecipeCreate(
            name="새 레시피",
            description="볼린저 밴드 전략",
            signal_config={
                "combinator": "AND",
                "signals": [
                    {"type": "recommended", "strategy_type": "bollinger_bands", "weight": 1.0}
                ],
            },
            custom_filters={"volume_min": 500000},
            stock_codes=["005930"],
            risk_config={"stop_loss": 2},
        )

        # The refresh callback simulates what the DB would do:
        # populate the id, timestamps, and defaults on the object.
        async def mock_refresh(obj):
            obj.id = uuid.uuid4()
            obj.name = req.name
            obj.description = req.description
            obj.signal_config = req.signal_config
            obj.custom_filters = req.custom_filters
            obj.stock_codes = req.stock_codes
            obj.risk_config = req.risk_config
            obj.is_active = False
            obj.is_template = False
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = datetime.now(timezone.utc)

        mock_db.refresh = AsyncMock(side_effect=mock_refresh)

        result = await create_recipe(req=req, db=mock_db, user=test_user)

        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

        assert result.name == "새 레시피"
        assert result.description == "볼린저 밴드 전략"
        assert result.signal_config == req.signal_config
        assert result.stock_codes == ["005930"]
        assert result.is_active is False
        assert result.is_template is False


# ─── Recipe Get Tests ────────────────────────────────────────


class TestGetRecipe:
    """Test GET /recipes/{id} (get single recipe)."""

    @pytest.mark.asyncio
    async def test_get_recipe_not_found(self, test_user, mock_db):
        """Getting a non-existent recipe raises 404."""
        from app.api.v1.recipes import get_recipe
        from fastapi import HTTPException

        mock_db.execute = AsyncMock(return_value=MockResult([]))

        with pytest.raises(HTTPException) as exc_info:
            await get_recipe(
                recipe_id=str(uuid.uuid4()),
                db=mock_db,
                user=test_user,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Recipe not found"

    @pytest.mark.asyncio
    async def test_get_recipe_success(self, test_user, mock_db):
        """Getting an existing recipe returns the correct response."""
        from app.api.v1.recipes import get_recipe

        recipe = _make_recipe(test_user.id, name="My Recipe")
        mock_db.execute = AsyncMock(return_value=MockResult([recipe]))

        result = await get_recipe(
            recipe_id=str(recipe.id),
            db=mock_db,
            user=test_user,
        )

        assert result.id == str(recipe.id)
        assert result.name == "My Recipe"
        assert result.signal_config == recipe.signal_config
        assert result.stock_codes == recipe.stock_codes
        assert result.risk_config == recipe.risk_config


# ─── Recipe Update Tests ─────────────────────────────────────


class TestUpdateRecipe:
    """Test PUT /recipes/{id} (update recipe)."""

    @pytest.mark.asyncio
    async def test_update_recipe(self, test_user, mock_db):
        """Updating a recipe modifies the specified fields."""
        from app.api.v1.recipes import update_recipe

        recipe = _make_recipe(test_user.id, name="Old Name")
        mock_db.execute = AsyncMock(return_value=MockResult([recipe]))

        req = RecipeUpdate(name="New Name", stock_codes=["035720"])

        # After setattr + flush + refresh, the recipe object should have new values.
        async def mock_refresh(obj):
            # Simulate DB returning updated values
            pass

        mock_db.refresh = AsyncMock(side_effect=mock_refresh)

        result = await update_recipe(
            recipe_id=str(recipe.id),
            req=req,
            db=mock_db,
            user=test_user,
        )

        mock_db.flush.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()
        # setattr should have been called on the recipe mock
        assert recipe.name == "New Name"
        assert recipe.stock_codes == ["035720"]

    @pytest.mark.asyncio
    async def test_update_recipe_not_found(self, test_user, mock_db):
        """Updating a non-existent recipe raises 404."""
        from app.api.v1.recipes import update_recipe
        from fastapi import HTTPException

        mock_db.execute = AsyncMock(return_value=MockResult([]))
        req = RecipeUpdate(name="Whatever")

        with pytest.raises(HTTPException) as exc_info:
            await update_recipe(
                recipe_id=str(uuid.uuid4()),
                req=req,
                db=mock_db,
                user=test_user,
            )

        assert exc_info.value.status_code == 404


# ─── Recipe Delete Tests ─────────────────────────────────────


class TestDeleteRecipe:
    """Test DELETE /recipes/{id} (delete recipe)."""

    @pytest.mark.asyncio
    async def test_delete_recipe(self, test_user, mock_db):
        """Deleting an existing recipe calls db.delete."""
        from app.api.v1.recipes import delete_recipe

        recipe = _make_recipe(test_user.id)
        mock_db.execute = AsyncMock(return_value=MockResult([recipe]))

        await delete_recipe(
            recipe_id=str(recipe.id),
            db=mock_db,
            user=test_user,
        )

        mock_db.delete.assert_awaited_once_with(recipe)

    @pytest.mark.asyncio
    async def test_delete_recipe_not_found(self, test_user, mock_db):
        """Deleting a non-existent recipe raises 404."""
        from app.api.v1.recipes import delete_recipe
        from fastapi import HTTPException

        mock_db.execute = AsyncMock(return_value=MockResult([]))

        with pytest.raises(HTTPException) as exc_info:
            await delete_recipe(
                recipe_id=str(uuid.uuid4()),
                db=mock_db,
                user=test_user,
            )

        assert exc_info.value.status_code == 404


# ─── Recipe Activate / Deactivate Tests ──────────────────────


class TestActivateRecipe:
    """Test POST /recipes/{id}/activate."""

    @pytest.mark.asyncio
    async def test_activate_recipe(self, test_user, mock_db):
        """Activating a recipe sets is_active=True."""
        from app.api.v1.recipes import activate_recipe

        recipe = _make_recipe(test_user.id, is_active=False)
        mock_db.execute = AsyncMock(return_value=MockResult([recipe]))

        result = await activate_recipe(
            recipe_id=str(recipe.id),
            db=mock_db,
            user=test_user,
        )

        assert recipe.is_active is True
        mock_db.flush.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()
        assert result.is_active is True

    @pytest.mark.asyncio
    async def test_activate_recipe_not_found(self, test_user, mock_db):
        """Activating a non-existent recipe raises 404."""
        from app.api.v1.recipes import activate_recipe
        from fastapi import HTTPException

        mock_db.execute = AsyncMock(return_value=MockResult([]))

        with pytest.raises(HTTPException) as exc_info:
            await activate_recipe(
                recipe_id=str(uuid.uuid4()),
                db=mock_db,
                user=test_user,
            )

        assert exc_info.value.status_code == 404


class TestDeactivateRecipe:
    """Test POST /recipes/{id}/deactivate."""

    @pytest.mark.asyncio
    async def test_deactivate_recipe(self, test_user, mock_db):
        """Deactivating a recipe sets is_active=False."""
        from app.api.v1.recipes import deactivate_recipe

        recipe = _make_recipe(test_user.id, is_active=True)
        mock_db.execute = AsyncMock(return_value=MockResult([recipe]))

        result = await deactivate_recipe(
            recipe_id=str(recipe.id),
            db=mock_db,
            user=test_user,
        )

        assert recipe.is_active is False
        mock_db.flush.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()
        assert result.is_active is False


# ─── Recipe Clone Tests ──────────────────────────────────────


class TestCloneRecipe:
    """Test POST /recipes/{id}/clone."""

    @pytest.mark.asyncio
    async def test_clone_recipe(self, test_user, mock_db):
        """Cloning a recipe creates a new recipe with '(복제)' suffix."""
        from app.api.v1.recipes import clone_recipe

        source = _make_recipe(
            test_user.id,
            name="골든크로스 전략",
            is_template=True,
        )
        mock_db.execute = AsyncMock(return_value=MockResult([source]))

        async def mock_refresh(obj):
            obj.id = uuid.uuid4()
            obj.name = f"{source.name} (복제)"
            obj.description = source.description
            obj.signal_config = source.signal_config
            obj.custom_filters = source.custom_filters
            obj.stock_codes = source.stock_codes
            obj.risk_config = source.risk_config
            obj.is_active = False
            obj.is_template = False
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = datetime.now(timezone.utc)

        mock_db.refresh = AsyncMock(side_effect=mock_refresh)

        result = await clone_recipe(
            recipe_id=str(source.id),
            db=mock_db,
            user=test_user,
        )

        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

        assert result.name == "골든크로스 전략 (복제)"
        assert result.signal_config == source.signal_config
        assert result.stock_codes == source.stock_codes
        assert result.risk_config == source.risk_config

    @pytest.mark.asyncio
    async def test_clone_recipe_not_found(self, test_user, mock_db):
        """Cloning a non-existent recipe raises 404."""
        from app.api.v1.recipes import clone_recipe
        from fastapi import HTTPException

        mock_db.execute = AsyncMock(return_value=MockResult([]))

        with pytest.raises(HTTPException) as exc_info:
            await clone_recipe(
                recipe_id=str(uuid.uuid4()),
                db=mock_db,
                user=test_user,
            )

        assert exc_info.value.status_code == 404


# ─── Template List Tests ─────────────────────────────────────


class TestListTemplates:
    """Test GET /recipes/templates."""

    @pytest.mark.asyncio
    async def test_list_templates(self, test_user, mock_db):
        """Listing templates returns only template recipes."""
        from app.api.v1.recipes import list_templates

        t1 = _make_recipe(test_user.id, name="Template A", is_template=True)
        t2 = _make_recipe(test_user.id, name="Template B", is_template=True)
        mock_db.execute = AsyncMock(return_value=MockResult([t1, t2]))

        result = await list_templates(db=mock_db, _user=test_user)

        assert len(result) == 2
        assert result[0].name == "Template A"
        assert result[1].name == "Template B"
        assert result[0].is_template is True
        assert result[1].is_template is True

    @pytest.mark.asyncio
    async def test_list_templates_empty(self, test_user, mock_db):
        """Listing templates when none exist returns empty list."""
        from app.api.v1.recipes import list_templates

        mock_db.execute = AsyncMock(return_value=MockResult([]))

        result = await list_templates(db=mock_db, _user=test_user)

        assert result == []
