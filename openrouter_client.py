import json, os, logging
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import mcp.types as mcp_types
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

MODEL = "x-ai/grok-code-fast-1"

HELIX_SYSTEM_PROMPT = os.getenv("HELIX_SYSTEM_PROMPT")

def mcp_tool_to_openrouter(t: mcp_types.Tool) -> dict:
    """Convert MCP tool definition to OpenRouter/OpenAI function format."""
    return {
        "type": "function",
        "function": {
            "name": t.name,
            "description": t.description or "",
            "parameters": t.inputSchema or {"type": "object"},
        },
    }

async def process_user_request(user_id: str, user_query: str) -> str:
    """
    Process a single user request by spawning a dedicated MCP server instance.
    
    Args:
        user_id: Unique identifier for the user
        user_query: The user's search query
        
    Returns:
        The agent's final response
    """
    logger.info(f"Processing request for user: {user_id}")
    
    server = StdioServerParameters(
        command="python",
        args=["mcp_server.py"],
        env={"USER_ID": user_id}
    )
    
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            logger.info(f"Agent started with system prompt: {HELIX_SYSTEM_PROMPT}")

            tools_resp = await session.list_tools()
            logger.info(f"Available tools: {[t.name for t in tools_resp.tools]}")
            tools_for_model = [mcp_tool_to_openrouter(t) for t in tools_resp.tools]

            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.environ.get("OPENROUTER_API_KEY")
            )

            messages = [
                {"role": "system", "content": HELIX_SYSTEM_PROMPT},
                {"role": "user", "content": user_query},
            ]
            
            logger.info(f"User {user_id} query: {user_query}")

            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools_for_model,
            )

            msg = response.choices[0].message
            logger.info(f"agent's response: {msg.model_dump()}")

            while msg.tool_calls:
                logger.info(f"Tool calls requested: {len(msg.tool_calls)}")
                messages.append(msg.model_dump())

                for call in msg.tool_calls:
                    name = call.function.name
                    args = json.loads(call.function.arguments or "{}")
                    
                    logger.info(f"Executing tool: {name} with args: {args}")

                    result = await session.call_tool(name, args)

                    payload = None
                    if getattr(result, "structuredContent", None):
                        payload = json.dumps(result.structuredContent)
                    else:
                        parts = []
                        for c in result.content:
                            if isinstance(c, mcp_types.TextContent):
                                parts.append(c.text)
                        payload = "\n".join(parts) if parts else ""
                    
                    logger.info(f"Tool {name} result: {payload}")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": payload,
                    })

                follow = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                )
                msg = follow.choices[0].message
                logger.info(f"agent's response: {msg.model_dump()}")

            logger.info(f"Final agent's response for user {user_id}: {msg.content}")
            return msg.content