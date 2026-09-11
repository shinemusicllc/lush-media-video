"""Pydantic models cho API requests / responses."""

from pydantic import BaseModel
from typing import Optional


class UserLogin(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"


class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class JobClearRequest(BaseModel):
    job_ids: list[str] = []


class JobResponse(BaseModel):
    id: str
    username: str
    server_id: str
    server_name: str
    status: str
    progress: int
    error_msg: Optional[str] = None
    input_image: str
    created_at: str
    completed_at: Optional[str] = None
    has_output: bool = False


class ServerStatusResponse(BaseModel):
    id: str
    name: str
    status: str
    current_job: Optional[str] = None
    queue_size: int
