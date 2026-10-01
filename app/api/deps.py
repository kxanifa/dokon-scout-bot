
from fastapi import Depends, Header, HTTPException, status

from app.services.auth import AuthError, authenticate_admin_user
from app.services.sheets import Agent


async def get_current_admin(
    authorization: str | None = Header(None),
    x_debug_user_id: int | None = Header(None),
) -> Agent:
    try:
        agent = await authenticate_admin_user(auth_header=authorization, debug_user_id=x_debug_user_id)
        return agent
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": str(e)},
        ) from e


async def get_current_superadmin(
    admin: Agent = Depends(get_current_admin),
) -> Agent:
    if admin.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": "Faqat superadmin amalga oshirishi mumkin."},
        )
    return admin
