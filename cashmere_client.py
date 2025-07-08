"""Cashmere MCP Client

A Python client for interacting with the Cashmere MCP API.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Union
import time

from fastmcp import Client
from fastmcp.client.auth import BearerAuth
from pydantic_settings import BaseSettings, SettingsConfigDict

from cashmere_types import (
    Collection,
    CollectionsResponse,
    Publication,
    PublicationsResponse,
    SearchPublicationsResponse,
)


class Settings(BaseSettings):
    """Application settings."""

    CASHMERE_API_KEY: str = ""
    CASHMERE_MCP_SERVER_URL: str = ""

    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")


# Global settings instance
settings = Settings()


def create_authenticated_client() -> Client:
    """Create an authenticated MCP client.

    Returns:
        An authenticated Client instance
    """
    return Client(
        transport=settings.CASHMERE_MCP_SERVER_URL,
        auth=BearerAuth(settings.CASHMERE_API_KEY),
    )


client = create_authenticated_client()


def _parse_and_validate(result: Any, model_type: type) -> Any:
    """Parse JSON content and validate with Pydantic model."""
    # Extract text content from various MCP response formats
    if hasattr(result, 'text'):
        # Direct TextContent object
        data = json.loads(result.text)
    elif isinstance(result, list) and len(result) == 1 and hasattr(result[0], 'text'):
        # List containing single TextContent object (common MCP format)
        data = json.loads(result[0].text)
    elif isinstance(result, (str, bytes, bytearray)):
        # Raw string/bytes
        data = json.loads(result)
    else:
        # Already parsed JSON
        data = result
    # Handle List[Model] types
    if hasattr(model_type, '__origin__') and model_type.__origin__ is list:
        # If we expect a list but got a single item, wrap it in a list
        if not isinstance(data, list):
            data = [data]
        item_type = model_type.__args__[0]
        return [item_type.model_validate(item).model_dump() for item in data]
    else:
        # Single Pydantic model
        return model_type.model_validate(data).model_dump()


# Async functions
async def async_list_tools() -> list[dict]:
    """List all available tools from the MCP server.

    Returns:
        List[dict]: List of available tools as dictionaries
    """
    async with client:
        result = await client.list_tools()
        # Return tools as dictionaries to avoid validation issues
        return [tool.model_dump() for tool in result]


async def async_list_resources():
    """List all available resources from the MCP server.

    Returns:
        List of available resources
    """
    async with client:
        result = await client.list_resources()
        return result


async def async_search_publications(
    query: str,
    external_ids: Optional[Union[str, List[str]]] = None
) -> List[dict]:
    """Search for publications using the call_tool method.

    Args:
        query: The search query
        external_ids: Optional external IDs to filter by

    Returns:
        Search response containing items and count

    Raises:
        APIResponseError: If the API response format is unexpected
    """
    # Initialize params with query
    params: Dict[str, Any] = {"query": query}

    # Add external_ids to params if provided
    if external_ids:
        if isinstance(external_ids, str):
            params["external_ids"] = [external_ids]
        else:
            params["external_ids"] = external_ids

    async with client:
        start = time.time()
        result = await client.call_tool("search_publications", params)
        # print(f"Result: {result}")
        # Parse the result as a list of SearchPublicationItem
        print("[search_publications]", time.time() - start)
        parsed = _parse_and_validate(result, SearchPublicationsResponse)
        return parsed


async def async_list_publications(
    collection_id: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> dict:
    """List publications with optional filtering using the call_tool method.

    Args:
        collection_id: Filter by collection ID
        limit: Maximum number of results to return
        offset: Offset for pagination

    Returns:
        Publications response containing items and count

    Raises:
        APIResponseError: If the API response format is unexpected
    """
    async with client:
        params: Dict[str, Any] = {}
        if collection_id is not None:
            params["collection_id"] = collection_id
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        start = time.time()
        result = await client.call_tool("list_publications", params)
        # Parse the result and ensure it's in the correct PublicationsResponse format
        parsed = _parse_and_validate(result, PublicationsResponse)
        end = time.time()
        print("[list publications]", end - start)

        return parsed


async def async_get_publication(publication_id: str) -> dict:
    """Get a single publication by ID using the call_tool method.

    Args:
        publication_id: The ID of the publication to retrieve

    Returns:
        The requested publication as a Publication object

    Raises:
        APIResponseError: If the API response format is unexpected
    """
    async with client:
        result = await client.call_tool("get_publication", {"publication_id": publication_id})
        parsed = _parse_and_validate(result, Publication)
        return parsed


async def async_list_collections(
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> dict:
    """List all collections using the call_tool method.

    Args:
        limit: Maximum number of results to return
        offset: Offset for pagination

    Returns:
        Collections response containing items and count

    Raises:
        APIResponseError: If the API response format is unexpected
    """
    async with client:
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        start = time.time()
        result = await client.call_tool("list_collections", params)
        print("[list_collections]", time.time() - start)
        return _parse_and_validate(result, CollectionsResponse)


async def async_get_collection(collection_id: int) -> dict:
    """Get a single collection by ID using the call_tool method.

    Args:
        collection_id: The ID of the collection to retrieve

    Returns:
        The requested collection as a Collection object

    Raises:
        APIResponseError: If the API response format is unexpected
        ValueError: If the collection is not found
    """
    async with client:
        result = await client.call_tool("get_collection", {"collection_id": collection_id})
        return _parse_and_validate(result, Collection)


async def async_get_usage_report_summary(
    external_ids: Optional[Union[str, List[str]]] = None
) -> Dict[str, Any]:
    """
    Asynchronously get usage report summary.

    Args:
        external_ids: Optional external IDs to filter by

    Returns:
        Usage report summary
    """
    async with client:
        params = {}
        if external_ids:
            params["external_ids"] = external_ids if isinstance(external_ids, list) else [external_ids]
        result = await client.call_tool("get_usage_report_summary", params or {})
        return json.loads(result[0].text)


# Synchronous wrappers for backward compatibility
def list_tools() -> list[dict]:
    """Synchronously list all available tools.

    Returns:
        List[dict]: List of available tools as dictionaries
    """
    return asyncio.run(async_list_tools())


def list_resources():
    """Synchronously list all available resources."""
    return asyncio.run(async_list_resources())


def search_publications(
    query: str,
    external_ids: Optional[Union[str, List[str]]] = None
) -> List[dict]:
    """Synchronously search for publications."""
    return asyncio.run(async_search_publications(query, external_ids))


def list_publications(
    collection_id: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> dict:
    """Synchronously list publications.

    Args:
        collection_id: Filter by collection ID
        limit: Maximum number of results to return
        offset: Offset for pagination

    Returns:
        Publications response containing items and count
    """
    return asyncio.run(async_list_publications(collection_id, limit, offset))


def get_publication(publication_id: str) -> dict:
    """Synchronously get a single publication."""
    return asyncio.run(async_get_publication(publication_id))


def list_collections(
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> dict:
    """Synchronously list all collections."""
    return asyncio.run(async_list_collections(limit, offset))


def get_collection(collection_id: int) -> dict:
    """Synchronously get a single collection."""
    return asyncio.run(async_get_collection(collection_id))

def get_usage_report_summary(
    external_ids: Optional[Union[str, List[str]]] = None
) -> Dict[str, Any]:
    """
    Synchronously get usage report summary. If called from a running event loop, raises RuntimeError.

    Args:
        external_ids: Optional external IDs to filter by

    Returns:
        Usage report summary
    """
    return asyncio.run(async_get_usage_report_summary(external_ids=external_ids))

# Command-line interface
def main() -> None:
    """Main entry point for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(description="Cashmere MCP Client")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # List tools
    subparsers.add_parser("list-tools", help="List available tools")

    # List resources
    subparsers.add_parser("list-resources", help="List available resources")

    # Search publications
    search_parser = subparsers.add_parser("search", help="Search publications")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--external-ids", nargs="+", help="External IDs to filter by")

    # List publications
    list_pubs_parser = subparsers.add_parser("list-publications", help="List publications")
    list_pubs_parser.add_argument("--collection-id", type=int, help="Filter by collection ID")
    list_pubs_parser.add_argument("--limit", type=int, help="Maximum number of results")
    list_pubs_parser.add_argument("--offset", type=int, help="Pagination offset")

    # Get publication
    get_pub_parser = subparsers.add_parser("get-publication", help="Get publication by ID")
    get_pub_parser.add_argument("publication_id", help="Publication ID")

    # List collections
    list_colls_parser = subparsers.add_parser("list-collections", help="List collections")
    list_colls_parser.add_argument("--limit", type=int, help="Maximum number of results")
    list_colls_parser.add_argument("--offset", type=int, help="Pagination offset")

    # Get collection
    get_coll_parser = subparsers.add_parser("get-collection", help="Get collection by ID")
    get_coll_parser.add_argument("collection_id", type=int, help="Collection ID")

    # Get usage report
    usage_parser = subparsers.add_parser("usage", help="Get usage report")
    usage_parser.add_argument("--external-ids", nargs="+", help="External IDs to filter by")

    args = parser.parse_args()

    if args.command == "list-tools":
        tools = list_tools()
        print(f"{len(tools)} available tools:")
        for tool in tools:
            print(f"- {tool['name']}")

    elif args.command == "list-resources":
        resources = list_resources()
        print(f"{len(resources)} available resources:")
        for resource in resources:
            # Use attribute access for Resource objects
            name = getattr(resource, 'name', 'Unnamed')
            print(f"- {name}")

    elif args.command == "search":
        start = time.time()
        results = search_publications(args.query, args.external_ids)
        end = time.time()
        print("time", end - start)
        print(f"Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result.get('omnipub_title', 'Untitled')} - {result.get('content', '')[:50]}...")

    elif args.command == "list-publications":
        response = list_publications(
            collection_id=args.collection_id,
            limit=args.limit,
            offset=args.offset
        )
        print(f"Found {response.get('count', 0)} publications:")
        for pub_item in response.get('items', []):
            pub_data = pub_item.get('data', {})
            print(f"- {pub_data.get('title', 'Untitled')} ({pub_item.get('uuid', 'No ID')})")

    elif args.command == "get-publication":
        pub = get_publication(args.publication_id)
        print(f"Title: {pub.get('data', {}).get('title', 'Untitled')}")
        print(f"ID: {pub.get('uuid', 'No ID')}")

    elif args.command == "list-collections":
        collections = list_collections(limit=args.limit, offset=args.offset)
        print(f"Found {collections['count']} collections:")
        for coll in collections['items']:
            print(f"- {coll.get('name', 'Unnamed collection')} (ID: {coll.get('id', '?')})")

    elif args.command == "get-collection":
        coll = get_collection(args.collection_id)
        print(f"Name: {coll.get('name', 'Unnamed collection')}")
        print(f"ID: {coll.get('id', '?')}")
        print(f"Description: {coll.get('description', 'No description')}")

    elif args.command == "usage":
        usage = get_usage_report_summary(external_ids=args.external_ids)
        print(usage)

if __name__ == "__main__":
    main()
