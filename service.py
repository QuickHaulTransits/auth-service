import logging
import random
import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
import asyncio

from shared.config import settings
from shared.database import get_redis
from shared.security import hash_password, verify_password, create_access_token
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Fallback in-memory storage if DB is down
MOCK_USERS = {}


async def send_otp_email(to_email: str, otp: str) -> bool:
    """Send OTP email (non-blocking, fire and forget)"""
    if not settings.smtp_enabled:
        logger.info(f"\n[DEV MODE] OTP for {to_email}: {otp}\n")
        return True
    
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        msg['To'] = to_email
        msg['Subject'] = 'Your OTP for QuickHaul Registration'
        body = f"Your OTP for QuickHaul registration is: {otp}\n\nExpires in 10 minutes."
        msg.attach(MIMEText(body, 'plain'))

        # Determine which SMTP method to use based on settings
        if settings.smtp_use_tls and settings.smtp_port == 465:
            # Port 465: Use SMTP_SSL
            with smtplib.SMTP_SSL(
                host=settings.smtp_host,
                port=settings.smtp_port,
                timeout=15
            ) as server:
                if settings.smtp_username:
                    server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(msg)
        else:
            # Port 1025 or 587: Use plain SMTP with optional STARTTLS
            with smtplib.SMTP(
                host=settings.smtp_host,
                port=settings.smtp_port,
                timeout=15
            ) as server:
                if settings.smtp_use_starttls:
                    server.starttls()
                
                # Only login if credentials are provided (local SMTP servers may not need it)
                if settings.smtp_username and settings.smtp_password:
                    server.login(settings.smtp_username, settings.smtp_password)
                
                server.send_message(msg)
        
        logger.info(f"OTP sent successfully to {to_email}")
        return True
    except socket.timeout:
        logger.error(f"SMTP Timeout for {to_email} (timeout after 15s)")
        logger.info(f"\n[FALLBACK] Email timeout. OTP for {to_email}: {otp}\n")
        return False
    except Exception as e:
        logger.error(f"SMTP Error for {to_email}: {str(e)}")
        logger.info(f"\n[FALLBACK] Email failed. OTP for {to_email}: {otp}\n")
        return False


async def generate_and_send_otp(email: str):
    """Generate OTP, store in Redis, and send email synchronously for verification"""
    otp = str(random.randint(100000, 999999))
    redis = get_redis()
    
    # Store OTP in Redis immediately
    await redis.setex(f"otp:{email.lower()}", 600, otp)
    
    # Send email and wait for result
    success = await send_otp_email(email, otp)
    
    return otp, success


async def verify_otp(email: str, provided_otp: str) -> bool:
    redis = get_redis()
    key = f"otp:{email.lower()}"
    stored = await redis.get(key)
    logger.info(f"OTP CHECK: email={email}, key={key}, stored={stored}, provided={provided_otp}")
    if not stored: 
        logger.warning(f"No OTP found in Redis for {email}")
        return False
    valid = str(stored) == str(provided_otp)
    if valid: 
        await redis.delete(key)
        logger.info(f"OTP Verified successfully for {email}")
    else:
        logger.warning(f"OTP Mismatch for {email}: expected {stored}, got {provided_otp}")
    return valid


async def register_user(payload, db: AsyncIOMotorDatabase):
    user_email = payload.email.lower()
    
    # Primary: MongoDB
    if db is not None:
        users = db["users"]
        if await users.find_one({"email": user_email}):
            raise HTTPException(status_code=400, detail="Email already in use")
        doc = {
            "name": payload.name,
            "email": user_email,
            "phone": payload.phone,
            "password_hash": hash_password(payload.password),
            "created_at": datetime.now(timezone.utc),
        }
        result = await users.insert_one(doc)
        user_id = str(result.inserted_id)
    else:
        # Fallback: In-memory (lost on restart)
        logger.warning(f"MongoDB not connected. Using in-memory fallback for {user_email}")
        if user_email in MOCK_USERS:
            raise HTTPException(status_code=400, detail="Email already in use (mock)")
        user_id = f"mock_{len(MOCK_USERS) + 1}"
        MOCK_USERS[user_email] = {
            "id": user_id,
            "name": payload.name,
            "email": user_email,
            "password_hash": hash_password(payload.password)
        }

    token = create_access_token(user_id)
    return {"access_token": token, "token_type": "bearer", "user_id": user_id, "email": user_email}


async def login_user(payload, db: AsyncIOMotorDatabase):
    user_email = payload.email.lower()
    
    # Primary: MongoDB
    if db is not None:
        user = await db["users"].find_one({"email": user_email})
    else:
        # Fallback: In-memory
        user = MOCK_USERS.get(user_email)
        
    if not user or not verify_password(payload.password, user.get("password_hash") or user.get("password")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    user_id = str(user.get("_id") or user.get("id"))
    token = create_access_token(user_id)
    return {"access_token": token, "token_type": "bearer", "user_id": user_id, "email": user["email"]}
