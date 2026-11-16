from datetime import datetime, timedelta
from typing import Any, Union, Dict
import base64
import json
import hmac
import hashlib
import secrets

from app.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


class FallbackJWTError(Exception):
    pass


# Check if passlib is available
try:
    from passlib.context import CryptContext
    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    _has_passlib = True
except ImportError:
    _has_passlib = False

# Check if python-jose is available
try:
    from jose import jwt as _jose_jwt, JWTError as _JoseJWTError
    _has_jose = True
    JWTError = _JoseJWTError
except ImportError:
    _has_jose = False
    JWTError = FallbackJWTError


def _b64_url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')


def _b64_url_decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += '=' * padding
    return base64.urlsafe_b64decode(data.encode('utf-8'))


class StandardLibJWT:
    @staticmethod
    def encode(claims: Dict[str, Any], key: str, algorithm: str = "HS256") -> str:
        header = {"alg": algorithm, "typ": "JWT"}
        # Convert datetime objects to timestamps
        serializable_claims = {}
        for k, v in claims.items():
            if isinstance(v, datetime):
                serializable_claims[k] = int(v.timestamp())
            else:
                serializable_claims[k] = v
        
        h_str = _b64_url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
        p_str = _b64_url_encode(json.dumps(serializable_claims, separators=(',', ':')).encode('utf-8'))
        signing_input = f"{h_str}.{p_str}".encode('utf-8')
        
        sig = hmac.new(key.encode('utf-8'), signing_input, hashlib.sha256).digest()
        sig_str = _b64_url_encode(sig)
        return f"{h_str}.{p_str}.{sig_str}"

    @staticmethod
    def decode(token: str, key: str, algorithms: list = None) -> Dict[str, Any]:
        parts = token.split('.')
        if len(parts) != 3:
            raise FallbackJWTError("Invalid token segments")
        
        signing_input = f"{parts[0]}.{parts[1]}".encode('utf-8')
        expected_sig = hmac.new(key.encode('utf-8'), signing_input, hashlib.sha256).digest()
        expected_sig_str = _b64_url_encode(expected_sig)
        
        if not hmac.compare_digest(expected_sig_str, parts[2]):
            raise FallbackJWTError("Signature verification failed")
            
        try:
            payload = json.loads(_b64_url_decode(parts[1]).decode('utf-8'))
        except Exception as e:
            raise FallbackJWTError(f"Malformed token payload: {e}")
            
        if "exp" in payload:
            if datetime.utcnow().timestamp() > payload["exp"]:
                raise FallbackJWTError("Token has expired")
                
        return payload


# Export unified jwt handler
if _has_jose:
    jwt = _jose_jwt
else:
    jwt = StandardLibJWT


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if hashed_password.startswith("sha256$"):
        parts = hashed_password.split("$")
        if len(parts) >= 3:
            salt, h = parts[1], parts[2]
            computed = hashlib.sha256((salt + plain_password).encode("utf-8")).hexdigest()
            return hmac.compare_digest(computed, h)
        return False
    if _has_passlib:
        try:
            return _pwd_context.verify(plain_password, hashed_password)
        except Exception:
            pass
    return plain_password == hashed_password


def get_password_hash(password: str) -> str:
    if _has_passlib:
        try:
            return _pwd_context.hash(password)
        except Exception:
            pass
    salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"sha256${salt}${h}"


def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
