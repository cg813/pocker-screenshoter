import jwt

from fastapi import HTTPException, status, Cookie

from apps.config import settings


def check_token(token: str = Cookie(None)):
    # TODO we need to check also timestamp
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    try:
        jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.exceptions.InvalidTokenError:
        raise credentials_exception
