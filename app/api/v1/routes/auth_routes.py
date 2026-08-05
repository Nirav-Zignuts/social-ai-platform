"""
Authentication API routes.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.v1.schemas.auth_schema import (
    LoginRequest,
    RegisterRequest,
    UserResponse,
    VerifyEmailRequest,
)
from app.common.messages import SuccessMessage, ErrorMessage, AuthMessages, ErrorMessages
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.services.auth import (
    AuthService,
    AuthenticationError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
    UserAlreadyExistsError,
)
from app.services.email_service import EmailService
from app.middlewares.auth_middleware import require_auth
from app.common.responses import SuccessResponse

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)


@router.post(
    "/register",
    response_model=SuccessMessage,
    status_code=status.HTTP_201_CREATED,
    summary="User Registration",
    description="Register a new user with email and password",
)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def register(
    request: Request,
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Register a new user.

    **Request Body:**
    - `full_name`: User's full name (2-255 characters)
    - `email`: User's email address
    - `password`: User's password (8-128 characters)

    **Response:**
    - Returns a success message and sends a verification email

    **Errors:**
    - 400: Email already exists or validation error
    - 429: Too many requests
    - 500: Server error
    """
    try:
        auth_service = AuthService(db)
        result = auth_service.register_user(payload)

        email_service = EmailService()
        verification_link = email_service.build_verification_link(
            result["activation_token"]
        )
        background_tasks.add_task(
            email_service.send_verification_email_safe,
            recipient=payload.email,
            full_name=payload.full_name,
            verification_link=verification_link,
        )

        return SuccessMessage(
            message=AuthMessages.EMAIL_VERIFICATION_SENT,
            data={
                "user": result["user"],
            },
            code=status.HTTP_201_CREATED,
        )
    except UserAlreadyExistsError as e:
        return ErrorMessage(
            message=str(e),
            code=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.post(
    "/login",
    response_model=SuccessMessage | ErrorMessage,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticate user with email and password",
)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(
    request: Request,
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Login user with email and password.

    **Request Body:**
    - `email`: User's email address
    - `password`: User's password

    **Response:**
    - Returns user data along with access and refresh tokens

    **Errors:**
    - 401: Invalid credentials
    - 429: Too many requests
    - 500: Server error
    """
    try:
        auth_service = AuthService(db)
        result = auth_service.login_user(payload)

        return SuccessMessage(
            message=AuthMessages.LOGIN_SUCCESS,
            data={
                "user": result["user"],
                "tokens": {
                    "access_token": result["access_token"],
                    "refresh_token": result["refresh_token"],
                    "token_type": result["token_type"],
                },
            },
            code=status.HTTP_200_OK,
        )
    except InvalidCredentialsError as e:
        return ErrorMessage(
            message=str(e),
            code=status.HTTP_401_UNAUTHORIZED,
        )
    except AuthenticationError as e:
        return ErrorMessage(
            message=str(e),
            code=status.HTTP_401_UNAUTHORIZED,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.post(
    "/verify-email",
    response_model=SuccessMessage | ErrorMessage,
    status_code=status.HTTP_200_OK,
    summary="Verify Email",
    description="Verify a user email address using the activation token",
)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def verify_email(
    request: Request,
    payload: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    """
    Verify the user email with the activation token.

    **Request Body:**
    - `token`: Activation token sent by email

    **Response:**
    - Returns a success message when email is verified

    **Errors:**
    - 401: Invalid or expired activation token
    - 429: Too many requests
    - 500: Server error
    """
    try:
        auth_service = AuthService(db)
        auth_service.verify_email(payload.token)

        return SuccessMessage(
            message=AuthMessages.EMAIL_VERIFIED,
            code=status.HTTP_200_OK,
        )
    except TokenExpiredError as e:
        return ErrorMessage(
            message=str(e),
            code=status.HTTP_401_UNAUTHORIZED,
        )
    except InvalidTokenError as e:
        return ErrorMessage(
            message=str(e),
            code=status.HTTP_401_UNAUTHORIZED,
        )
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.post(
    "/refresh",
    response_model=SuccessMessage | ErrorMessage,
    status_code=status.HTTP_200_OK,
    summary="Refresh Access Token",
    description="Generate new access token using refresh token",
)
@limiter.limit(settings.RATE_LIMIT_AUTH_REFRESH)
async def refresh_token(
    request: Request,
    refresh_token: str,
    db: Session = Depends(get_db),
):
    """
    Generate a new access token using refresh token.

    **Query Parameters:**
    - `refresh_token`: Valid refresh token

    **Response:**
    - Returns new access token

    **Errors:**
    - 401: Invalid or expired refresh token
    - 429: Too many requests
    - 500: Server error
    """
    try:
        auth_service = AuthService(db)
        result = auth_service.refresh_access_token(refresh_token)

        return SuccessMessage(
            message=AuthMessages.TOKEN_REFRESHED,
            data={
                "access_token": result["access_token"],
                "token_type": result["token_type"],
            },
            code=status.HTTP_200_OK,
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=ErrorMessage(
                message=ErrorMessages.INVALID_TOKEN,
                code=status.HTTP_401_UNAUTHORIZED,
                details=str(e),
            ).model_dump(),
        )


@router.get("/me", response_model=SuccessResponse, status_code=status.HTTP_200_OK)
async def get_current_user(
    request: Request,
    current_user: UserResponse = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """
    Get the currently authenticated user.

    **Response:**
    - Returns the current user's information

    **Errors:**
    - 401: Unauthorized access
    - 429: Too many requests
    """
    auth_service = AuthService(db)
    return auth_service.get_user_by_id(current_user.get("user_id"))


@router.post(
    "/logout",
    response_model=SuccessMessage | ErrorMessage,
    status_code=status.HTTP_200_OK,
    summary="User Logout",
    description="Invalidate the current access token and logout the user",
)
async def logout(
    request: Request,
    current_user: UserResponse = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """
    Logout the currently authenticated user.

    **Response:**
    - Returns a success message upon successful logout

    **Errors:**
    - 401: Unauthorized access
    - 429: Too many requests
    """
    try:
        auth_service = AuthService(db)
        auth_service.logout_user(request, current_user.get("user_id"))

        return SuccessMessage(
            message=AuthMessages.LOGOUT_SUCCESS,
            code=status.HTTP_200_OK,
        )
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )
