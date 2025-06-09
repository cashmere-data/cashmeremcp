from typing import Final

import httpx
from fastapi import HTTPException
from pydantic_settings import BaseSettings, SettingsConfigDict

from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer_novalidate import BearerNoValidateAuthProvider
from fastmcp.server.dependencies import get_http_request


class Settings(BaseSettings):
    CASHMERE_API_KEY: str
    CASHMERE_MCP_SERVER_URL: str
    CASHMERE_API_URL: str
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")


settings = Settings()

# Use one shared client for *all* requests.
HTTP_TIMEOUT: Final = httpx.Timeout(30.0, connect=5.0, read=30.0)
HTTP_LIMITS: Final = httpx.Limits(
    max_connections=2048,  # hard cap
    max_keepalive_connections=512,  # pool size
)
_shared_client: httpx.AsyncClient | None = None


def _get_shared_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            base_url=settings.CASHMERE_API_URL,
            timeout=HTTP_TIMEOUT,
            limits=HTTP_LIMITS,
            # Don’t set Authorization here; we’ll inject it per-request.
        )
    return _shared_client


def create_authenticated_client():
    """
    Return the _shared_ AsyncClient plus a header dict containing the caller’s bearer
    token.  Tools pass that header when they invoke .get/.post.
    """
    request = get_http_request()
    bearer = request.headers.get("Authorization")
    if bearer is None:
        raise HTTPException(status_code=401, detail="No bearer token found")
    return _get_shared_client(), {"Authorization": bearer}


auth = BearerNoValidateAuthProvider()

# Create MCP server with authentication
mcp = FastMCP(
    name="Cashmere MCP Server",
    auth_provider=auth,
)


@mcp.tool
async def search_publications(query: str):
    client, hdrs = create_authenticated_client()
    resp = await client.get("/semantic-search", params={"q": query}, headers=hdrs)
    return resp.json()


print(f"search_publications registered (id(mcp)={id(mcp)})")


@mcp.tool
async def list_publications(
    limit: int | None = None,
    offset: int | None = None,
    collection_id: int | None = None,
):
    client, hdrs = create_authenticated_client()
    params = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
        if collection_id is not None:
            params["collection"] = collection_id
        resp = await client.get("/books", params=params, headers=hdrs)
        json = resp.json()
        truncated_response = {k: v for k, v in json.items() if k != "data"}
        if "items" in truncated_response:
            for item in truncated_response["items"]:
                item["data"].pop("nav", None)
        return truncated_response


print(f"list_publications registered (id(mcp)={id(mcp)})")


@mcp.tool
async def get_publication(publication_id: str):
    client, hdrs = create_authenticated_client()
    resp = await client.get(f"/book/{publication_id}", headers=hdrs)
    return resp.json()


print(f"get_publication registered (id(mcp)={id(mcp)})")


@mcp.tool
async def list_collections(limit: int | None = None, offset: int | None = None):
    client, hdrs = create_authenticated_client()
    params = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    resp = await client.get("/collections", params=params, headers=hdrs)
    return resp.json()


print(f"list_collections registered (id(mcp)={id(mcp)})")

# TODO: Implement get_collection
# @mcp.tool
# async def get_collection(collection_id: int):
#     async with create_authenticated_client() as client:
#         resp = await client.get(f"/collection/{collection_id}")
#         return resp.json()
# print(f"get_collection registered (id(mcp)={id(mcp)})")

# TODO: Implement get_usage_report
# @mcp.tool
# async def get_usage_report(userId: Union[str, None] = None):
#     async with create_authenticated_client() as client:
#         params = {}
#         if userId is not None:
#             params['userId'] = userId
#         resp = await client.get("/usage-report", params=params)
#         return resp.json()
# print(f"get_usage_report registered (id(mcp)={id(mcp)})")

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)
