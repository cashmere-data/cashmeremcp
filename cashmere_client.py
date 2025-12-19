"""Cashmere MCP Client

A Python client for interacting with the Cashmere MCP API.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import time

from fastmcp import Client
from fastmcp.client.auth import BearerAuth, OAuth
from pydantic_settings import BaseSettings, SettingsConfigDict

from cashmere_types import (
    Collection,
    CollectionsResponse,
    Publication,
    PublicationsResponse,
    SearchPublicationItem,
    SearchPublicationsResponse,
    UsageReportSummary,
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
    client_kwargs = {
        "name": "Cashmere MCP Client",
        "transport": settings.CASHMERE_MCP_SERVER_URL,
    }
    if settings.CASHMERE_API_KEY:
        client_kwargs["auth"] = BearerAuth(settings.CASHMERE_API_KEY)
    elif "api_key" in settings.CASHMERE_MCP_SERVER_URL:
        # server allows this, no auth needed in client
        pass
    else:
        client_kwargs["auth"] = OAuth(
            mcp_url=settings.CASHMERE_MCP_SERVER_URL,
            client_name="Cashmere MCP Client",
        )
    return Client(**client_kwargs)


def get_oauth_token_location() -> Optional[Path]:
    home = Path.home()
    fastmcp_cache_dir = home / ".fastmcp" / "oauth-mcp-client-cache"
    if not fastmcp_cache_dir.exists():
        return None
    # Token files are named based on server URL, e.g., "http_localhost_8001_tokens.json"
    if settings.CASHMERE_MCP_SERVER_URL:
        # Convert URL to filename format: http://localhost:8001 -> http_localhost_8001
        url_normalized = settings.CASHMERE_MCP_SERVER_URL.replace("://", "_")
        url_normalized = url_normalized.replace(":", "_")
        url_normalized = url_normalized.replace("/", "_")
        url_normalized = url_normalized.rstrip("_").replace("__", "_")
        token_filename = f"{url_normalized}_tokens.json"
        token_path = fastmcp_cache_dir / token_filename
        if token_path.exists():
            return token_path
    # If no specific match, return the first tokens.json file found
    for item in fastmcp_cache_dir.iterdir():
        if item.is_file() and item.name.endswith("_tokens.json"):
            return item
    return None


def reset_oauth_token() -> bool:
    token_location = get_oauth_token_location()
    if token_location and token_location.exists():
        try:
            token_location.unlink()
            return True
        except Exception as e:
            print(f"Error deleting token file: {e}")
            return False
    return False


def get_oauth_token_info() -> Dict[str, Any]:
    token_location = get_oauth_token_location()
    info = {
        "found": False,
        "location": None,
        "size": None,
    }
    if token_location and token_location.exists():
        info["found"] = True
        info["location"] = str(token_location)
        info["size"] = token_location.stat().st_size
        try:
            with open(token_location, "r") as f:
                token_data = json.load(f)
                data = token_data["data"]
                token_payload = data.get("token_payload", {})
                access_token = token_payload.get("access_token", "")
                info["expires_at"] = data.get("expires_at", "N/A")
                info["access_token_preview"] = access_token[:5] if access_token else "N/A"
                info["keys"] = list(token_payload.keys())
        except Exception:
            pass
    return info


client = create_authenticated_client()


# Mapping of tool names to their expected Pydantic model types
TOOL_TYPE_MAPPING = {
    'search_publications': SearchPublicationItem,  # This represents the list item type
    'list_publications': PublicationsResponse,
    'get_publication': Publication,
    'list_collections': CollectionsResponse,
    'get_collection': Collection,
    'get_usage_report_summary': UsageReportSummary,
}


def _pydantic_to_json_schema_properties(model_class) -> dict:
    """Convert Pydantic model to JSON schema properties for comparison."""
    if hasattr(model_class, 'model_json_schema'):
        schema = model_class.model_json_schema()
        return schema.get('properties', {})
    return {}


def _validate_tool_schema_against_type(tool_name: str, tool_schema: dict) -> dict:
    """Validate a tool's output schema against its expected Pydantic type.

    Returns:
        dict: Validation result with 'valid', 'expected_type', 'issues' keys
    """
    result = {
        'valid': True,
        'expected_type': None,
        'issues': []
    }

    if tool_name not in TOOL_TYPE_MAPPING:
        result['valid'] = False
        result['issues'].append(f"No expected type defined for tool '{tool_name}'")
        return result

    expected_type = TOOL_TYPE_MAPPING[tool_name]
    result['expected_type'] = expected_type.__name__

    # Get expected properties from Pydantic model
    expected_properties = _pydantic_to_json_schema_properties(expected_type)

    # Get actual properties from tool schema
    actual_properties = tool_schema.get('properties', {})

    # Handle tools with generic schemas (like list_publications)
    if not actual_properties and tool_schema.get('additionalProperties') is True:
        result['issues'].append("Tool has generic schema with no specific properties defined")
        # For generic schemas, we can't validate structure but we note it
        return result

    # Special handling for search_publications which wraps results in a "result" array
    if tool_name == 'search_publications' and 'result' in actual_properties:
        # Extract the array item schema from the result property
        result_prop = actual_properties['result']
        if result_prop.get('type') == 'array' and 'items' in result_prop:
            # Get the schema of array items
            items_schema = result_prop['items']
            if '$ref' in items_schema and '$defs' in tool_schema:
                # Resolve the reference
                ref_name = items_schema['$ref'].split('/')[-1]
                if ref_name in tool_schema['$defs']:
                    resolved_schema = tool_schema['$defs'][ref_name]
                    actual_properties = resolved_schema.get('properties', {})

    # Check for missing properties
    expected_keys = set(expected_properties.keys())
    actual_keys = set(actual_properties.keys())

    missing_props = expected_keys - actual_keys
    extra_props = actual_keys - expected_keys

    if missing_props:
        result['valid'] = False
        result['issues'].append(f"Missing properties: {', '.join(missing_props)}")

    if extra_props:
        result['issues'].append(f"Extra properties: {', '.join(extra_props)}")

    # Check property types for common properties
    for prop in expected_keys & actual_keys:
        expected_prop = expected_properties[prop]
        actual_prop = actual_properties[prop]

        # Basic type checking (this could be more sophisticated)
        expected_type_info = expected_prop.get('type')
        actual_type_info = actual_prop.get('type')

        if expected_type_info != actual_type_info:
            # Handle anyOf cases (nullable fields)
            if 'anyOf' in expected_prop:
                expected_types = [t.get('type') for t in expected_prop['anyOf'] if 'type' in t]
                if actual_type_info not in expected_types:
                    result['valid'] = False
                    result['issues'].append(f"Property '{prop}' type mismatch: expected {expected_types}, got {actual_type_info}")
            elif 'anyOf' in actual_prop:
                actual_types = [t.get('type') for t in actual_prop['anyOf'] if 'type' in t]
                if expected_type_info not in actual_types:
                    result['valid'] = False
                    result['issues'].append(f"Property '{prop}' type mismatch: expected {expected_type_info}, got {actual_types}")
            else:
                result['valid'] = False
                result['issues'].append(f"Property '{prop}' type mismatch: expected {expected_type_info}, got {actual_type_info}")

    return result


def _parse_and_validate(result: Any, model_type: type) -> Any:
    """Parse JSON content and validate with Pydantic model."""
    def _extract_json_data(obj: Any) -> Any:
        """Extract JSON data from various MCP response formats, handling CallToolResult objects."""
        # CallToolResult object (from fastmcp) - has content but no text
        if hasattr(obj, 'content') and not hasattr(obj, 'text'):
            if isinstance(obj.content, list) and len(obj.content) > 0:
                # Extract from all items, return single if only one
                extracted = [_extract_json_data(item) for item in obj.content]
                return extracted[0] if len(extracted) == 1 else extracted
            return obj.content
        # TextContent object or item with text attribute
        elif hasattr(obj, 'text'):
            return json.loads(obj.text)
        # List with single TextContent
        elif isinstance(obj, list) and len(obj) == 1 and hasattr(obj[0], 'text'):
            return json.loads(obj[0].text)
        # Raw string/bytes
        elif isinstance(obj, (str, bytes, bytearray)):
            return json.loads(obj)
        # Already parsed JSON or other data structures - clean recursively
        elif isinstance(obj, list):
            return [_extract_json_data(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: _extract_json_data(v) for k, v in obj.items()}
        else:
            return obj

    data = _extract_json_data(result)

    # Validate with Pydantic
    if hasattr(model_type, '__origin__') and model_type.__origin__ is list:
        if not isinstance(data, list):
            data = [data]
        item_type = model_type.__args__[0]
        return [item_type.model_validate(item).model_dump() for item in data]
    else:
        return model_type.model_validate(data).model_dump()


# Async functions
async def async_list_tools() -> list[dict]:
    """List all available tools from the MCP server.

    Returns:
        List[dict]: List of available tools as dictionaries, including inputSchema (parameters)
    """
    async with client:
        result = await client.list_tools()
        # Return tools as dictionaries to avoid validation issues
        tools = []
        for tool in result:
            tool_dict = tool.model_dump()
            if hasattr(tool, 'inputSchema') and 'inputSchema' not in tool_dict:
                tool_dict['inputSchema'] = tool.inputSchema
            tools.append(tool_dict)
        return tools


async def async_list_resources():
    """List all available resources from the MCP server.

    Returns:
        List of available resources
    """
    async with client:
        result = await client.list_resources()
        return result


async def async_get_resource(uri: str) -> Any:
    """Get a specific resource by URI from the MCP server.

    Args:
        uri: The URI of the resource to fetch

    Returns:
        The resource content and metadata
    """
    async with client:
        result = await client.read_resource(uri)
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
        return _parse_and_validate(result, UsageReportSummary)


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


def get_resource(uri: str) -> Any:
    """Synchronously get a specific resource by URI."""
    return asyncio.run(async_get_resource(uri))


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

    # Check output schemas
    subparsers.add_parser("check-schemas", help="Check which tools have output schemas")

    # List resources
    subparsers.add_parser("list-resources", help="List available resources")

    # Get resource
    get_resource_parser = subparsers.add_parser("get-resource", help="Get a specific resource by URI")
    get_resource_parser.add_argument("uri", help="Resource URI (e.g., ui://widget/cashmere-app-v1-search-publications.html)")

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

    # OAuth token management
    subparsers.add_parser("oauth-token-info", help="Get information about the locally saved OAuth token")
    subparsers.add_parser("reset-oauth-token", help="Reset/clear the locally saved OAuth token")

    args = parser.parse_args()

    if args.command == "list-tools":
        tools = list_tools()
        print(f"{len(tools)} available tools:")
        for tool in tools:
            print(f"- {tool['name']}")
            print(f"  Description: {tool['description']}")
            # Show input schema (parameters)
            if 'inputSchema' in tool and tool['inputSchema']:
                input_schema = tool['inputSchema']
                print(f"  Input Parameters:")
                if 'properties' in input_schema:
                    for param_name, param_info in input_schema['properties'].items():
                        param_type = param_info.get('type', 'unknown')
                        param_desc = param_info.get('description', '')
                        required = param_name in input_schema.get('required', [])
                        required_str = " (required)" if required else " (optional)"
                        print(f"    - {param_name}: {param_type}{required_str}")
                        if param_desc:
                            print(f"        {param_desc}")
                elif 'type' in input_schema:
                    print(f"    Type: {input_schema['type']}")
            else:
                print(f"  Input Parameters: None")
            # Check if tool has output schema
            if 'outputSchema' in tool and tool['outputSchema']:
                schema = tool['outputSchema']
                print(f"  Has Output Schema: Yes")
                print(f"  Schema Type: {schema.get('type', 'unknown')}")
                if 'properties' in schema:
                    print(f"  Schema Properties: {list(schema['properties'].keys())}")
            else:
                print(f"  Has Output Schema: No")
            print()

    elif args.command == "check-schemas":
        tools = list_tools()
        print("Output Schema Analysis & Type Validation:")
        print("=" * 60)

        tools_with_schema = []
        tools_without_schema = []
        validation_results = {}

        for tool in tools:
            if 'outputSchema' in tool and tool['outputSchema']:
                tools_with_schema.append(tool)
                # Validate against expected Pydantic types
                validation_results[tool['name']] = _validate_tool_schema_against_type(
                    tool['name'], tool['outputSchema']
                )
            else:
                tools_without_schema.append(tool)

        print(f"Tools WITH output schemas ({len(tools_with_schema)}):")
        valid_count = 0
        for tool in tools_with_schema:
            schema = tool['outputSchema']
            validation = validation_results[tool['name']]

            # Status indicator
            if validation['valid']:
                status = "✓ VALID"
                valid_count += 1
            else:
                status = "⚠ INVALID"

            print(f"  {status} {tool['name']}")
            print(f"    Schema Type: {schema.get('type', 'unknown')}")

            if validation['expected_type']:
                print(f"    Expected Type: {validation['expected_type']}")

            if 'properties' in schema:
                print(f"    Properties: {', '.join(schema['properties'].keys())}")

            if validation['issues']:
                print(f"    Issues:")
                for issue in validation['issues']:
                    print(f"      - {issue}")

            print()

        print(f"Tools WITHOUT output schemas ({len(tools_without_schema)}):")
        for tool in tools_without_schema:
            print(f"  ✗ {tool['name']}")

        print(f"\nSummary:")
        print(f"  - {len(tools_with_schema)}/{len(tools)} tools have output schemas")
        print(f"  - {valid_count}/{len(tools_with_schema)} schemas are valid against expected types")

        # Show tools without defined types
        tools_without_types = [name for name in [t['name'] for t in tools_with_schema]
                              if name not in TOOL_TYPE_MAPPING]
        if tools_without_types:
            print(f"  - Tools without defined types in cashmere_types.py: {', '.join(tools_without_types)}")

    elif args.command == "list-resources":
        resources = list_resources()
        print(f"{len(resources)} available resources:")
        for resource in resources:
            # Use attribute access for Resource objects
            name = getattr(resource, 'name', 'Unnamed')
            print(f"- {name}")

    elif args.command == "get-resource":
        resource = get_resource(args.uri)
        # Print all metadata from the resource
        # Handle different response formats (dict, Pydantic model, object with attributes, etc.)
        if hasattr(resource, 'model_dump'):
            # Pydantic model
            resource_dict = resource.model_dump()
        elif isinstance(resource, dict):
            # Already a dict
            resource_dict = resource
        elif hasattr(resource, '__dict__'):
            # Object with __dict__
            resource_dict = vars(resource)
        else:
            # Fallback: convert to string representation
            resource_dict = {"raw": str(resource)}
        print(json.dumps(resource_dict, indent=2, default=str))

    elif args.command == "search":
        start = time.time()
        results = search_publications(args.query, args.external_ids)
        end = time.time()
        print("time", end - start)
        print(f"Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result.get('omnipub_title', 'Untitled')} - {result.get('content', '')[:50]}...")
            print(result)

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

    elif args.command == "oauth-token-info":
        info = get_oauth_token_info()
        if not info["found"]:
            print("No OAuth token found locally.")
            print("Token may not yet be created. Check ~/.fastmcp/oauth-mcp-client-cache/ manually.")
            return
        print("OAuth token found:")
        print(f"  Location: {info['location']}")
        print(f"  Size: {info['size']} bytes")
        if "keys" in info:
            print(f"  Token keys: {', '.join(info['keys'])}")
        if "expires_at" in info:
            print(f"  Expires at: {info['expires_at']}")
        if "access_token_preview" in info:
            print(f"  Access token: {info['access_token_preview']}...")

    elif args.command == "reset-oauth-token":
        if reset_oauth_token():
            print("OAuth token successfully reset/deleted.")
            print("You will need to re-authenticate on the next client usage.")
        else:
            print("No OAuth token found to reset.")
            print("Token may be stored in a different location or not yet created.")

if __name__ == "__main__":
    main()
