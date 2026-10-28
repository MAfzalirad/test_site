from __future__ import annotations

import os
import secrets
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Iterator, Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "/data/poll.sqlite3"))
VOTE_OPTIONS = ("yes", "no", "abstain")
COOKIE_NAME = "poll_voter"


@contextmanager
def connect_db() -> Iterator[sqlite3.Connection]:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_db() -> None:
    with connect_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voter_id TEXT NOT NULL UNIQUE,
                choice TEXT NOT NULL CHECK (choice IN ('yes', 'no', 'abstain')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def get_results() -> dict[str, object]:
    with connect_db() as connection:
        rows = connection.execute(
            "SELECT choice, COUNT(*) AS count FROM votes GROUP BY choice"
        ).fetchall()
    counts = {option: 0 for option in VOTE_OPTIONS}
    counts.update({row["choice"]: row["count"] for row in rows})
    return {"total": sum(counts.values()), "counts": counts}


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_db()
    yield


app = FastAPI(
    title="رأی‌گیری آزمایشی",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)


class VoteSubmission(BaseModel):
    choice: Literal["yes", "no", "abstain"]


@app.get("/", include_in_schema=False)
def homepage() -> FileResponse:
    return FileResponse(ROOT_DIR / "index.html", media_type="text/html")


@app.get("/api/poll")
def poll_status(request: Request) -> dict[str, object]:
    result = get_results()
    voter_id = request.cookies.get(COOKIE_NAME)
    with connect_db() as connection:
        has_voted = bool(
            voter_id
            and connection.execute(
                "SELECT 1 FROM votes WHERE voter_id = ?", (voter_id,)
            ).fetchone()
        )
    result["has_voted"] = has_voted
    return result


@app.post("/api/vote")
def submit_vote(
    vote: VoteSubmission, request: Request, response: Response
) -> dict[str, object]:
    voter_id = request.cookies.get(COOKIE_NAME) or secrets.token_urlsafe(32)
    try:
        with connect_db() as connection:
            connection.execute(
                "INSERT INTO votes (voter_id, choice) VALUES (?, ?)",
                (voter_id, vote.choice),
            )
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="رأی شما قبلاً ثبت شده است.") from error

    response.set_cookie(
        key=COOKIE_NAME,
        value=voter_id,
        max_age=60 * 60 * 24 * 365,
        httponly=True,
        secure=request.headers.get("x-forwarded-proto", request.url.scheme) == "https",
        samesite="lax",
        path="/",
    )
    return get_results()


@app.get("/healthz", include_in_schema=False)
def health_check() -> dict[str, str]:
    return {"status": "ok"}
