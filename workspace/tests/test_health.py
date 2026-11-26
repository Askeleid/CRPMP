import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_health_check_returns_200(client):
    """Verify /api/health/ returns HTTP 200 with status ok."""
    response = client.get(reverse("health-check"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_swagger_docs_returns_200(client):
    """Verify /api/docs/ serves the Swagger UI with HTTP 200."""
    response = client.get(reverse("swagger-ui"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_openapi_schema_returns_200(client):
    """Verify /api/schema/ serves the OpenAPI 3 schema with HTTP 200."""
    response = client.get(reverse("schema"))

    assert response.status_code == 200
    assert b"/api/health/" in response.content
