from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, HttpUrl
import os
from dotenv import load_dotenv
import string
import random
from datetime import datetime
import certifi

# Load environment variables
load_dotenv()

app = FastAPI()

# Get allowed origins from environment variable or use default
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://url-shortner-lime-one.vercel.app/").split(",")

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection with SSL certificate
client = AsyncIOMotorClient(
    os.getenv("MONGODB_URI"),
    tlsCAFile=certifi.where()
)
db = client.url_shortener
urls = db.urls

class URLInput(BaseModel):
    original_url: HttpUrl

class URLResponse(BaseModel):
    short_url: str
    original_url: str
    created_at: datetime

@app.get("/")
async def root():
    """Root endpoint that returns API information."""
    return {
        "message": "Welcome to URL Shortener API",
        "endpoints": {
            "POST /shorten": "Create a short URL",
            "GET /{short_code}": "Redirect to original URL",
            "GET /stats/{short_code}": "Get URL statistics"
        }
    }

def generate_short_code(length: int = 6) -> str:
    """Generate a random short code for the URL."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

@app.post("/shorten", response_model=URLResponse)
async def shorten_url(url_input: URLInput):
    """Create a short URL for the given long URL."""
    # Check if URL already exists
    existing_url = await urls.find_one({"original_url": str(url_input.original_url)})
    if existing_url:
        return URLResponse(
            short_url=existing_url["short_code"],
            original_url=existing_url["original_url"],
            created_at=existing_url["created_at"]
        )

    # Generate new short code
    short_code = generate_short_code()
    while await urls.find_one({"short_code": short_code}):
        short_code = generate_short_code()

    # Create new URL entry
    url_data = {
        "short_code": short_code,
        "original_url": str(url_input.original_url),
        "created_at": datetime.utcnow(),
        "clicks": 0
    }
    
    await urls.insert_one(url_data)
    
    return URLResponse(
        short_url=short_code,
        original_url=str(url_input.original_url),
        created_at=url_data["created_at"]
    )

@app.get("/{short_code}")
async def redirect_to_url(short_code: str):
    """Redirect to the original URL when accessing the short URL."""
    url_data = await urls.find_one({"short_code": short_code})
    if not url_data:
        raise HTTPException(status_code=404, detail="URL not found")
    
    # Increment click count
    await urls.update_one(
        {"short_code": short_code},
        {"$inc": {"clicks": 1}}
    )
    
    return {"url": url_data["original_url"]}

@app.get("/stats/{short_code}")
async def get_url_stats(short_code: str):
    """Get statistics for a short URL."""
    url_data = await urls.find_one({"short_code": short_code})
    if not url_data:
        raise HTTPException(status_code=404, detail="URL not found")
    
    return {
        "short_code": url_data["short_code"],
        "original_url": url_data["original_url"],
        "created_at": url_data["created_at"],
        "clicks": url_data["clicks"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 