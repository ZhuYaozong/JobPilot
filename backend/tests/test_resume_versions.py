from collections.abc import Callable

from fastapi.testclient import TestClient


def test_create_resume_version_success(
    client: TestClient,
    create_resume: Callable[[], dict],
    create_job: Callable[[], dict],
    test_marker: str,
) -> None:
    resume = create_resume()
    job = create_job()

    response = client.post(
        "/api/v1/resume-versions",
        json={
            "resume_id": resume["id"],
            "job_posting_id": job["id"],
            "version_no": 1,
            "version_label": f"{test_marker} tailored draft",
            "content": "# Tailored resume\nFastAPI workflow experience.",
            "change_summary": "Highlight workflow backend experience.",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["resume_id"] == resume["id"]
    assert data["version_no"] == 1
    assert data["version_label"] == f"{test_marker} tailored draft"


def test_list_resume_versions_by_resume_includes_created_version(
    client: TestClient,
    create_resume: Callable[[], dict],
    create_job: Callable[[], dict],
    test_marker: str,
) -> None:
    resume = create_resume()
    job = create_job()
    created = client.post(
        "/api/v1/resume-versions",
        json={
            "resume_id": resume["id"],
            "job_posting_id": job["id"],
            "version_no": 1,
            "version_label": f"{test_marker} list target",
            "content": "# Tailored resume\nVersion list check.",
        },
    )
    assert created.status_code == 201
    created_id = created.json()["id"]

    response = client.get(f"/api/v1/resumes/{resume['id']}/versions")

    assert response.status_code == 200
    versions = response.json()
    assert any(version["id"] == created_id for version in versions)
