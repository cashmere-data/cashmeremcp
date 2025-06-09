import httpx
from fastapi import HTTPException

from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer_novalidate import BearerNoValidateAuthProvider
from fastmcp.server.dependencies import get_http_request


# Create a custom HTTP client factory that uses the current request's token
def create_authenticated_client():
    # Get the current request context to access the bearer token
    # request_context = get_request_context()
    request = get_http_request()
    bearer_token = request.headers.get("Authorization")
    if bearer_token is None:
        print("Unauthorized request: No bearer token found")
        raise HTTPException(status_code=401, detail="No bearer token found")

    # access_token = "d8db5e301f5d876c2ae775aa841503e08f7979385e07244fcf7c16883b00560a" #get_access_token()  # This is the token from the MCP client
    # print(f"Token: {token}")
    return httpx.AsyncClient(
        base_url="https://cashmere.io/api/v1", headers={"Authorization": bearer_token}
    )


auth = BearerNoValidateAuthProvider()

# Create MCP server with authentication
mcp = FastMCP(
    name="Cashmere MCP Server",
    auth_provider=auth,
)


@mcp.tool
async def search_publications(query: str):
    async with create_authenticated_client() as client:
        resp = await client.get(f"/semantic-search?q={query}")
        return resp.json()


print(f"search_publications registered (id(mcp)={id(mcp)})")


@mcp.tool
async def list_publications(
    limit: int | None = None,
    offset: int | None = None,
    collection_id: int | None = None,
):
    async with create_authenticated_client() as client:
        params = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if collection_id is not None:
            params["collection"] = collection_id
        resp = await client.get("/books", params=params)
        json = resp.json()
        truncated_response = {k: v for k, v in json.items() if k != "data"}
        if "items" in truncated_response:
            for item in truncated_response["items"]:
                item["data"].pop("nav", None)
        return truncated_response


print(f"list_publications registered (id(mcp)={id(mcp)})")


@mcp.tool
async def get_publication(publication_id: str):
    async with create_authenticated_client() as client:
        resp = await client.get(f"/book/{publication_id}")
        return resp.json()


print(f"get_publication registered (id(mcp)={id(mcp)})")


@mcp.tool
async def list_collections(limit: int | None = None, offset: int | None = None):
    async with create_authenticated_client() as client:
        params = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        resp = await client.get("/collections", params=params)
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
