import datetime
import json
import logging
import os
import re
import sqlite3
import time
from collections import defaultdict, deque
from contextlib import closing
from typing import Any, Dict, Literal
from urllib.parse import urlencode, urlparse

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

APP_NAME = "prod-mcp-server"
DB_PATH = os.getenv("MCP_DB_PATH", "mcp.db")
API_TOKEN = os.getenv("MCP_API_TOKEN", "")
REQUEST_TIMEOUT_SEC = int(os.getenv("MCP_HTTP_TIMEOUT_SEC", "10"))
ALLOWED_HTTP_HOSTS = set(
    host.strip()
    for host in os.getenv("MCP_ALLOWED_HTTP_HOSTS", "jsonplaceholder.typicode.com").split(",")
    if host.strip()
)
RATE_LIMIT_PER_MIN = int(os.getenv("MCP_RATE_LIMIT_PER_MIN", "120"))
token_buckets: dict[str, deque[float]] = defaultdict(deque)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(APP_NAME)
mcp = FastMCP(APP_NAME)


class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    status: Literal["active", "inactive"] = "active"


class CustomerOut(BaseModel):
    id: int
    name: str
    email: str
    status: Literal["active", "inactive"]


class FetchJsonOut(BaseModel):
    url: str
    status_code: int
    data: dict[str, Any]


def _is_valid_email(email: str) -> bool:
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None


def _require_token(token: str) -> None:
    if not API_TOKEN:
        raise ValueError("Server misconfigured: MCP_API_TOKEN is missing")
    if token != API_TOKEN:
        raise PermissionError("Unauthorized token")


def _check_rate_limit(token: str) -> None:
    now = time.time()
    window_start = now - 60
    bucket = token_buckets[token]

    while bucket and bucket[0] < window_start:
        bucket.popleft()

    if len(bucket) >= RATE_LIMIT_PER_MIN:
        raise RuntimeError("Rate limit exceeded")

    bucket.append(now)


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Only https URLs are allowed")
    if parsed.hostname.lower() not in ALLOWED_HTTP_HOSTS:
        raise PermissionError(f"Host '{parsed.hostname}' not in allowlist")


def _init_db() -> None:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL CHECK(status IN ('active', 'inactive'))
            )
            """
        )
        conn.commit()


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_query_params(params_dict: Dict[str, Any]) -> str:
    if not params_dict:
        return ""

    query_pairs: list[tuple[str, str]] = []
    for key, value in params_dict.items():
        if value is None:
            continue
        if isinstance(value, list):
            for list_value in value:
                query_pairs.append((key, str(list_value)))
        else:
            query_pairs.append((key, str(value)))

    if not query_pairs:
        return ""
    return "?" + urlencode(query_pairs)


@mcp.tool()
def healthcheck() -> dict[str, Any]:
    return {
        "ok": True,
        "service": APP_NAME,
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


@mcp.tool()
def fetch_json(url: str, token: str) -> dict[str, Any]:
    _require_token(token)
    _check_rate_limit(token)
    _validate_url(url)

    response = requests.get(url, timeout=REQUEST_TIMEOUT_SEC)
    response.raise_for_status()

    output = FetchJsonOut(url=url, status_code=response.status_code, data=response.json())
    return output.model_dump()


@mcp.tool()
def upsert_customer(customer: dict[str, Any], token: str) -> dict[str, Any]:
    _require_token(token)
    _check_rate_limit(token)

    try:
        validated = CustomerIn.model_validate(customer)
    except ValidationError as exc:
        raise ValueError(f"Invalid customer payload: {exc}") from exc

    if not _is_valid_email(validated.email):
        raise ValueError("Invalid customer payload: email must be a valid address")

    with closing(_db()) as conn:
        existing = conn.execute(
            "SELECT id FROM customers WHERE email = ?",
            (validated.email,),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE customers SET name = ?, status = ? WHERE email = ?",
                (validated.name, validated.status, validated.email),
            )
            customer_id = existing["id"]
        else:
            result = conn.execute(
                "INSERT INTO customers (name, email, status) VALUES (?, ?, ?)",
                (validated.name, validated.email, validated.status),
            )
            customer_id = result.lastrowid

        conn.commit()

        row = conn.execute(
            "SELECT id, name, email, status FROM customers WHERE id = ?",
            (customer_id,),
        ).fetchone()

    return CustomerOut(**dict(row)).model_dump()


@mcp.tool()
def list_customers(limit: int = 50, token: str = "") -> dict[str, Any]:
    _require_token(token)
    _check_rate_limit(token)

    bounded_limit = max(1, min(limit, 500))
    with closing(_db()) as conn:
        rows = conn.execute(
            "SELECT id, name, email, status FROM customers ORDER BY id DESC LIMIT ?",
            (bounded_limit,),
        ).fetchall()

    items = [CustomerOut(**dict(row)).model_dump() for row in rows]
    return {"count": len(items), "items": items}


@mcp.tool()
def webhook_github_push(payload: dict[str, Any], token: str) -> dict[str, Any]:
    _require_token(token)
    _check_rate_limit(token)

    repo = payload.get("repository", {}).get("full_name")
    ref = payload.get("ref")
    commit = payload.get("head_commit", {}).get("id")
    message = payload.get("head_commit", {}).get("message")

    return {"ok": True, "repo": repo, "ref": ref, "commit": commit, "message": message}


def main() -> None:
    _init_db()
    log.info("Starting MCP server: %s", APP_NAME)
    mcp.run()


if __name__ == "__main__":
    main()
