"""Cashmere MCP Client

A Python client for interacting with the Cashmere MCP API.
"""

import asyncio
import json as pyjson
import random
import sys
import time
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, cast, get_origin, get_args, get_type_hints

from fastmcp import Client
from fastmcp.client.auth import BearerAuth
from fastmcp.tools import Tool
from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore

from cashmere_types import (
    Collection,
    CollectionsResponse,
    Publication,
    PublicationsResponse,
    SearchPublicationsResponse,
    SearchPublicationItem,
)


class APIResponseError(ValueError):
    """Raised when the API returns an unexpected response format."""
    pass


def parse_json_content(content: Any, model_type: type | None = None) -> Any:
    """Convert TextContent, str, bytes, bytearray, or list to parsed JSON.
    
    Args:
        content: The content to parse (can be TextContent, str, bytes, bytearray, or list)
        model_type: Optional type hint to convert the parsed content to
        
    Returns:
        Parsed JSON content, optionally converted to the specified type.
        If the input is a list, only the first item is parsed.
        
    Raises:
        APIResponseError: If the content cannot be parsed or doesn't match the expected format
        TypeError: If the content type is not supported
    """
    def _get_original_text(data: Any) -> str:
        """Helper to get the original text content if available."""
        if hasattr(data, 'text'):
            return data.text
        if isinstance(data, (str, bytes, bytearray)):
            return data.decode('utf-8') if isinstance(data, (bytes, bytearray)) else data
        return str(data)

    def _parse(data: Any) -> Any:
        original_text = _get_original_text(data)
        
        # Handle lists by taking the first item if it's the only item
        if isinstance(data, list):
            if not data:
                raise APIResponseError("Received empty list in API response")
            if len(data) > 1:
                print(f"Warning: Received {len(data)} items in response, only processing the first one")
            data = data[0]
        
        # Handle TextContent-like objects
        if hasattr(data, 'text') and hasattr(data, 'type'):
            try:
                data = pyjson.loads(data.text)
            except (pyjson.JSONDecodeError, TypeError) as e:
                raise APIResponseError(f"Failed to parse JSON from TextContent: {str(e)}\nOriginal content: {original_text}")
        # Handle string/bytes input
        elif isinstance(data, (str, bytes, bytearray)):
            try:
                data = pyjson.loads(data)
            except (pyjson.JSONDecodeError, TypeError) as e:
                raise APIResponseError(f"Failed to parse JSON: {str(e)}\nOriginal content: {original_text}")
        
        # If we have a model type to validate against
        if model_type is not None:
            # Handle list types like List[SearchPublicationItem]
            if hasattr(model_type, '__origin__') and get_origin(model_type) is list:
                if not isinstance(data, list):
                    raise APIResponseError(f"Expected a list, got {type(data).__name__}\nOriginal content: {original_text}")
                item_type = get_args(model_type)[0]
                if hasattr(item_type, '__annotations__'):  # List[TypedDict]
                    return [item_type(**item) if isinstance(item, dict) else item for item in data]
                return data
            # Handle TypedDict
            elif hasattr(model_type, '__annotations__'):
                if not isinstance(data, dict):
                    raise APIResponseError(f"Expected a dictionary, got {type(data).__name__}\nOriginal content: {original_text}")
                result = {}
                for field, field_type in get_type_hints(model_type).items():
                    if field in data:
                        try:
                            result[field] = _convert_value(data[field], field_type)
                        except (ValueError, TypeError) as e:
                            raise APIResponseError(f"Failed to convert field '{field}': {str(e)}\nOriginal content: {original_text}")
                    elif field in getattr(model_type, '__required_keys__', set()):
                        raise APIResponseError(f"Missing required field: {field}\nOriginal content: {original_text}")
                return model_type(**result)
        
        return data
    
    def _convert_value(value: Any, target_type: type) -> Any:
        """Convert a value to the target type if necessary."""
        if value is None:
            return None
            
        # Handle primitive types
        if target_type in (str, int, float, bool):
            try:
                return target_type(value)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Cannot convert {value!r} to {target_type.__name__}")
        
        # Handle generic types like List, Dict, etc.
        if hasattr(target_type, '__origin__'):
            origin = get_origin(target_type)
            args = get_args(target_type)
            
            if origin is list and isinstance(value, list):
                item_type = args[0] if args else type(value[0]) if value else str
                return [_convert_value(item, item_type) for item in value]
                
            elif origin is dict and isinstance(value, dict):
                key_type, value_type = args if len(args) == 2 else (str, type(next(iter(value.values()))) if value else str)
                return {_convert_value(k, key_type): _convert_value(v, value_type) 
                       for k, v in value.items()}
                       
            elif origin is Union:  # Handle Optional[Type] which is Union[Type, None]
                non_none_types = [t for t in args if t is not type(None)]
                if non_none_types:
                    return _convert_value(value, non_none_types[0])
        
        # Handle nested TypedDict
        elif hasattr(target_type, '__annotations__'):
            return parse_json_content(value, target_type)
            
        return value
    
    try:
        return _parse(content)
    except APIResponseError:
        raise
    except Exception as e:
        raise APIResponseError(f"Error parsing content: {str(e)}") from e


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


# Async functions
async def async_list_tools() -> List[Tool]:
    """List all available tools from the MCP server.
    
    Returns:
        List[Tool]: List of available tools
    """
    client = create_authenticated_client()
    async with client:
        result = await client.list_tools()
        return result


async def async_list_resources():
    """List all available resources from the MCP server.
    
    Returns:
        List of available resources
    """
    client = create_authenticated_client()
    async with client:
        result = await client.list_resources()
        return result


async def async_search_publications(
    query: str, 
    external_ids: Optional[Union[str, List[str]]] = None
) -> SearchPublicationsResponse:
    """Search for publications using the call_tool method.
    
    Args:
        query: The search query
        external_ids: Optional external IDs to filter by
        
    Returns:
        Search response containing items and count
        
    Raises:
        APIResponseError: If the API response format is unexpected
    """
    client = create_authenticated_client()
    try:
        # Initialize params with query
        params: Dict[str, Any] = {"query": query}
        
        # Add external_ids to params if provided
        if external_ids:
            if isinstance(external_ids, str):
                params["external_ids"] = [external_ids]
            else:
                params["external_ids"] = external_ids
            
        async with client:
            result = await client.call_tool("search_publications", params)
            # print(f"Result: {result}")
            # Parse the result as a list of SearchPublicationItem
            parsed = parse_json_content(result, SearchPublicationsResponse)
            
            return parsed
    except Exception as e:
        if isinstance(e, APIResponseError):
            raise
        raise RuntimeError(f"Failed to search publications: {str(e)}") from e


async def async_list_publications(
    collection_id: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> PublicationsResponse:
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
    client = create_authenticated_client()
    async with client:
        params: Dict[str, Any] = {}
        if collection_id is not None:
            params["collection_id"] = collection_id
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
            
        result = await client.call_tool("list_publications", params)
        # Parse the result and ensure it's in the correct PublicationsResponse format
        parsed = parse_json_content(result, PublicationsResponse)
        
        return parsed


async def async_get_publication(publication_id: str) -> Publication:
    """Get a single publication by ID using the call_tool method.
    
    Args:
        publication_id: The ID of the publication to retrieve
        
    Returns:
        The requested publication as a Publication object
        
    Raises:
        APIResponseError: If the API response format is unexpected
    """
    client = create_authenticated_client()
    async with client:
        result = await client.call_tool("get_publication", {"publication_id": publication_id})
        parsed = parse_json_content(result, Publication)
        return parsed


async def async_list_collections(
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> CollectionsResponse:
    """List all collections using the call_tool method.
    
    Args:
        limit: Maximum number of results to return
        offset: Offset for pagination
        
    Returns:
        Collections response containing items and count
        
    Raises:
        APIResponseError: If the API response format is unexpected
    """
    client = create_authenticated_client()
    async with client:
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        result = await client.call_tool("list_collections", params)
        return parse_json_content(result, CollectionsResponse)


async def async_get_collection(collection_id: int) -> Collection:
    """Get a single collection by ID using the call_tool method.
    
    Args:
        collection_id: The ID of the collection to retrieve
        
    Returns:
        The requested collection as a Collection object
        
    Raises:
        APIResponseError: If the API response format is unexpected
        ValueError: If the collection is not found
    """
    client = create_authenticated_client()
    async with client:
        try:
            result = await client.call_tool("get_collection", {"collection_id": collection_id})
            print(f"Debug - Raw API response: {result}")  # Debug log
            return parse_json_content(result, Collection)
        except Exception as e:
            print(f"Debug - Error in async_get_collection: {str(e)}")
            print(f"Debug - Collection ID: {collection_id}")
            print(f"Debug - Client settings: {settings.CASHMERE_MCP_SERVER_URL}")
            raise

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
    client = create_authenticated_client()
    async with client:
        params = {}
        if external_ids:
            params["external_ids"] = external_ids if isinstance(external_ids, list) else [external_ids]
        result = await client.call_tool("get_usage_report_summary", params or {})
        print(f"Debug - Raw API response: {result}")  # Debug log
        return cast(Dict[str, Any], parse_json_content(result))


# Synchronous wrappers for backward compatibility
def list_tools() -> list[Tool]:
    """Synchronously list all available tools."""
    return asyncio.run(async_list_tools())


def list_resources():
    """Synchronously list all available resources."""
    return asyncio.run(async_list_resources())


def search_publications(
    query: str, 
    external_ids: Optional[Union[str, List[str]]] = None
) -> SearchPublicationsResponse:
    """Synchronously search for publications."""
    return asyncio.run(async_search_publications(query, external_ids))


def list_publications(
    collection_id: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> PublicationsResponse:
    """Synchronously list publications.
    
    Args:
        collection_id: Filter by collection ID
        limit: Maximum number of results to return
        offset: Offset for pagination
        
    Returns:
        Publications response containing items and count
    """
    return asyncio.run(async_list_publications(collection_id, limit, offset))


def get_publication(publication_id: str) -> Publication:
    """Synchronously get a single publication."""
    return asyncio.run(async_get_publication(publication_id))


def list_collections(
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> CollectionsResponse:
    """Synchronously list all collections."""
    return asyncio.run(async_list_collections(limit, offset))


def get_collection(collection_id: int) -> Collection:
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
    
    try:
        if args.command == "list-tools":
            tools = list_tools()
            print(f"{len(tools)} available tools:")
            for tool in tools:
                print(f"- {tool.name}")
                
        elif args.command == "list-resources":
            resources = list_resources()
            print(f"{len(resources)} available resources:")
            for resource in resources:
                print(f"- {resource.name}")
                
        elif args.command == "search":
            results: SearchPublicationsResponse = search_publications(args.query, args.external_ids)
            print(f"Found {len(results)} results:")
            for i, result in enumerate(results, 1):
                print(f"{i}. {result.get('omnipub_title', 'Untitled')} - {result.get('content', '')[:50]}...")
                
        elif args.command == "list-publications":
            response: PublicationsResponse = list_publications(
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
            print("Usage report:")
            for k, v in usage.items():
                print(f"{k}: {v}")
                
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
