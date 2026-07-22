import asyncio
import uuid

import httpx
import pytest

from app.main import app
from app.domain.models import RoleEnum, User
from app.interfaces.deps import get_current_user, get_db
from app.services.ai_service import AIService

TEST_USER_ID = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
TEST_VOLUNTEER_ID = uuid.UUID("223e4567-e89b-12d3-a456-426614174000")


class DummySession:
    def close(self) -> None:
        return None


async def mock_get_current_user() -> User:
    user = User()
    user.id = TEST_USER_ID
    user.email = "test@foodbridge.com"
    user.role = RoleEnum.NGO
    user.is_active = True
    return user


def mock_get_db():
    yield DummySession()


async def mock_assign_best_volunteer(db, donation_id, ngo_id):
    return {
        "best_volunteer_id": TEST_VOLUNTEER_ID,
        "volunteer_id": TEST_VOLUNTEER_ID,
        "confidence_score": 0.9,
        "confidence": 0.9,
        "volunteer_name": "Test Volunteer",
        "name": "Test Volunteer",
        "distance_km": 1.2,
        "distance": 1.2,
    }


def mock_get_hunger_heatmap(db):
    return [{"lat": 28.6139, "lng": 77.2090, "weight": 0.8}]


def mock_check_fraud(db, user_id):
    return {
        "user_id": user_id,
        "fraud_risk_score": 12.5,
        "is_flagged": False,
        "reason": "Normal behavior",
    }


def mock_get_recommendations(db, donor_id):
    return {
        "recommended_ngo": "Test NGO",
        "best_pickup_time": "06:00 PM",
        "suggested_food_items": ["Rice", "Cooked Meals"],
    }


def mock_get_impact_insights(db):
    return {
        "insights": [
            "Food waste reduced by 15% this month.",
            "Most donations occur in the evening window.",
            "Volunteer activity rises on weekends.",
        ],
        "generated_at": "2026-01-01T00:00:00Z",
    }


def api_request(method: str, path: str, **kwargs) -> httpx.Response:
    async def _send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(_send())


@pytest.fixture(autouse=True)
def override_dependencies(monkeypatch):
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_db] = mock_get_db

    monkeypatch.setattr(
        AIService,
        "assign_best_volunteer",
        staticmethod(mock_assign_best_volunteer),
    )
    monkeypatch.setattr(
        AIService,
        "get_hunger_heatmap",
        staticmethod(mock_get_hunger_heatmap),
    )
    monkeypatch.setattr(AIService, "check_fraud", staticmethod(mock_check_fraud))
    monkeypatch.setattr(
        AIService,
        "get_recommendations",
        staticmethod(mock_get_recommendations),
    )
    monkeypatch.setattr(
        AIService,
        "get_impact_insights",
        staticmethod(mock_get_impact_insights),
    )

    yield

    app.dependency_overrides.clear()


def test_assign_volunteer():
    response = api_request(
        "POST",
        "/api/v1/ai/assign-volunteer",
        json={"donation_id": str(TEST_USER_ID)},
    )
    assert response.status_code == 200
    assert "best_volunteer_id" in response.json()


def test_check_food_freshness():
    response = api_request(
        "POST",
        "/api/v1/ai/check-food-freshness",
        json={"image_url": "http://example.com/food.jpg"},
    )
    assert response.status_code == 200
    assert "freshness_status" in response.json()


def test_hunger_heatmap():
    response = api_request("GET", "/api/v1/ai/hunger-heatmap")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_fraud_check():
    response = api_request(
        "POST",
        "/api/v1/ai/fraud-check",
        json={"user_id": str(TEST_USER_ID)},
    )
    assert response.status_code == 200
    assert "fraud_risk_score" in response.json()


def test_recommendations():
    response = api_request("GET", "/api/v1/ai/recommendations")
    assert response.status_code == 200
    assert "recommended_ngo" in response.json()


def test_impact_insights():
    response = api_request("GET", "/api/v1/ai/impact-insights")
    assert response.status_code == 200
    assert "insights" in response.json()
