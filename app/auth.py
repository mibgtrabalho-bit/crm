import secrets
from fastapi import Depends, Header, HTTPException
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SESSIONS: dict[str, int] = {}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_session(user_id: int) -> str:
    token = secrets.token_hex(24)
    SESSIONS[token] = user_id
    return token


def current_user(x_session_token: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    if not x_session_token or x_session_token not in SESSIONS:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = db.get(User, SESSIONS[x_session_token])
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user
