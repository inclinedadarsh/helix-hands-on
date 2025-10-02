from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
# from cerebras_client import process_user_request
from openrouter_client import process_user_request
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Search Agent API")

class SearchRequest(BaseModel):
    user_id: str
    query: str

class SearchResponse(BaseModel):
    user_id: str
    query: str
    result: str

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Handle a search request for a specific user.
    """
    try:
        logger.info(f"Received search request from user: {request.user_id}")
        result = await process_user_request(request.user_id, request.query)
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
