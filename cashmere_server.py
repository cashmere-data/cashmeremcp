from typing import Final

import httpx
from fastapi import HTTPException
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer_novalidate import BearerNoValidateAuthProvider
from fastmcp.server.dependencies import get_http_request


class Settings(BaseSettings):
    CASHMERE_API_URL: str
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


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


# OAuth 2.0 Protected Resource Metadata (RFC 9728)
OAUTH_PR_METADATA = {
    "resource": "https://cashmere.io/api/v1/docs",
    "authorization_servers": ["https://cashmere.io"],
    "bearer_methods_supported": ["header"],
    "resource_name": "Cashmere API",
}

# Create MCP server with authentication
mcp = FastMCP(
    name="Cashmere MCP Server",
    instructions=(
        """This server exposes **read‑only** proxy tools that forward requests to the Cashmere public REST API.\n\n"
        "Cashmere provides access to intellectual property and publications that are protected by copyright "
        "or other legal restrictions with authorization from the copyright holder.\n\n"
        "All requests require a valid bearer token supplied by the caller; the server performs no further "
        "validation beyond passing that token through.\n\n"
        "Use the tools to search publications, list or fetch individual publications, and query collections."""
    ),
    tags={"cashmere", "publications", "collections", "search", "read"},
    auth=auth,
)


# Well‑known endpoint for OAuth 2.0 Protected Resource Metadata
@mcp.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
async def oauth_pr_metadata(_):
    return JSONResponse(OAUTH_PR_METADATA)


@mcp.tool(
    description=(
        "Search publications by semantic relevance. "
        "Returns a ranked list of books matching the provided "
        "natural‑language query."
    ),
    tags={"search", "publications", "read"},
    annotations={
        "title": "Search Publications",
        "readOnlyHint": True,
        "openWorldHint": True,
    },
)
async def search_publications(query: str):
    """Proxy for `GET /semantic-search` on the Cashmere API.

    Parameters
    ----------
    query : str
        Free‑form text used for semantic search.

    Returns
    -------
    dict
        JSON response from the Cashmere API containing ranked publications.
    """
    client, hdrs = create_authenticated_client()
    resp = await client.get("/semantic-search", params={"q": query}, headers=hdrs)
    return resp.json()


@mcp.tool(
    description=(
        "List publications visible to the caller with optional "
        "pagination and optional filtering by collection."
    ),
    tags={"publications", "list", "read"},
    annotations={
        "title": "List Publications",
        "readOnlyHint": True,
        "openWorldHint": True,
    },
)
async def list_publications(
    limit: int | None = None,
    offset: int | None = None,
    collection_id: int | None = None,
):
    """Proxy for `GET /books` on the Cashmere API.

    Parameters
    ----------
    limit : int | None
        Maximum number of items to return.
    offset : int | None
        Pagination offset.
    collection_id : int | None
        Restrict results to a specific collection ID.

    Returns
    -------
    dict
        A trimmed JSON response (with large `data.nav` fields removed).
    """
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


@mcp.tool(
    description=(
        "Fetch detailed metadata (and, where permitted, content) "
        "for a single publication identified by its UID."
    ),
    tags={"publication", "read"},
    annotations={
        "title": "Get Publication",
        "readOnlyHint": True,
        "openWorldHint": True,
    },
)
async def get_publication(publication_id: str):
    """Proxy for `GET /book/{publication_id}` on the Cashmere API.

    Parameters
    ----------
    publication_id : str
        Unique identifier of the publication to retrieve.

    Returns
    -------
    dict
        Full JSON payload for the specified publication.
    """
    client, hdrs = create_authenticated_client()
    resp = await client.get(f"/book/{publication_id}", headers=hdrs)
    return resp.json()


@mcp.tool(
    description=(
        "List collections available to the caller with optional pagination controls."
    ),
    tags={"collections", "list", "read"},
    annotations={
        "title": "List Collections",
        "readOnlyHint": True,
        "openWorldHint": True,
    },
)
async def list_collections(limit: int | None = None, offset: int | None = None):
    """Proxy for `GET /collections` on the Cashmere API.

    Parameters
    ----------
    limit : int | None
        Maximum number of collections to return.
    offset : int | None
        Pagination offset.

    Returns
    -------
    dict
        JSON response listing collections.
    """
    client, hdrs = create_authenticated_client()
    params = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    resp = await client.get("/collections", params=params, headers=hdrs)
    return resp.json()


# TODO: Implement get_collection
# @mcp.tool
# async def get_collection(collection_id: int):
#     async with create_authenticated_client() as client:
#         resp = await client.get(f"/collection/{collection_id}")
#         return resp.json()

# TODO: Implement get_usage_report
# @mcp.tool
# async def get_usage_report(userId: Union[str, None] = None):
#     async with create_authenticated_client() as client:
#         params = {}
#         if userId is not None:
#             params['userId'] = userId
#         resp = await client.get("/usage-report", params=params)
#         return resp.json()


# Add WWW-Authenticate hint for OAuth-protected resource metadata
class MetadataHint(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if response.status_code == 401:
            response.headers["WWW-Authenticate"] = (
                'Bearer resource="https://cashmere.io/api/v1/docs", '
                'authorization_uri="https://mcp.cashmere.io/.well-known/oauth-protected-resource"'
            )
        return response


# Attach the middleware to the underlying Starlette app
app = mcp.http_app()
app.add_middleware(MetadataHint)

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)
