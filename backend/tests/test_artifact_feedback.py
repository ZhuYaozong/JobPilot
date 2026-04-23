from collections.abc import Callable

from fastapi.testclient import TestClient


def create_artifact(
    client: TestClient,
    create_resume: Callable[[], dict],
    test_marker: str,
) -> dict:
    resume = create_resume()
    response = client.post(
        "/api/v1/artifacts",
        json={
            "artifact_type": "cover_letter",
            "resume_id": resume["id"],
            "title": f"{test_marker} feedback target",
            "content_text": "Draft content for feedback tests.",
            "content_json": {"source": "pytest"},
            "generator_type": "ai",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_artifact_feedback_success(
    client: TestClient,
    create_resume: Callable[[], dict],
    test_marker: str,
) -> None:
    artifact = create_artifact(client, create_resume, test_marker)

    response = client.post(
        f"/api/v1/artifacts/{artifact['id']}/feedback",
        json={
            "feedback_type": "accepted",
            "note": "Used as the final draft.",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["generated_artifact_id"] == artifact["id"]
    assert data["feedback_type"] == "accepted"
    assert data["note"] == "Used as the final draft."
    assert data["id"] is not None
    assert data["created_at"] is not None


def test_list_artifact_feedback_success(
    client: TestClient,
    create_resume: Callable[[], dict],
    test_marker: str,
) -> None:
    artifact = create_artifact(client, create_resume, test_marker)

    first = client.post(
        f"/api/v1/artifacts/{artifact['id']}/feedback",
        json={"feedback_type": "saved_for_later", "note": "Review later."},
    )
    assert first.status_code == 201

    second = client.post(
        f"/api/v1/artifacts/{artifact['id']}/feedback",
        json={"feedback_type": "edited_then_used", "note": "Edited intro."},
    )
    assert second.status_code == 201

    response = client.get(f"/api/v1/artifacts/{artifact['id']}/feedback")

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    assert [item["id"] for item in data[:2]] == [
        second.json()["id"],
        first.json()["id"],
    ]
    assert data[0]["feedback_type"] == "edited_then_used"
    assert data[1]["feedback_type"] == "saved_for_later"


def test_create_artifact_feedback_missing_artifact_returns_404(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/artifacts/999999999/feedback",
        json={"feedback_type": "accepted"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Generated artifact not found"


def test_list_artifact_feedback_missing_artifact_returns_404(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/artifacts/999999999/feedback")

    assert response.status_code == 404
    assert response.json()["detail"] == "Generated artifact not found"


def test_create_artifact_feedback_invalid_type_returns_400(
    client: TestClient,
    create_resume: Callable[[], dict],
    test_marker: str,
) -> None:
    artifact = create_artifact(client, create_resume, test_marker)

    response = client.post(
        f"/api/v1/artifacts/{artifact['id']}/feedback",
        json={"feedback_type": "liked"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid feedback_type"
