"""Prototype account configuration and role checks."""
import hashlib
import json
import os
import secrets
from typing import Literal, NamedTuple

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field


class Account(NamedTuple):
    username: str
    role: Literal["admin", "customer"]
    password: str


def load_accounts() -> dict[str, Account]:
    accounts = {}
    for role in ("admin", "customer"):
        username = os.getenv(f"CROSAFE_{role.upper()}_USER", role)
        password = os.getenv(f"CROSAFE_{role.upper()}_PASSWORD")
        if password:
            if username in accounts:
                raise ValueError("Dashboard account usernames must be distinct")
            accounts[username] = Account(username, role, password)
    additional = json.loads(os.getenv("CROSAFE_EXTRA_CUSTOMERS") or "{}")
    if not isinstance(additional, dict):
        raise ValueError("CROSAFE_EXTRA_CUSTOMERS must be a JSON object")
    for username, password in additional.items():
        if not username or username in accounts or not isinstance(password, str) or not password:
            raise ValueError("Each extra customer needs a distinct username and password")
        accounts[username] = Account(username, "customer", password)
    return accounts


basic = HTTPBasic(auto_error=False)
router = APIRouter(prefix="/v1/session", tags=["session"])
COOKIE = "crosafe_session"
SESSION_SECONDS = 8 * 60 * 60


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1, max_length=256)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def check_credentials(request: Request, username: str, password: str) -> Account:
    account = request.app.state.accounts.get(username)
    expected = account.password if account else ""
    if not secrets.compare_digest(expected.encode(), password.encode()) or account is None:
        raise HTTPException(401, "Invalid username or password")
    return account


def identify(
    request: Request, credentials: HTTPBasicCredentials | None = Depends(basic),
) -> Account:
    if credentials is not None:
        return check_credentials(request, credentials.username, credentials.password)
    token = request.cookies.get(COOKIE)
    if token:
        with request.app.state.pool.connection() as connection:
            row = connection.execute(
                "SELECT username FROM dashboard_sessions "
                "WHERE token_hash = %s AND expires_at > now()", (digest(token),),
            ).fetchone()
        if row and (account := request.app.state.accounts.get(row[0])):
            return account
    raise HTTPException(401, "Sign in required")


@router.post("/login")
def login(data: Login, request: Request, response: Response) -> dict:
    account = check_credentials(request, data.username, data.password)
    token = secrets.token_urlsafe(32)
    old_token = request.cookies.get(COOKIE)
    with request.app.state.pool.connection() as connection:
        connection.execute("DELETE FROM dashboard_sessions WHERE expires_at <= now()")
        if old_token:
            connection.execute("DELETE FROM dashboard_sessions WHERE token_hash = %s", (digest(old_token),))
        connection.execute(
            "INSERT INTO dashboard_sessions VALUES (%s, %s, now() + %s * interval '1 second')",
            (digest(token), account.username, SESSION_SECONDS),
        )
    response.set_cookie(
        COOKIE, token, max_age=SESSION_SECONDS, httponly=True, samesite="strict",
        secure=os.getenv("CROSAFE_SECURE_COOKIE", "false").lower() == "true",
    )
    return {"username": account.username, "role": account.role}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(COOKIE)
    if token:
        with request.app.state.pool.connection() as connection:
            connection.execute("DELETE FROM dashboard_sessions WHERE token_hash = %s", (digest(token),))
    response.delete_cookie(COOKIE)
    return {"signed_out": True}


@router.get("/me")
def me(account: Account = Depends(identify)) -> dict:
    return {"username": account.username, "role": account.role}


def admin(account: Account = Depends(identify)) -> Account:
    if account.role != "admin":
        raise HTTPException(403, "Administrator access required")
    return account


def customer(account: Account = Depends(identify)) -> Account:
    if account.role != "customer":
        raise HTTPException(403, "Customer access required")
    return account
