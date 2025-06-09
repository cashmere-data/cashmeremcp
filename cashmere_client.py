import asyncio
import json as pyjson

from mcp.types import TextContent
from pydantic_settings import BaseSettings, SettingsConfigDict

from cashmere_types import (
    Collection,
    CollectionsResponse,
    Publication,
    PublicationsResponse,
    SearchPublicationsResponse,
)
from fastmcp import Client
from fastmcp.client.auth import BearerAuth


def parse_json_content(content):
    """
    Convert TextContent, str, bytes, bytearray, or list of these to parsed JSON.
    Raises TypeError for unsupported types.
    """

    if isinstance(content, TextContent):
        return pyjson.loads(content.text)
    elif isinstance(content, str | bytes | bytearray):
        return pyjson.loads(content)
    elif isinstance(content, list):
        return [parse_json_content(item) for item in content]
    else:
        raise TypeError(f"Unsupported content type: {type(content)}")


class Settings(BaseSettings):
    CASHMERE_API_KEY: str
    CASHMERE_MCP_SERVER_URL: str
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")


settings = Settings()


def create_authenticated_client():
    auth_token = settings.CASHMERE_API_KEY
    return Client(
        settings.CASHMERE_MCP_SERVER_URL,
        auth=BearerAuth(auth_token),
    )


async def list_tools():
    client = create_authenticated_client()
    async with client:
        tools = await client.list_tools()
        print("Tools:")
        print("\n".join(f"  - {t.name}" for t in tools))


async def list_resources():
    client = create_authenticated_client()
    async with client:
        resources = await client.list_resources()
        print("Resources:")
        print("\n".join(f"  - {r.uri}" for r in resources))


async def search_publications(query: str) -> SearchPublicationsResponse:
    client = create_authenticated_client()
    async with client:
        publications = await client.call_tool("search_publications", {"query": query})
        publications = parse_json_content(publications)
        return publications[0]


async def list_publications(
    collection_id: int | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> PublicationsResponse:
    client = create_authenticated_client()
    async with client:
        publications = await client.call_tool(
            "list_publications",
            {"limit": limit, "offset": offset, "collection_id": collection_id},
        )
        publications = parse_json_content(publications)
        return publications[0]


async def get_publication(publication_id: str) -> Publication:
    client = create_authenticated_client()
    async with client:
        publication = await client.call_tool(
            "get_publication", {"publication_id": publication_id}
        )
        publication = parse_json_content(publication)
        return publication[0]


async def list_collections(
    limit: int | None = None, offset: int | None = None
) -> CollectionsResponse:
    client = create_authenticated_client()
    async with client:
        collections = await client.call_tool(
            "list_collections", {"limit": limit, "offset": offset}
        )
        collections = parse_json_content(collections)
        return collections[0]


async def get_collection(collection_id: str) -> Collection:
    client = create_authenticated_client()
    async with client:
        collection = await client.call_tool(
            "get_collection", {"collection_id": collection_id}
        )
        collection = parse_json_content(collection)
        return collection


async def get_usage_report(userId: str | None):
    client = create_authenticated_client()
    async with client:
        usage_report = await client.call_tool("get_usage_report", {"userId": userId})
        usage_report = parse_json_content(usage_report)
        return usage_report


async def test_all_tools():
    user_query = "How should I do marketing in the twenty-first century?"
    matched_publications = await search_publications(user_query)
    print(f"matched_publications: {len(matched_publications)}")

    collections = await list_collections()
    print(f"collections: {len(collections)}")

    # TODO: Implement get_collection
    # collection = await get_collection(collections['items'][0]['id'])
    # print(f"collection: {collection}")

    publications = await list_publications(collection_id=collections["items"][0]["id"])
    print(f"publications: {len(publications)}")

    publication = await get_publication(publications["items"][0]["uuid"])
    print(f"publication: {pyjson.dumps(publication, indent=2)}")

    # TODO: Implement get_usage_report
    # usage_report = await get_usage_report(None)
    # print(f"usage_report: {usage_report}")


asyncio.run(list_tools())
asyncio.run(list_resources())
# asyncio.run(test_all_tools())
user_query = "How should I do marketing in the twenty-first century?"
matched_publications = asyncio.run(search_publications(user_query))
print(f"matched_publications: {matched_publications}")
