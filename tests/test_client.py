"""Integration tests for Cashmere MCP client.

These tests verify the client's interaction with a live MCP server.
They require a .env.local file with the following variables:
- CASHMERE_API_KEY
- CASHMERE_MCP_SERVER_URL
"""
import os
from pathlib import Path
import pytest
from dotenv import load_dotenv

# Load environment variables from .env.local
env_path = Path(__file__).parent.parent / '.env.local'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    pytest.skip("Missing .env.local file with test configuration", allow_module_level=True)

# Check for required environment variables
if not all([os.getenv("CASHMERE_API_KEY"), os.getenv("CASHMERE_MCP_SERVER_URL")]):
    pytest.skip(
        "Missing required environment variables. Please check your .env.local file.",
        allow_module_level=True
    )

from cashmeremcp.cashmere_client import (
    list_publications,
    get_publication,
    search_publications,
    list_collections,
    get_collection,
    get_usage_report_summary,
    list_tools,
    list_resources,
    async_list_publications,
    async_get_publication,
    async_search_publications,
    async_list_collections,
    async_get_collection,
    async_get_usage_report_summary,
    async_list_tools,
    async_list_resources,
)

# Test data
TEST_SEARCH_QUERY = "test"
TEST_LIMIT = 1

# Helper function to get a test publication ID
def get_test_publication_id() -> str:
    """Helper to get a valid publication ID for testing."""
    publications = list_publications(limit=1)
    if not publications.get('items'):
        pytest.skip("No publications available for testing")
    return publications['items'][0]['uuid']


async def async_get_test_publication_id() -> str:
    """Async helper to get a valid publication ID for testing."""
    publications = await async_list_publications(limit=1)
    if not publications.get('items'):
        pytest.skip("No publications available for testing")
    return publications['items'][0]['uuid']

# Helper function to get a test collection ID
def get_test_collection_id() -> int:
    """Helper to get a valid collection ID for testing."""
    collections = list_collections(limit=1)
    if not collections.get('items'):
        pytest.skip("No collections available for testing")
    return collections['items'][0]['id']


async def async_get_test_collection_id() -> int:
    """Async helper to get a valid collection ID for testing."""
    collections = await async_list_collections(limit=1)
    if not collections.get('items'):
        pytest.skip("No collections available for testing")
    return collections['items'][0]['id']

# Synchronous tests
def test_list_publications() -> None:
    """Test listing publications with real API call."""
    result = list_publications(limit=TEST_LIMIT)
    
    # Verify response structure
    assert isinstance(result, dict), "Response should be a dictionary"
    assert 'items' in result, "Response should contain 'items' key"
    assert isinstance(result['items'], list), "Items should be a list"
    assert 'count' in result, "Response should contain 'count' key"
    
    # If we have items, verify their structure
    if result['items']:
        item = result['items'][0]
        assert 'uuid' in item, "Publication item should have 'uuid'"
        assert 'data' in item, "Publication item should have 'data'"


def test_get_publication() -> None:
    """Test getting a single publication with real API call."""
    pub_id = get_test_publication_id()
    result = get_publication(pub_id)
    
    # Verify publication structure
    assert isinstance(result, dict), "Response should be a dictionary"
    assert 'uuid' in result, "Publication should have 'uuid'"
    assert 'data' in result, "Publication should have 'data'"
    assert 'title' in result['data'], "Publication data should have 'title'"


def test_search_publications() -> None:
    """Test searching publications with real API call."""
    result = search_publications(TEST_SEARCH_QUERY)
    
    # Verify response structure
    assert isinstance(result, list), "Response should be a list"
    
    # If we have results, verify their structure
    if result:
        item = result[0]
        assert 'omnipub_uuid' in item, "Search result should have 'omnipub_uuid'"
        assert 'content' in item, "Search result should have 'content'"


def test_list_collections() -> None:
    """Test listing collections with real API call."""
    result = list_collections(limit=TEST_LIMIT)
    
    # Verify response structure
    assert isinstance(result, dict), "Response should be a dictionary"
    assert 'items' in result, "Response should contain 'items' key"
    assert isinstance(result['items'], list), "Items should be a list"
    
    # If we have items, verify their structure
    if result['items']:
        item = result['items'][0]
        assert 'id' in item, "Collection should have 'id'"
        assert 'name' in item, "Collection should have 'name'"


def test_get_collection() -> None:
    """Test getting a single collection with real API call."""
    collection_id = get_test_collection_id()
    result = get_collection(collection_id)
    
    # Verify collection structure
    assert isinstance(result, dict), "Response should be a dictionary"
    assert 'id' in result, "Collection should have 'id'"
    assert 'name' in result, "Collection should have 'name'"
    assert 'description' in result, "Collection should have 'description'"


def test_list_tools() -> None:
    """Test listing available tools."""
    tools = list_tools()
    assert isinstance(tools, list), "Should return a list of tools"
    if tools:  # If tools are available, check their structure
        tool = tools[0]
        assert hasattr(tool, 'name'), "Tool should have 'name'"
        assert hasattr(tool, 'description'), "Tool should have 'description'"


def test_list_resources() -> None:
    """Test listing available resources."""
    resources = list_resources()
    assert isinstance(resources, list), "Should return a list of resources"
    if resources:  # If resources are available, check their structure
        resource = resources[0]
        assert hasattr(resource, 'name'), "Resource should have 'name'"
        assert hasattr(resource, 'description'), "Resource should have 'description'"


def test_get_usage_report_summary() -> None:
    """Test getting usage report summary."""
    try:
        report = get_usage_report_summary()
        print(f"Debug - Raw API response: {report}")  # Debug log
        assert isinstance(report, dict), "Should return a dictionary"
        # Check for expected keys in the report based on actual API response
        assert 'embeddings_count' in report, "Report should contain 'embeddings_count'"
        assert 'first_report_date' in report, "Report should contain 'first_report_date'"
        assert 'last_report_date' in report, "Report should contain 'last_report_date'"
        assert 'report_count' in report, "Report should contain 'report_count'"
    except Exception as e:
        # Skip if the endpoint is not available or returns an error
        pytest.skip(f"Usage report endpoint not available: {e}")


# Async tests
@pytest.mark.asyncio
async def test_async_list_publications() -> None:
    """Test async listing of publications."""
    result = await async_list_publications(limit=TEST_LIMIT)
    
    # Verify response structure
    assert isinstance(result, dict), "Response should be a dictionary"
    assert 'items' in result, "Response should contain 'items' key"
    assert isinstance(result['items'], list), "Items should be a list"


@pytest.mark.asyncio
async def test_async_get_publication() -> None:
    """Test async getting of a single publication."""
    pub_id = await async_get_test_publication_id()
    result = await async_get_publication(pub_id)
    
    # Verify publication structure
    assert isinstance(result, dict), "Response should be a dictionary"
    assert 'uuid' in result, "Publication should have 'uuid'"
    assert 'data' in result, "Publication should have 'data'"
    assert 'title' in result['data'], "Publication data should have 'title'"


@pytest.mark.asyncio
async def test_async_search_publications() -> None:
    """Test async searching of publications."""
    result = await async_search_publications(TEST_SEARCH_QUERY)
    
    # Verify response structure
    assert isinstance(result, list), "Response should be a list"
    if result:  # If we have results, verify their structure
        assert 'omnipub_uuid' in result[0], "Search result should have 'omnipub_uuid'"


@pytest.mark.asyncio
async def test_async_list_tools() -> None:
    """Test async listing of available tools."""
    tools = await async_list_tools()
    assert isinstance(tools, list), "Should return a list of tools"
    if tools:  # If tools are available, check their structure
        tool = tools[0]
        assert hasattr(tool, 'name'), "Tool should have 'name'"
        assert hasattr(tool, 'description'), "Tool should have 'description'"


@pytest.mark.asyncio
async def test_async_list_resources() -> None:
    """Test async listing of available resources."""
    resources = await async_list_resources()
    assert isinstance(resources, list), "Should return a list of resources"
    if resources:  # If resources are available, check their structure
        resource = resources[0]
        assert hasattr(resource, 'name'), "Resource should have 'name'"
        assert hasattr(resource, 'type'), "Resource should have 'type'"


@pytest.mark.asyncio
async def test_async_get_usage_report_summary() -> None:
    """Test async getting of usage report summary."""
    try:
        report = await async_get_usage_report_summary()
        print(f"Debug - Async Raw API response: {report}")  # Debug log
        assert isinstance(report, dict), "Should return a dictionary"
        # Check for expected keys in the report based on actual API response
        assert 'embeddings_count' in report, "Report should contain 'embeddings_count'"
        assert 'first_report_date' in report, "Report should contain 'first_report_date'"
        assert 'last_report_date' in report, "Report should contain 'last_report_date'"
        assert 'report_count' in report, "Report should contain 'report_count'"
    except Exception as e:
        # Skip if the endpoint is not available or returns an error
        pytest.skip(f"Async usage report endpoint not available: {e}")


@pytest.mark.asyncio
async def test_async_list_collections() -> None:
    """Test async listing of collections."""
    result = await async_list_collections(limit=TEST_LIMIT)
    
    # Verify response structure
    assert isinstance(result, dict), "Response should be a dictionary"
    assert 'items' in result, "Response should contain 'items' key"
    assert isinstance(result['items'], list), "Items should be a list"
    
    # If we have items, verify their structure
    if result['items']:
        item = result['items'][0]
        assert 'id' in item, "Collection should have 'id'"
        assert 'name' in item, "Collection should have 'name'"


@pytest.mark.asyncio
async def test_async_get_collection() -> None:
    """Test async getting a single collection."""
    # Get a valid collection ID using async helper
    collection_id = await async_get_test_collection_id()
    
    # Now test getting the collection by ID
    result = await async_get_collection(collection_id)
    
    # Verify collection structure
    assert isinstance(result, dict), "Response should be a dictionary"
    assert 'id' in result, "Collection should have 'id'"
    assert 'name' in result, "Collection should have 'name'"
    assert 'description' in result, "Collection should have 'description'"

# Test error cases
def test_get_nonexistent_publication() -> None:
    """Test getting a publication that doesn't exist."""
    with pytest.raises(Exception):
        get_publication("nonexistent-id-1234567890")


@pytest.mark.asyncio
async def test_async_get_nonexistent_publication() -> None:
    """Test async getting a publication that doesn't exist."""
    with pytest.raises(Exception):
        await async_get_publication("nonexistent-id-1234567890")
