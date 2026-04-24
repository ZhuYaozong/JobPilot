import argparse
import asyncio
from pathlib import Path
import sys

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import AsyncSessionLocal
from app.services.user_scope_service import (
    DEFAULT_DEMO_USERNAME,
    DEFAULT_SANDBOX_USERNAME,
    DEFAULT_TEST_USERNAME,
    is_generated_test_username,
)


POLLUTION_PATTERNS = [
    "%pytest%",
    "step%",
    "%step5%",
    "%step6%",
    "%step7%",
    "%step8%",
    "%workflow demo%",
    "%smoke test%",
]


async def fetch_scalar(sql: str, params: dict[str, object] | None = None) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(sql), params or {})
        value = result.scalar_one()
        return int(value or 0)


async def print_summary() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                """
                select
                  u.username,
                  u.is_test_user,
                  (select count(*) from resumes r where r.user_id = u.id) as resumes,
                  (select count(*) from job_postings j where j.user_id = u.id) as jobs,
                  (select count(*) from match_results m where m.user_id = u.id) as matches,
                  (select count(*) from application_records a where a.user_id = u.id) as applications,
                  (select count(*) from generated_artifacts g where g.user_id = u.id) as artifacts
                from users u
                order by u.id
                """
            )
        )
        rows = result.mappings().all()

    print("Current user data summary:")
    for row in rows:
        print(
            "- {username} test={is_test_user} resumes={resumes} jobs={jobs} "
            "matches={matches} applications={applications} artifacts={artifacts}".format(
                **row,
            )
        )


async def mark_generated_test_users(apply: bool) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("select id, username from users where is_test_user = false")
        )
        rows = result.mappings().all()
        target_ids = [
            row["id"]
            for row in rows
            if is_generated_test_username(str(row["username"]))
        ]

        if apply and target_ids:
            await session.execute(
                text("update users set is_test_user = true where id = any(:user_ids)"),
                {"user_ids": target_ids},
            )
            await session.commit()

    return len(target_ids)


async def collect_polluted_demo_sandbox_ids() -> dict[str, list[int]]:
    async with AsyncSessionLocal() as session:
        patterns = {"patterns": POLLUTION_PATTERNS}
        user_filter = {"usernames": [DEFAULT_DEMO_USERNAME, DEFAULT_SANDBOX_USERNAME]}

        resume_result = await session.execute(
            text(
                """
                select r.id
                from resumes r
                join users u on u.id = r.user_id
                where u.username = any(:usernames)
                  and (
                    r.title ilike any(:patterns)
                    or r.content_hash ilike any(:patterns)
                    or coalesce(r.source_file_url, '') ilike any(:patterns)
                  )
                """
            ),
            user_filter | patterns,
        )
        resume_ids = [int(row[0]) for row in resume_result.all()]

        job_result = await session.execute(
            text(
                """
                select j.id
                from job_postings j
                join users u on u.id = j.user_id
                where u.username = any(:usernames)
                  and (
                    j.company_name ilike any(:patterns)
                    or j.job_title ilike any(:patterns)
                    or coalesce(j.source_url, '') ilike any(:patterns)
                  )
                """
            ),
            user_filter | patterns,
        )
        job_ids = [int(row[0]) for row in job_result.all()]

    return {
        "resume_ids": resume_ids,
        "job_ids": job_ids,
    }


async def cleanup_demo_sandbox_pollution(apply: bool) -> dict[str, int]:
    ids = await collect_polluted_demo_sandbox_ids()
    resume_ids = ids["resume_ids"]
    job_ids = ids["job_ids"]
    counts: dict[str, int] = {
        "artifact_feedback_events": 0,
        "application_events": 0,
        "resume_versions": 0,
        "generated_artifacts": 0,
        "match_results": 0,
        "application_records": 0,
        "job_postings": len(job_ids),
        "resumes": len(resume_ids),
    }

    if not resume_ids and not job_ids:
        return counts

    async with AsyncSessionLocal() as session:
        params = {
            "resume_ids": resume_ids,
            "job_ids": job_ids,
            "usernames": [DEFAULT_DEMO_USERNAME, DEFAULT_SANDBOX_USERNAME],
        }

        affected_queries = {
            "artifact_feedback_events": """
                select count(*)
                from artifact_feedback_events f
                join generated_artifacts g on g.id = f.generated_artifact_id
                join users u on u.id = g.user_id
                where u.username = any(:usernames)
                  and (
                    g.resume_id = any(:resume_ids)
                    or g.job_posting_id = any(:job_ids)
                    or g.title ilike any(:patterns)
                  )
            """,
            "application_events": """
                select count(*)
                from application_events e
                join application_records a on a.id = e.application_record_id
                join users u on u.id = a.user_id
                where u.username = any(:usernames)
                  and (
                    a.resume_id = any(:resume_ids)
                    or a.job_posting_id = any(:job_ids)
                    or coalesce(a.notes, '') ilike any(:patterns)
                  )
            """,
            "resume_versions": """
                select count(*)
                from resume_versions v
                join resumes r on r.id = v.resume_id
                join users u on u.id = r.user_id
                where u.username = any(:usernames)
                  and (
                    v.resume_id = any(:resume_ids)
                    or v.job_posting_id = any(:job_ids)
                    or v.version_label ilike any(:patterns)
                    or coalesce(v.change_summary, '') ilike any(:patterns)
                  )
            """,
            "generated_artifacts": """
                select count(*)
                from generated_artifacts g
                join users u on u.id = g.user_id
                where u.username = any(:usernames)
                  and (
                    g.resume_id = any(:resume_ids)
                    or g.job_posting_id = any(:job_ids)
                    or g.application_record_id in (
                      select a.id
                      from application_records a
                      where a.resume_id = any(:resume_ids)
                         or a.job_posting_id = any(:job_ids)
                         or coalesce(a.notes, '') ilike any(:patterns)
                    )
                    or g.title ilike any(:patterns)
                  )
            """,
            "match_results": """
                select count(*)
                from match_results m
                join users u on u.id = m.user_id
                where u.username = any(:usernames)
                  and (m.resume_id = any(:resume_ids) or m.job_posting_id = any(:job_ids))
            """,
            "application_records": """
                select count(*)
                from application_records a
                join users u on u.id = a.user_id
                where u.username = any(:usernames)
                  and (
                    a.resume_id = any(:resume_ids)
                    or a.job_posting_id = any(:job_ids)
                    or coalesce(a.notes, '') ilike any(:patterns)
                )
            """,
        }

        count_params = params | {"patterns": POLLUTION_PATTERNS}
        for name, query in affected_queries.items():
            result = await session.execute(text(query), count_params)
            counts[name] = int(result.scalar_one() or 0)

        if not apply:
            return counts

        delete_statements = [
            """
            delete from artifact_feedback_events f
            using generated_artifacts g, users u
            where g.id = f.generated_artifact_id
              and u.id = g.user_id
              and u.username = any(:usernames)
              and (
                g.resume_id = any(:resume_ids)
                or g.job_posting_id = any(:job_ids)
                or g.title ilike any(:patterns)
              )
            """,
            """
            delete from application_events e
            using application_records a, users u
            where a.id = e.application_record_id
              and u.id = a.user_id
              and u.username = any(:usernames)
              and (
                a.resume_id = any(:resume_ids)
                or a.job_posting_id = any(:job_ids)
                or coalesce(a.notes, '') ilike any(:patterns)
              )
            """,
            """
            delete from resume_versions v
            using resumes r, users u
            where r.id = v.resume_id
              and u.id = r.user_id
              and u.username = any(:usernames)
              and (
                v.resume_id = any(:resume_ids)
                or v.job_posting_id = any(:job_ids)
                or v.version_label ilike any(:patterns)
                or coalesce(v.change_summary, '') ilike any(:patterns)
              )
            """,
            """
            delete from generated_artifacts g
            using users u
            where u.id = g.user_id
              and u.username = any(:usernames)
              and (
                g.resume_id = any(:resume_ids)
                or g.job_posting_id = any(:job_ids)
                or g.application_record_id in (
                  select a.id
                  from application_records a
                  where a.resume_id = any(:resume_ids)
                     or a.job_posting_id = any(:job_ids)
                     or coalesce(a.notes, '') ilike any(:patterns)
                )
                or g.title ilike any(:patterns)
              )
            """,
            """
            delete from match_results m
            using users u
            where u.id = m.user_id
              and u.username = any(:usernames)
              and (m.resume_id = any(:resume_ids) or m.job_posting_id = any(:job_ids))
            """,
            """
            delete from application_records a
            using users u
            where u.id = a.user_id
              and u.username = any(:usernames)
              and (
                a.resume_id = any(:resume_ids)
                or a.job_posting_id = any(:job_ids)
                or coalesce(a.notes, '') ilike any(:patterns)
              )
            """,
            "delete from job_postings where id = any(:job_ids)",
            "delete from resumes where id = any(:resume_ids)",
        ]

        for statement in delete_statements:
            await session.execute(text(statement), count_params)

        await session.commit()

    return counts


async def delete_generated_test_users(apply: bool) -> dict[str, int]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                """
                select id
                from users
                where username not in (:demo_username, :sandbox_username, :test_username)
                  and (is_test_user = true or username ilike any(:patterns))
                """
            ),
            {
                "demo_username": DEFAULT_DEMO_USERNAME,
                "sandbox_username": DEFAULT_SANDBOX_USERNAME,
                "test_username": DEFAULT_TEST_USERNAME,
                "patterns": POLLUTION_PATTERNS,
            },
        )
        user_ids = [int(row[0]) for row in result.all()]

        count_params = {"user_ids": user_ids}
        counts: dict[str, int] = {
            "users": len(user_ids),
            "resumes": 0,
            "jobs": 0,
            "matches": 0,
            "applications": 0,
            "artifacts": 0,
        }
        if not user_ids:
            return counts

        count_queries = {
            "resumes": "select count(*) from resumes where user_id = any(:user_ids)",
            "jobs": "select count(*) from job_postings where user_id = any(:user_ids)",
            "matches": "select count(*) from match_results where user_id = any(:user_ids)",
            "applications": "select count(*) from application_records where user_id = any(:user_ids)",
            "artifacts": "select count(*) from generated_artifacts where user_id = any(:user_ids)",
        }
        for name, query in count_queries.items():
            count_result = await session.execute(text(query), count_params)
            counts[name] = int(count_result.scalar_one() or 0)

        if not apply or not user_ids:
            return counts

        delete_statements = [
            """
            delete from artifact_feedback_events f
            using generated_artifacts g
            where g.id = f.generated_artifact_id and g.user_id = any(:user_ids)
            """,
            """
            delete from application_events e
            using application_records a
            where a.id = e.application_record_id and a.user_id = any(:user_ids)
            """,
            """
            delete from resume_versions v
            using resumes r
            where r.id = v.resume_id and r.user_id = any(:user_ids)
            """,
            "delete from generated_artifacts where user_id = any(:user_ids)",
            "delete from match_results where user_id = any(:user_ids)",
            "delete from application_records where user_id = any(:user_ids)",
            "delete from job_postings where user_id = any(:user_ids)",
            "delete from resumes where user_id = any(:user_ids)",
            "delete from users where id = any(:user_ids)",
        ]

        for statement in delete_statements:
            await session.execute(text(statement), count_params)

        await session.commit()

    return counts


def print_counts(title: str, counts: dict[str, int]) -> None:
    print(title)
    for key, value in counts.items():
        print(f"- {key}: {value}")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean local pytest/smoke data from JobPilot dev database.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete data. Without this flag the script only prints a dry-run.",
    )
    parser.add_argument(
        "--delete-test-users",
        action="store_true",
        help=(
            "Delete generated test users and their data. "
            "Without this flag they are only marked as is_test_user=true."
        ),
    )
    args = parser.parse_args()

    print("Mode:", "apply" if args.apply else "dry-run")
    await print_summary()

    marked_count = await mark_generated_test_users(apply=args.apply)
    print(f"Generated test users to mark as is_test_user=true: {marked_count}")

    demo_counts = await cleanup_demo_sandbox_pollution(apply=args.apply)
    print_counts("Demo/sandbox polluted business records:", demo_counts)

    if args.delete_test_users:
        test_counts = await delete_generated_test_users(apply=args.apply)
        print_counts("Generated test users to delete:", test_counts)

    if not args.apply:
        print("Dry-run only. Re-run with --apply to make changes.")


if __name__ == "__main__":
    asyncio.run(main())
