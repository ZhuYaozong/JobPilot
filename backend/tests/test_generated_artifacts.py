from collections.abc import Callable

from fastapi.testclient import TestClient


def test_create_generated_artifact_success(
    client: TestClient,
    create_application: Callable[[], dict],
    test_marker: str,
) -> None:
    application = create_application()

    response = client.post(
        "/api/v1/artifacts",
        json={
            "artifact_type": "cover_letter",
            "application_record_id": application["id"],
            "title": f"{test_marker} cover letter draft",
            "content_text": "Dear hiring team, this is a manual draft.",
            "content_json": {"sections": ["intro", "fit"]},
            "generator_type": "manual",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["artifact_type"] == "cover_letter"
    assert data["application_record_id"] == application["id"]
    assert data["title"] == f"{test_marker} cover letter draft"
    assert data["status"] == "draft"


def test_create_generated_artifact_requires_business_link(
    client: TestClient,
    test_marker: str,
) -> None:
    response = client.post(
        "/api/v1/artifacts",
        json={
            "artifact_type": "cover_letter",
            "title": f"{test_marker} orphan artifact",
            "content_text": "This artifact has no business link.",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Generated artifact must link to at least one business object"
    )


def test_read_generated_artifact_success(
    client: TestClient,
    create_resume: Callable[[], dict],
    test_marker: str,
) -> None:
    resume = create_resume()
    created = client.post(
        "/api/v1/artifacts",
        json={
            "artifact_type": "resume_summary",
            "resume_id": resume["id"],
            "title": f"{test_marker} resume summary",
            "content_text": "Manual summary for testing.",
            "content_json": {"highlights": ["FastAPI"]},
        },
    )
    assert created.status_code == 201
    artifact_id = created.json()["id"]

    response = client.get(f"/api/v1/artifacts/{artifact_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == artifact_id
    assert data["resume_id"] == resume["id"]
    assert data["content_json"] == {"highlights": ["FastAPI"]}


def test_delete_generated_artifact_removes_feedback(
    client: TestClient,
    create_resume: Callable[[], dict],
    test_marker: str,
) -> None:
    resume = create_resume()
    created = client.post(
        "/api/v1/artifacts",
        json={
            "artifact_type": "cover_letter",
            "resume_id": resume["id"],
            "title": f"{test_marker} delete me",
            "content_text": "Manual draft.",
        },
    )
    assert created.status_code == 201
    artifact_id = created.json()["id"]

    feedback = client.post(
        f"/api/v1/artifacts/{artifact_id}/feedback",
        json={"feedback_type": "accepted", "note": "looks good"},
    )
    assert feedback.status_code == 201

    response = client.delete(f"/api/v1/artifacts/{artifact_id}")
    assert response.status_code == 204

    assert client.get(f"/api/v1/artifacts/{artifact_id}").status_code == 404
    assert client.get(f"/api/v1/artifacts/{artifact_id}/feedback").status_code == 404
