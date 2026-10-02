"""HTTP surface of the identity context: /v1/auth."""

from fastapi import APIRouter, Request, Response

from sonari_core.identity.schemas import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from sonari_core.identity.service import AuthService, Session
from sonari_core.shared.errors import AppError
from sonari_core.shared.message_keys import MessageKey

REFRESH_COOKIE = "refresh_token"
COOKIE_PATH = "/v1/auth"  # the browser sends the refresh token to these routes only

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _service(request: Request) -> AuthService:
    service: AuthService = request.app.state.auth
    return service


def _client_ip(request: Request) -> str:
    # Behind a proxy this is the proxy's address unless uvicorn runs with --proxy-headers
    # and --forwarded-allow-ips, which P35/P72 must set.
    return request.client.host if request.client else "unknown"


def _respond(request: Request, response: Response, session: Session) -> AuthResponse:
    response.set_cookie(
        REFRESH_COOKIE,
        session.refresh_token,
        max_age=session.refresh_max_age_s,
        path=COOKIE_PATH,
        httponly=True,
        secure=request.app.state.settings.auth_cookie_secure,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"  # the body carries an access token
    return AuthResponse(
        user=UserResponse(id=session.user.id, email=session.user.email),
        access_token=session.access_token,
        expires_in=session.expires_in,
    )


@router.post("/register", status_code=201, response_model=AuthResponse)
async def register(body: RegisterRequest, request: Request, response: Response) -> AuthResponse:
    session = await _service(request).register(
        body.email, body.password, body.turnstile_token, _client_ip(request)
    )
    return _respond(request, response, session)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, request: Request, response: Response) -> AuthResponse:
    session = await _service(request).login(body.email, body.password, _client_ip(request))
    return _respond(request, response, session)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(request: Request, response: Response) -> AuthResponse:
    session = await _service(request).refresh(request.cookies.get(REFRESH_COOKIE))
    return _respond(request, response, session)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response) -> None:
    await _service(request).logout(request.cookies.get(REFRESH_COOKIE))
    response.delete_cookie(
        REFRESH_COOKIE,
        path=COOKIE_PATH,
        httponly=True,
        secure=request.app.state.settings.auth_cookie_secure,
        samesite="lax",
    )


@router.get("/me", response_model=UserResponse)
async def me(request: Request) -> UserResponse:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AppError(
            401,
            "token_missing",
            MessageKey.AUTH_TOKEN_INVALID,
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await _service(request).authenticate(token)
    return UserResponse(id=user.id, email=user.email)
