from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from client import helix
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Search Agent API")

def ensure_user_directories(user_id: str) -> None:
    """
    Ensure the directory structure exists for a user.
    Creates: uploads/<user_id>/processed/{links,docs,media}/
    
    Args:
        user_id: Unique identifier for the user
    """
    base_path = Path(__file__).parent / "uploads" / user_id / "processed"
    
    for subdirectory in ["links", "docs", "media"]:
        dir_path = base_path / subdirectory
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured directory exists: {dir_path}")

class SearchRequest(BaseModel):
    user_id: str
    query: str

class SearchResponse(BaseModel):
    user_id: str
    query: str
    result: str

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    try:
        logger.info(f"Received search request from user: {request.user_id}")
        ensure_user_directories(request.user_id)
        result = await helix(request.user_id, request.query)
        return SearchResponse(
            user_id=request.user_id,
            query=request.query,
            result=result
        )
    except Exception as e:
        logger.error(f"Error processing request for user {request.user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "good"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
