import hashlib

from fastapi.testclient import TestClient


def make_headers(username: str) -> dict[str, str]:
    return {"X-User-Name": username}


def compact_value(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    return f"{value[: max_length - len(digest) - 1]}-{digest}"


def create_resume(
    client: TestClient,
    username: str,
    title: str,
    content_hash: str,
) -> dict:
    response = client.post(
        "/api/v1/resumes",
        headers=make_headers(username),
        json={
            "title": title,
            "raw_text": "FastAPI, SQLAlchemy, workflow state.",
            "content_hash": compact_value(content_hash, 64),
            "source_type": "manual",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_job(
    client: TestClient,
    username: str,
    company_name: str,
    job_title: str,
) -> dict:
    response = client.post(
        "/api/v1/jobs",
        headers=make_headers(username),
        json={
            "company_name": company_name,
            "job_title": job_title,
            "city": "Shanghai",
            "jd_text": "Build workflow-backed AI applications with FastAPI.",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_application(
    client: TestClient,
    username: str,
    resume_id: int,
    job_id: int,
    next_action: str,
) -> dict:
    response = client.post(
        "/api/v1/applications",
        headers=make_headers(username),
        json={
            "resume_id": resume_id,
            "job_posting_id": job_id,
            "current_stage": "saved",
            "next_action": next_action,
        },
    )
    assert response.status_code == 201
    return response.json()


def create_match(
    client: TestClient,
    username: str,
    resume_id: int,
    job_id: int,
    overall_score: float,
) -> dict:
    response = client.post(
        "/api/v1/matches",
        headers=make_headers(username),
        json={
            "resume_id": resume_id,
            "job_posting_id": job_id,
            "overall_score": overall_score,
            "strengths": ["fastapi"],
            "weaknesses": ["none"],
            "missing_keywords": ["agent"],
            "suggestions": ["add workflow examples"],
        },
    )
    assert response.status_code == 201
    return response.json()


def create_artifact(
    client: TestClient,
    username: str,
    resume_id: int,
    job_id: int,
    application_id: int,
    title: str,
) -> dict:
    response = client.post(
        "/api/v1/artifacts",
        headers=make_headers(username),
        json={
            "artifact_type": "cover_letter",
            "title": title,
            "resume_id": resume_id,
            "job_posting_id": job_id,
            "application_record_id": application_id,
            "content_text": "Draft content",
            "generator_type": "manual",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_resume_version(
    client: TestClient,
    username: str,
    resume_id: int,
    job_id: int | None,
    label: str,
) -> dict:
    response = client.post(
        "/api/v1/resume-versions",
        headers=make_headers(username),
        json={
            "resume_id": resume_id,
            "job_posting_id": job_id,
            "version_no": 1,
            "version_label": label,
            "content": "Version content",
            "content_format": "markdown",
            "source_type": "manual",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_artifact_feedback(
    client: TestClient,
    username: str,
    artifact_id: int,
) -> dict:
    response = client.post(
        f"/api/v1/artifacts/{artifact_id}/feedback",
        headers=make_headers(username),
        json={"feedback_type": "saved_for_later", "note": "Looks useful"},
    )
    assert response.status_code == 201
    return response.json()


def transition_application(
    client: TestClient,
    username: str,
    application_id: int,
) -> dict:
    response = client.post(
        f"/api/v1/applications/{application_id}/transition",
        headers=make_headers(username),
        json={
            "target_stage": "applied",
            "next_action": "Follow up",
            "note": "Submitted application",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_default_pytest_user_scope_does_not_leak_into_demo(
    client: TestClient,
    test_marker: str,
) -> None:
    test_resume = client.post(
        "/api/v1/resumes",
        json={
            "title": f"{test_marker} pytest resume",
            "raw_text": "Pytest scoped data only.",
            "content_hash": f"{test_marker}-pytest-resume",
            "source_type": "manual",
        },
    )
    assert test_resume.status_code == 201
    created_id = test_resume.json()["id"]

    demo_list = client.get("/api/v1/resumes?limit=100", headers=make_headers("demo"))
    assert demo_list.status_code == 200
    demo_ids = {item["id"] for item in demo_list.json()}
    assert created_id not in demo_ids

    demo_detail = client.get(
        f"/api/v1/resumes/{created_id}",
        headers=make_headers("demo"),
    )
    assert demo_detail.status_code == 404


def test_core_resource_lists_are_user_scoped(
    client: TestClient,
    test_marker: str,
) -> None:
    demo_user = f"demo-{test_marker}"
    sandbox_user = f"sandbox-{test_marker}"

    demo_resume = create_resume(
        client,
        demo_user,
        f"{test_marker} demo resume",
        f"{test_marker}-demo-resume",
    )
    demo_job = create_job(
        client,
        demo_user,
        f"{test_marker} demo company",
        "Demo AI Engineer",
    )
    demo_application = create_application(
        client,
        demo_user,
        demo_resume["id"],
        demo_job["id"],
        "Follow up with recruiter",
    )
    demo_match = create_match(
        client,
        demo_user,
        demo_resume["id"],
        demo_job["id"],
        88,
    )
    demo_artifact = create_artifact(
        client,
        demo_user,
        demo_resume["id"],
        demo_job["id"],
        demo_application["id"],
        f"{test_marker} demo artifact",
    )

    sandbox_resume = create_resume(
        client,
        sandbox_user,
        f"{test_marker} sandbox resume",
        f"{test_marker}-sandbox-resume",
    )
    sandbox_job = create_job(
        client,
        sandbox_user,
        f"{test_marker} sandbox company",
        "Sandbox AI Engineer",
    )
    sandbox_application = create_application(
        client,
        sandbox_user,
        sandbox_resume["id"],
        sandbox_job["id"],
        "Prepare interview",
    )
    sandbox_match = create_match(
        client,
        sandbox_user,
        sandbox_resume["id"],
        sandbox_job["id"],
        75,
    )
    sandbox_artifact = create_artifact(
        client,
        sandbox_user,
        sandbox_resume["id"],
        sandbox_job["id"],
        sandbox_application["id"],
        f"{test_marker} sandbox artifact",
    )

    for path, demo_id, sandbox_id in [
        ("/api/v1/resumes?limit=100", demo_resume["id"], sandbox_resume["id"]),
        ("/api/v1/jobs?limit=100", demo_job["id"], sandbox_job["id"]),
        ("/api/v1/matches?limit=100", demo_match["id"], sandbox_match["id"]),
        ("/api/v1/artifacts?limit=100", demo_artifact["id"], sandbox_artifact["id"]),
        (
            "/api/v1/applications?limit=100",
            demo_application["id"],
            sandbox_application["id"],
        ),
    ]:
        demo_response = client.get(path, headers=make_headers(demo_user))
        sandbox_response = client.get(path, headers=make_headers(sandbox_user))
        assert demo_response.status_code == 200
        assert sandbox_response.status_code == 200

        demo_ids = {item["id"] for item in demo_response.json()}
        sandbox_ids = {item["id"] for item in sandbox_response.json()}

        assert demo_id in demo_ids
        assert sandbox_id not in demo_ids
        assert sandbox_id in sandbox_ids
        assert demo_id not in sandbox_ids

    cross_scope_artifact = client.get(
        f"/api/v1/artifacts/{sandbox_artifact['id']}",
        headers=make_headers(demo_user),
    )
    assert cross_scope_artifact.status_code == 404


def test_updated_at_recent_first_rules_for_jobs_resumes_and_applications(
    client: TestClient,
    test_marker: str,
) -> None:
    username = f"ordering-updated-{test_marker}"

    older_job = create_job(client, username, f"{test_marker} older company", "Older Job")
    newer_job = create_job(client, username, f"{test_marker} newer company", "Newer Job")
    job_patch = client.patch(
        f"/api/v1/jobs/{older_job['id']}",
        headers=make_headers(username),
        json={"city": "Beijing"},
    )
    assert job_patch.status_code == 200
    jobs = client.get("/api/v1/jobs?limit=1", headers=make_headers(username))
    assert jobs.status_code == 200
    assert jobs.json()[0]["id"] == older_job["id"]
    assert newer_job["id"] != older_job["id"]
    jobs_offset = client.get("/api/v1/jobs?limit=1&offset=1", headers=make_headers(username))
    assert jobs_offset.status_code == 200
    assert jobs_offset.json()[0]["id"] == newer_job["id"]

    older_resume = create_resume(
        client,
        username,
        f"{test_marker} older resume",
        f"{test_marker}-older-resume",
    )
    newer_resume = create_resume(
        client,
        username,
        f"{test_marker} newer resume",
        f"{test_marker}-newer-resume",
    )
    resume_patch = client.patch(
        f"/api/v1/resumes/{older_resume['id']}",
        headers=make_headers(username),
        json={"title": f"{test_marker} older resume patched"},
    )
    assert resume_patch.status_code == 200
    resumes = client.get("/api/v1/resumes?limit=1", headers=make_headers(username))
    assert resumes.status_code == 200
    assert resumes.json()[0]["id"] == older_resume["id"]
    assert newer_resume["id"] != older_resume["id"]

    older_resume_ref = create_resume(
        client,
        username,
        f"{test_marker} application resume A",
        f"{test_marker}-application-resume-a",
    )
    older_job_ref = create_job(
        client,
        username,
        f"{test_marker} application company A",
        "Application Job A",
    )
    newer_resume_ref = create_resume(
        client,
        username,
        f"{test_marker} application resume B",
        f"{test_marker}-application-resume-b",
    )
    newer_job_ref = create_job(
        client,
        username,
        f"{test_marker} application company B",
        "Application Job B",
    )
    older_application = create_application(
        client,
        username,
        older_resume_ref["id"],
        older_job_ref["id"],
        "Old action",
    )
    newer_application = create_application(
        client,
        username,
        newer_resume_ref["id"],
        newer_job_ref["id"],
        "New action",
    )
    application_patch = client.patch(
        f"/api/v1/applications/{older_application['id']}",
        headers=make_headers(username),
        json={"notes": "Touched later"},
    )
    assert application_patch.status_code == 200
    applications = client.get(
        "/api/v1/applications?limit=1",
        headers=make_headers(username),
    )
    assert applications.status_code == 200
    assert applications.json()[0]["id"] == older_application["id"]
    assert newer_application["id"] != older_application["id"]


def test_created_at_recent_first_rules_for_matches_and_artifacts(
    client: TestClient,
    test_marker: str,
) -> None:
    username = f"ordering-created-{test_marker}"

    first_resume = create_resume(
        client,
        username,
        f"{test_marker} first resume",
        f"{test_marker}-first-resume",
    )
    first_job = create_job(
        client,
        username,
        f"{test_marker} first company",
        "First Match Job",
    )
    second_resume = create_resume(
        client,
        username,
        f"{test_marker} second resume",
        f"{test_marker}-second-resume",
    )
    second_job = create_job(
        client,
        username,
        f"{test_marker} second company",
        "Second Match Job",
    )

    first_match = create_match(
        client,
        username,
        first_resume["id"],
        first_job["id"],
        61,
    )
    second_match = create_match(
        client,
        username,
        second_resume["id"],
        second_job["id"],
        92,
    )
    matches = client.get("/api/v1/matches?limit=1", headers=make_headers(username))
    assert matches.status_code == 200
    assert matches.json()[0]["id"] == second_match["id"]
    assert first_match["id"] != second_match["id"]
    matches_offset = client.get(
        "/api/v1/matches?limit=1&offset=1",
        headers=make_headers(username),
    )
    assert matches_offset.status_code == 200
    assert matches_offset.json()[0]["id"] == first_match["id"]

    first_application = create_application(
        client,
        username,
        first_resume["id"],
        first_job["id"],
        "Artifact action A",
    )
    second_application = create_application(
        client,
        username,
        second_resume["id"],
        second_job["id"],
        "Artifact action B",
    )
    first_artifact = create_artifact(
        client,
        username,
        first_resume["id"],
        first_job["id"],
        first_application["id"],
        f"{test_marker} first artifact",
    )
    second_artifact = create_artifact(
        client,
        username,
        second_resume["id"],
        second_job["id"],
        second_application["id"],
        f"{test_marker} second artifact",
    )
    artifacts = client.get("/api/v1/artifacts?limit=1", headers=make_headers(username))
    assert artifacts.status_code == 200
    assert artifacts.json()[0]["id"] == second_artifact["id"]
    assert first_artifact["id"] != second_artifact["id"]


def test_delete_application_removes_timeline_and_linked_artifacts(
    client: TestClient,
    test_marker: str,
) -> None:
    username = f"delete-application-{test_marker}"
    resume = create_resume(client, username, f"{test_marker} resume", f"{test_marker}-resume")
    job = create_job(client, username, f"{test_marker} company", "Application Delete Job")
    application = create_application(client, username, resume["id"], job["id"], "Delete me")
    artifact = create_artifact(
        client,
        username,
        resume["id"],
        job["id"],
        application["id"],
        f"{test_marker} application artifact",
    )
    create_artifact_feedback(client, username, artifact["id"])
    transition_application(client, username, application["id"])

    cross_scope_delete = client.delete(
        f"/api/v1/applications/{application['id']}",
        headers=make_headers(f"other-{test_marker}"),
    )
    assert cross_scope_delete.status_code == 404

    response = client.delete(
        f"/api/v1/applications/{application['id']}",
        headers=make_headers(username),
    )
    assert response.status_code == 204
    assert response.content == b""

    assert client.get(
        f"/api/v1/applications/{application['id']}",
        headers=make_headers(username),
    ).status_code == 404
    assert client.get(
        f"/api/v1/artifacts/{artifact['id']}",
        headers=make_headers(username),
    ).status_code == 404
    assert client.get(f"/api/v1/resumes/{resume['id']}", headers=make_headers(username)).status_code == 200
    assert client.get(f"/api/v1/jobs/{job['id']}", headers=make_headers(username)).status_code == 200


def test_delete_match_keeps_resume_and_job(
    client: TestClient,
    test_marker: str,
) -> None:
    username = f"delete-match-{test_marker}"
    resume = create_resume(client, username, f"{test_marker} resume", f"{test_marker}-resume")
    job = create_job(client, username, f"{test_marker} company", "Match Delete Job")
    match = create_match(client, username, resume["id"], job["id"], 70)

    response = client.delete(
        f"/api/v1/matches/{match['id']}",
        headers=make_headers(username),
    )
    assert response.status_code == 204

    assert client.get(f"/api/v1/matches/{match['id']}", headers=make_headers(username)).status_code == 404
    assert client.get(f"/api/v1/resumes/{resume['id']}", headers=make_headers(username)).status_code == 200
    assert client.get(f"/api/v1/jobs/{job['id']}", headers=make_headers(username)).status_code == 200


def test_delete_resume_cascades_owned_business_records(
    client: TestClient,
    test_marker: str,
) -> None:
    username = f"delete-resume-{test_marker}"
    resume = create_resume(client, username, f"{test_marker} resume", f"{test_marker}-resume")
    job = create_job(client, username, f"{test_marker} company", "Resume Delete Job")
    application = create_application(client, username, resume["id"], job["id"], "Delete resume")
    match = create_match(client, username, resume["id"], job["id"], 81)
    version = create_resume_version(
        client,
        username,
        resume["id"],
        job["id"],
        f"{test_marker} version",
    )
    artifact = create_artifact(
        client,
        username,
        resume["id"],
        job["id"],
        application["id"],
        f"{test_marker} resume artifact",
    )
    create_artifact_feedback(client, username, artifact["id"])
    transition_application(client, username, application["id"])

    response = client.delete(
        f"/api/v1/resumes/{resume['id']}",
        headers=make_headers(username),
    )
    assert response.status_code == 204

    for path in [
        f"/api/v1/resumes/{resume['id']}",
        f"/api/v1/applications/{application['id']}",
        f"/api/v1/matches/{match['id']}",
        f"/api/v1/resume-versions/{version['id']}",
        f"/api/v1/artifacts/{artifact['id']}",
    ]:
        assert client.get(path, headers=make_headers(username)).status_code == 404

    assert client.get(f"/api/v1/jobs/{job['id']}", headers=make_headers(username)).status_code == 200


def test_delete_job_cascades_owned_business_records(
    client: TestClient,
    test_marker: str,
) -> None:
    username = f"delete-job-{test_marker}"
    resume = create_resume(client, username, f"{test_marker} resume", f"{test_marker}-resume")
    job = create_job(client, username, f"{test_marker} company", "Job Delete Job")
    application = create_application(client, username, resume["id"], job["id"], "Delete job")
    match = create_match(client, username, resume["id"], job["id"], 82)
    version = create_resume_version(
        client,
        username,
        resume["id"],
        job["id"],
        f"{test_marker} version",
    )
    artifact = create_artifact(
        client,
        username,
        resume["id"],
        job["id"],
        application["id"],
        f"{test_marker} job artifact",
    )
    create_artifact_feedback(client, username, artifact["id"])
    transition_application(client, username, application["id"])

    response = client.delete(f"/api/v1/jobs/{job['id']}", headers=make_headers(username))
    assert response.status_code == 204

    for path in [
        f"/api/v1/jobs/{job['id']}",
        f"/api/v1/applications/{application['id']}",
        f"/api/v1/matches/{match['id']}",
        f"/api/v1/resume-versions/{version['id']}",
        f"/api/v1/artifacts/{artifact['id']}",
    ]:
        assert client.get(path, headers=make_headers(username)).status_code == 404

    assert client.get(f"/api/v1/resumes/{resume['id']}", headers=make_headers(username)).status_code == 200
