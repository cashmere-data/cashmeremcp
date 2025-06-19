"""Test script to verify README examples work as expected."""
import asyncio
import os
import sys
from typing import Any, Dict, List, Optional, Union

# Add parent directory to path to allow importing from cashmere_client
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from cashmere_client import (
    list_publications,
    get_publication,
    search_publications,
    list_collections,
    get_collection,
    get_usage_report_summary,
    async_list_publications,
    async_get_publication,
    async_search_publications,
    async_list_collections,
    async_get_collection,
)


from typing import Dict, Any, List, Optional, Union, cast, TypeVar, Type, TypedDict, Sequence, TypeVar, Generic
from cashmere_types import (
    PublicationsResponse, 
    CollectionsResponse, 
    PublicationItem, 
    Collection, 
    Publication,
    SearchPublicationItem
)

# Type variables for better type hints
T = TypeVar('T')
ResponseType = Union[PublicationsResponse, CollectionsResponse]
ItemType = Union[PublicationItem, Collection]  # More specific type for items

def test_sync_api() -> None:
    """Test synchronous API examples from README."""
    print("Testing synchronous API examples...")
    publications: Optional[ResponseType] = None
    collections: Optional[ResponseType] = None
    
    # Test list_publications
    print("\n1. Testing list_publications...")
    try:
        publications = list_publications(limit=2)
        
        # Initialize items_list based on the type of publications
        items_list: List[PublicationItem] = []
        
        # Handle both list and PublicationsResponse types
        if isinstance(publications, dict) and 'items' in publications:
            # This is a PublicationsResponse
            items_list = publications['items']
            print(f"✓ Successfully listed {publications.get('count', len(items_list))} publications")
            if items_list:
                first_pub = items_list[0]
                title = first_pub.get('data', {}).get('title', 'Untitled')
                print(f"   - First publication: {title}")
        elif isinstance(publications, list):
            # This is a list of publications (legacy format)
            items_list = publications
            print(f"✓ Successfully listed {len(items_list)} publications")
            if items_list:
                first_pub = items_list[0]
                if isinstance(first_pub, dict):
                    title = first_pub.get('data', {}).get('title', 'Untitled')
                    print(f"   - First publication: {title}")
        else:
            print(f"✗ Unexpected return type from list_publications: {type(publications).__name__}")
    except Exception as e:
        print(f"✗ Error in list_publications: {e}")
    
    # Test get_publication if we have any publications
    pub_id = None
    if len(items_list) > 0:
        first_item = items_list[0]
        if isinstance(first_item, dict):
            pub_id = first_item.get('uuid')
        elif hasattr(first_item, 'uuid'):
            pub_id = first_item.uuid
        
    if pub_id:
        print(f"\n2. Testing get_publication with ID: {pub_id}")
        try:
            publication = get_publication(pub_id)
            if isinstance(publication, dict):
                print(f"✓ Successfully retrieved publication: {publication.get('data', {}).get('title', 'Untitled')}")
            else:
                print(f"✓ Successfully retrieved publication (type: {type(publication).__name__})")
        except Exception as e:
            print(f"✗ Error in get_publication: {e}")
    
    # Test search_publications
    print("\n3. Testing search_publications...")
    try:
        results = search_publications("test")
        if isinstance(results, list):
            print(f"✓ Search returned {len(results)} results")
            if results:
                first_result = results[0]
                if isinstance(first_result, dict):
                    print(f"   - First result: {first_result.get('omnipub_title', 'Untitled')}")
    except Exception as e:
        print(f"✗ Error in search_publications: {e}")
    
    # Test list_collections
    print("\n4. Testing list_collections...")
    try:
        collections = list_collections(limit=2)
        collection_items: List[Collection] = []
        
        # Handle both list and CollectionsResponse types
        if isinstance(collections, dict) and 'items' in collections:
            # This is a CollectionsResponse
            collection_items = collections['items']
            print(f"✓ Successfully listed {collections.get('count', len(collection_items))} collections")
        elif isinstance(collections, list):
            # This is a list of collections (legacy format)
            collection_items = collections
            print(f"✓ Successfully listed {len(collection_items)} collections")
        else:
            print(f"✗ Unexpected return type from list_collections: {type(collections).__name__}")
            
        if collection_items:
            first_coll = collection_items[0]
            if isinstance(first_coll, dict):
                print(f"   - First collection: {first_coll.get('name', 'Unnamed')} (ID: {first_coll.get('id', '?')})")
    except Exception as e:
        print(f"✗ Error in list_collections: {e}")
    
    # Test get_collection if we have any collections
    coll_id = None
    if collection_items:
        first_coll = collection_items[0]
        if isinstance(first_coll, dict):
            coll_id = first_coll.get('id')
        
    if coll_id:
        print(f"\n5. Testing get_collection with ID: {coll_id}")
        try:
            collection = get_collection(coll_id)
            if isinstance(collection, dict):
                print(f"✓ Successfully retrieved collection: {collection.get('name', 'Unnamed')}")
            else:
                print(f"✓ Successfully retrieved collection (type: {type(collection).__name__})")
        except Exception as e:
            print(f"✗ Error in get_collection: {e}")
    
    # Test get_usage_report_summary
    print("\n6. Testing get_usage_report_summary...")
    try:
        usage_summary = get_usage_report_summary()
        if usage_summary:
            print("✓ Successfully retrieved usage report summary")
            if 'total_requests' in usage_summary:
                print(f"   - Total requests: {usage_summary.get('total_requests', 0)}")
            if 'by_endpoint' in usage_summary:
                print(f"   - Endpoints tracked: {len(usage_summary.get('by_endpoint', {}))}")
    except Exception as e:
        print(f"✗ Error in get_usage_report_summary: {e}")


async def test_async_api() -> None:
    """Test asynchronous API examples from README."""
    print("\nTesting asynchronous API examples...")
    
    # Test async_list_publications
    print("\n1. Testing async_list_publications...")
    try:
        publications = await async_list_publications(limit=2)
        if publications:
            print(f"✓ Successfully listed {len(publications.get('items', []))} publications")
            print(f"   - Total count: {publications.get('count', 0)}")
            if publications.get('items'):
                first_pub = publications['items'][0]
                print(f"   - First publication: {first_pub.get('data', {}).get('title', 'Untitled')}")
    except Exception as e:
        print(f"✗ Error in async_list_publications: {e}")
    
    # Test async_get_publication if we have any publications
    if 'publications' in locals() and publications and publications.get('items'):
        pub_id = publications['items'][0]['uuid'] if publications['items'] and 'uuid' in publications['items'][0] else None
        if pub_id:
            print(f"\n2. Testing async_get_publication with ID: {pub_id}")
            try:
                publication: Publication = await async_get_publication(pub_id)
                print(f"✓ Successfully retrieved publication: {publication.get('data', {}).get('title', 'Untitled')}")
            except Exception as e:
                print(f"✗ Error in async_get_publication: {e}")
        else:
            print("\n2. Skipping async_get_publication test - no valid publication ID found")
    
    # Test async_search_publications
    print("\n3. Testing async_search_publications...")
    try:
        search_response = await async_search_publications("test")
        items = search_response.get('items', [])
        print(f"✓ Search returned {len(items)} results")
        if items and isinstance(items[0], dict):
            print(f"   - First result: {items[0].get('omnipub_title', 'Untitled')}")
    except Exception as e:
        print(f"✗ Error in async_search_publications: {e}")
    
    # Test async_list_collections
    print("\n4. Testing async_list_collections...")
    try:
        collections: CollectionsResponse = await async_list_collections(limit=2)
        print(f"Collections response type: {type(collections).__name__}")
        if hasattr(collections, 'get'):
            print(f"Collections keys: {list(collections.keys())}")
        if collections and 'items' in collections:
            print(f"✓ Successfully listed {len(collections['items'])} collections")
            if collections['items']:
                print(f"Items type: {type(collections['items']).__name__}")
                if hasattr(collections['items'], '__getitem__') and len(collections['items']) > 0:
                    coll = collections['items'][0]
                    print(f"First item type: {type(coll).__name__}")
                    if hasattr(coll, 'get'):
                        print(f"   - First collection: {coll.get('name', 'Unnamed')} (ID: {coll.get('id', '?')})")
                    else:
                        print(f"   - First collection (no 'get' method): {coll}")
    except Exception as e:
        print(f"✗ Error in async_list_collections: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
    
    # Test async_get_collection if we have any collections
    if 'collections' in locals() and collections and collections.get('items'):
        try:
            coll_id = collections['items'][0]['id']
            print(f"\n5. Testing async_get_collection with ID: {coll_id}")
            try:
                collection = await async_get_collection(coll_id)
                print(f"✓ Successfully retrieved collection: {collection.get('name', 'Unnamed')}")
                print(f"Collection type: {type(collection).__name__}")
                print(f"Collection keys: {list(collection.keys()) if hasattr(collection, 'keys') else 'N/A'}")
            except Exception as e:
                print(f"✗ Error in async_get_collection: {e}")
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
        except Exception as e:
            print(f"✗ Error preparing to test async_get_collection: {e}")
    
    # Test get_usage_report_summary (synchronous)
    print("\n6. Testing get_usage_report_summary (synchronous)...")
    try:
        usage = get_usage_report_summary()
        if usage:
            print("✓ Successfully retrieved usage report summary")
            if 'total_requests' in usage:
                print(f"   - Total requests: {usage.get('total_requests', 0)}")
            if 'by_endpoint' in usage:
                print(f"   - Endpoints tracked: {len(usage.get('by_endpoint', {}))}")
    except Exception as e:
        print(f"✗ Error in get_usage_report_summary: {e}")


def main() -> None:
    """Run all tests."""
    # Test synchronous API
    test_sync_api()
    
    # Test asynchronous API
    import asyncio
    asyncio.run(test_async_api())


def test_cli_commands() -> None:
    """Test CLI commands from README."""
    print("\nTesting CLI commands...")
    commands = [
        "python -m cashmere_client list-tools",
        "python -m cashmere_client list-resources",
        'python -m cashmere_client search "test"',
        "python -m cashmere_client list-publications --limit 2",
        "python -m cashmere_client list-collections --limit 2",
        "python -m cashmere_client usage",
    ]
    
    for cmd in commands:
        print(f"\nTesting command: {cmd}")
        try:
            result = os.popen(cmd).read()
            print("✓ Command executed successfully")
            if result.strip():
                print(f"   Output: {result.strip()[:100]}..." if len(result) > 100 else f"   Output: {result.strip()}")
            else:
                print("   No output")
        except Exception as e:
            print(f"✗ Error executing command: {e}")


if __name__ == "__main__":
    main()
