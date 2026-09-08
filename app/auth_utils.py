import base64
import hashlib
import hmac
import time
import boto3
import requests
from jose import jwt, JWTError
from config import Config

_cognito = boto3.client("cognito-idp", region_name=Config.AWS_REGION)

_jwks_cache = {"keys": None, "fetched_at": 0}


def _get_secret_hash(identity):
    message = identity + Config.COGNITO_CLIENT_ID
    dig = hmac.new(
        Config.COGNITO_CLIENT_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(dig).decode()


def sign_up(display_name, password, email):
    """Cognito's identity (Username) is the EMAIL. display_name is stored
    as a separate 'name' attribute, purely for showing in the UI."""
    return _cognito.sign_up(
        ClientId=Config.COGNITO_CLIENT_ID,
        SecretHash=_get_secret_hash(email),
        Username=email,
        Password=password,
        UserAttributes=[
            {"Name": "email", "Value": email},
            {"Name": "name", "Value": display_name},
        ],
    )


def confirm_sign_up(email, code):
    return _cognito.confirm_sign_up(
        ClientId=Config.COGNITO_CLIENT_ID,
        SecretHash=_get_secret_hash(email),
        Username=email,
        ConfirmationCode=code,
    )


def login(email, password):
    """Returns the auth result dict (IdToken, AccessToken, RefreshToken) or raises."""
    response = _cognito.initiate_auth(
        ClientId=Config.COGNITO_CLIENT_ID,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={
            "USERNAME": email,
            "PASSWORD": password,
            "SECRET_HASH": _get_secret_hash(email),
        },
    )
    return response["AuthenticationResult"]


def _get_jwks():
    """Cache Cognito's public keys for an hour to avoid fetching on every request."""
    now = time.time()
    if _jwks_cache["keys"] is None or (now - _jwks_cache["fetched_at"]) > 3600:
        url = (
            f"https://cognito-idp.{Config.AWS_REGION}.amazonaws.com/"
            f"{Config.COGNITO_USER_POOL_ID}/.well-known/jwks.json"
        )
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        _jwks_cache["keys"] = resp.json()["keys"]
        _jwks_cache["fetched_at"] = now
    return _jwks_cache["keys"]


def verify_token(token):
    """Verifies a Cognito ID token's signature and claims. Returns claims dict or None."""
    try:
        headers = jwt.get_unverified_header(token)
        kid = headers["kid"]
        keys = _get_jwks()
        key = next((k for k in keys if k["kid"] == kid), None)
        if key is None:
            return None

        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=Config.COGNITO_CLIENT_ID,
            issuer=(
                f"https://cognito-idp.{Config.AWS_REGION}.amazonaws.com/"
                f"{Config.COGNITO_USER_POOL_ID}"
            ),
        )
        return claims
    except JWTError:
        return None


def is_admin(claims):
    groups = claims.get("cognito:groups", [])
    return "Admins" in groups
