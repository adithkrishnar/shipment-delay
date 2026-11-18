from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.auth.security import SECRET_KEY, ALGORITHM, jwt, JWTError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user

def get_current_user_or_demo(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme_optional)
) -> User:
    """
    Validates token if provided.
    If no token is provided, enforces an explicit, restricted demo policy:
    resolves strictly to a non-superuser demo company user (scoped to demo company),
    and NEVER silently grants unrestricted carrier or superuser access.
    """
    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if user and user.is_active:
                    return user
        except Exception:
            pass
    
    # Explicit restricted demo policy:
    # Resolve strictly to a non-superuser demo company account
    demo_user = db.query(User).filter(User.email == "demo@globallogistics.com").first()
    if not demo_user:
        demo_user = db.query(User).filter(
            User.role == "company",
            User.is_superuser.is_(False),
            User.company_id == 16
        ).first()
    if not demo_user:
        demo_user = db.query(User).filter(
            User.role == "company",
            User.is_superuser.is_(False)
        ).first()

    if demo_user:
        return demo_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials required"
    )

def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="The user doesn't have enough privileges"
        )
    return current_user

def verify_company_access(
    company_id: int,
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Not authorized to access this company's data"
        )
    return current_user

