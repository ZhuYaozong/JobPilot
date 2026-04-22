from collections.abc import Callable

from fastapi.testclient import TestClient


def test_application_transition_updates_stage_and_writes_event(
    client: TestClient,
    create_application: Callable[[], dict],
    test_marker: str,
) -> None:
    application = create_application()

    transition = client.post(
        f"/api/v1/applications/{application['id']}/transition",
        json={
            "target_stage": "applied",
            "next_action": "Follow up with HR",
            "notes": "Submitted tailored resume.",
            "note": f"{test_marker} stage change",
            "payload_json": {"source": test_marker},
        },
    )

    assert transition.status_code == 200
    data = transition.json()
    assert data["id"] == application["id"]
    assert data["current_stage"] == "applied"
    assert data["next_action"] == "Follow up with HR"

    events = client.get(f"/api/v1/applications/{application['id']}/events")

    assert events.status_code == 200
    event_data = events.json()
    assert any(
        event["event_type"] == "stage_changed"
        and event["from_stage"] == "saved"
        and event["to_stage"] == "applied"
        for event in event_data
    )


def test_transition_missing_application_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/applications/999999999/transition",
        json={"target_stage": "applied"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Application record not found"
