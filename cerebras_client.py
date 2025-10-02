import asyncio, json, os, logging
from cerebras.cloud.sdk import Cerebras
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

# MODEL = "llama-4-scout-17b-16e-instruct"  
# MODEL = "gpt-oss-120b"
# MODEL = "qwen-3-32b"
# MODEL = "qwen-3-235b-a22b-thinking-2507"
MODEL = "qwen-3-coder-480b"
# MODEL = "qwen-3-235b-a22b-instruct-2507"

HELIX_SYSTEM_PROMPT = """You are Helix, a specialized search agent designed to find and retrieve information from files and directories.

CRITICAL RULES:
1. You MUST ALWAYS use your tools to search for information. NEVER answer questions from your own knowledge.
2. ONLY provide answers based on information found in the files you've searched.
3. If you cannot find relevant information in the files, clearly state "I could not find information about [query] in the available files."
4. Always cite which file(s) you found the information in.
5. If a query seems answerable from general knowledge, you MUST still search the files first.

Your workflow for every query:
1. Analyze the user's query to identify key search terms
2. Use list_file to understand the available files and structure
3. Use grep with relevant keywords to locate files containing the information
4. Use read_file to examine the content of relevant files
5. Synthesize the information found in the files to answer the query
6. Cite your sources (file names and locations)

Remember: You are a FILE SEARCH AGENT, not a general knowledge assistant. Always search first, never guess or use pre-trained knowledge."""

def mcp_tool_to_cerebras(t: mcp_types.Tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": t.name,
            "description": t.description or "",
            "strict": True,
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

            tools_resp = await session.list_tools()
            logger.info(f"Available tools: {[t.name for t in tools_resp.tools]}")
            tools_for_model = [mcp_tool_to_cerebras(t) for t in tools_resp.tools]

            client = Cerebras(api_key=os.environ["CEREBRAS_API_KEY"])

            messages = [
                {"role": "system", "content": HELIX_SYSTEM_PROMPT},
                {"role": "user", "content": user_query},
            ]
            
            logger.info(f"User {user_id} query: {user_query}")

            if MODEL == "llama-4-scout-17b-16e-instruct":
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=tools_for_model,
                    parallel_tool_calls=False,
                )
            else:
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

