"""
Basic Auth Service for Transport Booking System
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis
import json
from datetime import timedelta
import uuid
import httpx

OTP_SERVICE_URL = "http://localhost:8005"

app = FastAPI(title="Auth Service", version="2.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis connection for session storage
redis_client = redis.Redis(host='localhost', port=6379, db=2, decode_responses=True)

# Session TTL (24 hours)
SESSION_TTL = timedelta(hours=24)

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    otp: str
    phone: str = ""

class LoginResponse(BaseModel):
    token: str
    user: dict

# Mock user database (in production, use MongoDB)
MOCK_USERS = {
    "admin@quickhaul.com": {
        "id": "user_1",
        "name": "Admin User",
        "email": "admin@quickhaul.com",
        "password": "admin123",  # In production, use hashed passwords
        "role": "admin"
    },
    "user@quickhaul.com": {
        "id": "user_2", 
        "name": "Test User",
        "email": "user@quickhaul.com",
        "password": "user123",
        "role": "customer"
    }
}

@app.post("/auth/login")
async def login(login_data: LoginRequest):
    """Login endpoint"""
    email = login_data.email
    password = login_data.password
    
    # Check if user exists and password matches
    if email not in MOCK_USERS or MOCK_USERS[email]["password"] != password:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Generate session token
    session_token = str(uuid.uuid4())
    
    # Store session in Redis
    session_data = {
        "user_id": MOCK_USERS[email]["id"],
        "email": email,
        "name": MOCK_USERS[email]["name"],
        "role": MOCK_USERS[email]["role"],
        "created_at": str(timedelta(hours=0))
    }
    
    redis_client.setex(f"session:{session_token}", SESSION_TTL, json.dumps(session_data))
    
    # Return user data without password
    user_data = {
        "id": MOCK_USERS[email]["id"],
        "name": MOCK_USERS[email]["name"],
        "email": email,
        "role": MOCK_USERS[email]["role"]
    }
    
    return LoginResponse(token=session_token, user=user_data)

@app.post("/auth/logout")
async def logout(token: str):
    """Logout endpoint"""
    if token:
        redis_client.delete(f"session:{token}")
    return {"message": "Logged out successfully"}

@app.get("/auth/me")
async def get_current_user(token: str):
    """Get current user from token"""
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    
    session_data = redis_client.get(f"session:{token}")
    if not session_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return json.loads(session_data)

@app.post("/auth/register")
async def register(request: RegisterRequest):
    """Register new user with OTP verification"""
    if request.email in MOCK_USERS:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Verify OTP
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OTP_SERVICE_URL}/verify",
                json={"email": request.email, "otp": request.otp},
                timeout=5.0
            )
            if response.status_code != 200:
                result = response.json()
                raise HTTPException(status_code=400, detail=result.get("detail", "OTP verification failed"))
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="OTP service unavailable")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OTP verification failed: {str(e)}")
    
    # Create new user
    new_user = {
        "id": f"user_{len(MOCK_USERS) + 1}",
        "name": request.name,
        "email": request.email,
        "password": request.password,  # In production, hash this
        "role": "customer"
    }
    
    MOCK_USERS[request.email] = new_user
    
    # Generate session token for auto-login
    session_token = str(uuid.uuid4())
    session_data = {
        "user_id": new_user["id"],
        "email": request.email,
        "name": request.name,
        "role": "customer",
        "created_at": str(timedelta(hours=0))
    }
    redis_client.setex(f"session:{session_token}", SESSION_TTL, json.dumps(session_data))
    
    return {
        "message": "User registered successfully",
        "user_id": new_user["id"],
        "token": session_token,
        "user": {
            "id": new_user["id"],
            "name": request.name,
            "email": request.email,
            "role": "customer"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        redis_client.ping()
        return {"status": "healthy", "redis": "connected"}
    except:
        return {"status": "unhealthy", "redis": "disconnected"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
