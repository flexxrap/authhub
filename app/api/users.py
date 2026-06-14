from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.schemas import UserOut
from app.db.models import User

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def read_me(user: User = Depends(get_current_user)):
    return user
