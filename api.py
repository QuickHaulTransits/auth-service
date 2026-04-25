from typing import List, Optional
import logging
from pydantic import BaseModel, EmailStr, Field, field_validator
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.database import get_db
from shared.config import settings
from .schemas import UserBase, RegisterRequest, LoginRequest, AuthResponse, SendOtpRequest
from .service import generate_and_send_otp, verify_otp, register_user, login_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/send-otp")
async def send_otp(payload: SendOtpRequest):
    try:
        otp, email_was_sent = await generate_and_send_otp(payload.email)
        
        logger.info(f"OTP generated for {payload.email}: {otp} | Email sent: {email_was_sent}")
        
        return {
            "message": "OTP generated successfully" if email_was_sent else "OTP generated (Email failed)",
            "otp": otp,
            "email_sent": email_was_sent
        }
    except Exception as e:
        logger.error(f"OTP send failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send OTP: {str(e)}")


@router.post("/register", response_model=AuthResponse)
async def register(payload: RegisterRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    logger.info(f"Registration attempt: email={payload.email}, name={payload.name}, phone={payload.phone}")
    is_valid = await verify_otp(payload.email, payload.otp)
    if not is_valid:
        logger.error(f"OTP verification failed for {payload.email} with OTP {payload.otp}")
        raise HTTPException(status_code=400, detail="Invalid or expired OTP. Please request a new OTP.")
    try:
        result = await register_user(payload, db)
        logger.info(f"Registration successful for {payload.email}")
        return result
    except Exception as e:
        import traceback
        logger.error(f"Registration error: {str(e)}")
        print("\n--- REGISTRATION ERROR STACK TRACE ---")
        traceback.print_exc()
        print("---------------------------------------\n")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    return await login_user(payload, db)


@router.get("/users")
async def list_users(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Admin endpoint - list all users (for inter-service communication)"""
    users = []
    async for user in db["users"].find():
        user["id"] = str(user.pop("_id"))
        users.append(user)
    return users
