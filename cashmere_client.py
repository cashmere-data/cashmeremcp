import asyncio
import json as pyjson
import random
import sys
import time
from typing import Optional

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
    CASHMERE_API_KEY: Optional[str] = None
    CASHMERE_MCP_SERVER_URL: str
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")


settings = Settings()


def create_authenticated_client():
    client_kwargs = {}
    auth_token = settings.CASHMERE_API_KEY
    if auth_token:
        client_kwargs["auth"] = BearerAuth(auth_token)
    return Client(
        settings.CASHMERE_MCP_SERVER_URL,
        **client_kwargs,
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


async def search_publications(
    query: str, external_ids: str | list[str] | None = None
) -> SearchPublicationsResponse:
    client = create_authenticated_client()
    async with client:
        publications = await client.call_tool(
            "search_publications", {"query": query, "external_ids": external_ids}
        )
        publications = parse_json_content(publications)
        print(
            f"[search_publications] Publications: {len(publications[0]) if publications else 0}"
        )
        if not isinstance(publications, list):
            raise ValueError("Unexpected response format from search_publications")
        return publications[0] if publications else None


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
        return publications[0] if publications else None


async def get_publication(publication_id: str) -> Publication:
    client = create_authenticated_client()
    async with client:
        publication = await client.call_tool(
            "get_publication", {"publication_id": publication_id}
        )
        publication = parse_json_content(publication)
        return publication[0] if publication else None


async def list_collections(
    limit: int | None = None, offset: int | None = None
) -> CollectionsResponse:
    client = create_authenticated_client()
    async with client:
        collections = await client.call_tool(
            "list_collections", {"limit": limit, "offset": offset}
        )
        collections = parse_json_content(collections)
        return collections[0] if collections else None


async def get_collection(collection_id: int) -> Collection:
    client = create_authenticated_client()
    async with client:
        collection = await client.call_tool(
            "get_collection", {"collection_id": collection_id}
        )
        collection = parse_json_content(collection)
        return collection[0] if collection else None


async def get_usage_report_summary(external_ids: str | list[str] | None = None):
    client = create_authenticated_client()
    async with client:
        usage_report = await client.call_tool(
            "get_usage_report_summary", {"external_ids": external_ids}
        )
        usage_report = parse_json_content(usage_report)
        return usage_report[0] if usage_report else None


async def test_all_tools():
    start_time = time.time()
    user_query = "How should I do marketing in the twenty-first century?"
    external_id = "test_user_id"

    # Time search_publications
    search_start = time.time()
    matched_publications = await search_publications(user_query, [external_id])
    search_elapsed = time.time() - search_start
    print(
        f"[search_publications] found {len(matched_publications) if matched_publications else 0} publications in {search_elapsed:.2f} seconds"
    )

    # Time list_collections
    list_collections_start = time.time()
    collections = await list_collections()
    list_collections_elapsed = time.time() - list_collections_start
    print(
        f"[list_collections] found {collections['count']} collections in {list_collections_elapsed:.2f} seconds"
    )

    if not collections.get("items"):
        print("No collections found, cannot proceed with remaining tests")
        return
    collection_id = [c["id"] for c in collections["items"] if c["pubs_count"] > 0][0]
    if not collection_id:
        print(
            "No collections with publications found, cannot proceed with remaining tests"
        )
        return

    collection_start = time.time()
    collection = await get_collection(collection_id)
    collection_elapsed = time.time() - collection_start
    print(
        f"[get_collection] {collection_id} {collection['name']} retrieved in {collection_elapsed:.2f} seconds"
    )

    # Time list_publications
    list_pubs_start = time.time()
    publications = await list_publications(collection_id=collection_id)
    list_pubs_elapsed = time.time() - list_pubs_start
    print(
        f"[list_publications] found {publications['count'] if publications else 0} publications in {list_pubs_elapsed:.2f} seconds"
    )

    if not publications or not publications.get("items"):
        print("No publications found, cannot proceed with get_publication test")
        return

    # Time get_publication
    get_pub_start = time.time()
    await get_publication(publications["items"][0]["uuid"])
    get_pub_elapsed = time.time() - get_pub_start
    print(f"[get_publication] retrieved in {get_pub_elapsed:.2f} seconds")

    total_elapsed = time.time() - start_time
    print(f"\nTotal test execution time: {total_elapsed:.2f} seconds")

    # Time get_usage_report
    usage_report_start = time.time()
    usage_report = await get_usage_report_summary(external_ids=[external_id])
    usage_report_elapsed = time.time() - usage_report_start
    print(f"[get_usage_report] retrieved in {usage_report_elapsed:.2f} seconds")
    print(f"usage_report: {usage_report}")


async def test_requests_per_second(
    duration_seconds: int = 10, max_retries: int = 3, max_concurrent: int = 50
):
    """Test the requests per second that the search_publications tool can handle.

    Args:
        duration_seconds: How long to run the test for (default: 10 seconds)
        max_retries: Maximum number of retry attempts for failed requests (default: 3)
        max_concurrent: Maximum number of concurrent requests (default: 50)

    Returns:
        dict: Statistics about the test run
    """
    stats = {
        "total_requests": 0,
        "successful_requests": 0,
        "failed_requests": 0,
        "error_counts": {},
        "latencies": [],
        "start_time": time.time(),
        "active_requests": 0,
        "max_concurrent": 0,
    }

    # Semaphore to limit concurrency
    semaphore = asyncio.Semaphore(max_concurrent)

    try:
        with open("sample_search_queries.json") as f:
            query_pool = pyjson.load(f)["search_queries"]
    except (FileNotFoundError, pyjson.JSONDecodeError, KeyError) as e:
        print(f"Warning: Could not load sample queries: {e}. Using fallback queries.")
        query_pool = [f"query {i}" for i in range(100)]

    async def make_request():
        nonlocal stats
        query = random.choice(query_pool)
        retries = 0
        last_error = None

        try:
            async with semaphore:
                stats["active_requests"] += 1
                stats["max_concurrent"] = max(
                    stats["max_concurrent"], stats["active_requests"]
                )

                while retries <= max_retries:
                    try:
                        request_start = time.time()
                        await search_publications(query)
                        latency = time.time() - request_start
                        stats["latencies"].append(latency)
                        stats["successful_requests"] += 1
                        return
                    except Exception as e:
                        last_error = e
                        retries += 1
                        if retries <= max_retries:
                            # Exponential backoff: 100ms, 200ms, 400ms, etc.
                            await asyncio.sleep(0.1 * (2 ** (retries - 1)))
                        continue

                # If we get here, all retries failed
                stats["failed_requests"] += 1
                error_name = type(last_error).__name__
                stats["error_counts"][error_name] = (
                    stats["error_counts"].get(error_name, 0) + 1
                )
                return last_error
        finally:
            stats["active_requests"] = max(0, stats["active_requests"] - 1)

    # Run the test for the specified duration
    print(
        f"Starting test for {duration_seconds} seconds with max {max_concurrent} concurrent requests..."
    )
    start_time = time.time()
    end_time = start_time + duration_seconds

    tasks = set()
    try:
        while time.time() < end_time:
            # Clean up completed tasks
            done_tasks = {t for t in tasks if t.done()}
            tasks -= done_tasks

            # Check if we can add more tasks
            if len(tasks) < max_concurrent * 2:  # Keep some buffer
                stats["total_requests"] += 1
                task = asyncio.create_task(make_request())
                tasks.add(task)
                task.add_done_callback(tasks.discard)

            # Small sleep to prevent busy waiting
            await asyncio.sleep(0.001)

        # Wait for remaining tasks to complete with a timeout and process results
        if tasks:
            done, _ = await asyncio.wait(tasks, timeout=10.0)
            # Process any remaining errors from completed tasks
            for task in done:
                if task.done() and not task.cancelled():
                    try:
                        await task
                    except Exception:
                        # These errors were already counted in make_request
                        pass

    except asyncio.CancelledError:
        # Clean up any remaining tasks
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.wait(tasks, timeout=5.0)
        raise

    # Print summary
    elapsed = time.time() - start_time
    rps = stats["successful_requests"] / elapsed if elapsed > 0 else 0

    print(f"\nTest completed in {elapsed:.2f} seconds")
    print(f"Total requests: {stats['total_requests']}")
    print(f"Successful requests: {stats['successful_requests']}")
    print(f"Failed requests: {stats['failed_requests']}")
    print(f"Max concurrent requests: {stats['max_concurrent']}")
    print(
        f"Success rate: {(stats['successful_requests'] / stats['total_requests'] * 100):.2f}%"
        if stats["total_requests"] > 0
        else "No requests made"
    )
    print(f"Requests per second: {rps:.2f}")

    if stats["latencies"]:
        print("\nLatency (ms):")
        print(f"  Min: {min(stats['latencies']) * 1000:.2f}")
        print(
            f"  Avg: {(sum(stats['latencies']) / len(stats['latencies'])) * 1000:.2f}"
        )
        print(f"  Max: {max(stats['latencies']) * 1000:.2f}")

        # Calculate percentiles if we have enough data
        if len(stats["latencies"]) >= 10:
            sorted_latencies = sorted(stats["latencies"])
            p50 = sorted_latencies[int(len(sorted_latencies) * 0.5)]
            p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
            p99 = sorted_latencies[int(len(sorted_latencies) * 0.99)]
            print(f"  p50: {p50 * 1000:.2f}ms")
            print(f"  p95: {p95 * 1000:.2f}ms")
            print(f"  p99: {p99 * 1000:.2f}ms")

    if stats["error_counts"]:
        print("\nErrors encountered:")
        for error, count in sorted(
            stats["error_counts"].items(), key=lambda x: x[1], reverse=True
        ):
            print(
                f"  {error}: {count} ({(count / stats['total_requests'] * 100):.1f}%)"
            )

    return stats


async def load_test(
    num_requests: int = 2000, concurrency: int | None = None, max_retries: int = 3
) -> None:
    """
    Run a load test with the specified number of requests and concurrency.

    Args:
        num_requests: Total number of requests to make (default: 2000)
        concurrency: Maximum number of concurrent requests (default: min(100, num_requests))
        max_retries: Maximum number of retry attempts for failed requests (default: 3)
    """
    concurrency = min(concurrency or num_requests, 100)  # Cap concurrency at 100

    stats = {
        "total_requests": 0,
        "successful_requests": 0,
        "failed_requests": 0,
        "error_counts": {},
        "latencies": [],
        "start_time": time.time(),
        "active_requests": 0,
        "max_concurrent": 0,
    }

    # Semaphore to limit concurrency
    semaphore = asyncio.Semaphore(concurrency)

    try:
        with open("sample_search_queries.json") as f:
            query_pool = pyjson.load(f)["search_queries"]
    except (FileNotFoundError, pyjson.JSONDecodeError, KeyError) as e:
        print(f"Warning: Could not load sample queries: {e}. Using fallback queries.")
        query_pool = [f"query {i}" for i in range(100)]

    async def make_request():
        nonlocal stats
        query = random.choice(query_pool)
        retries = 0
        last_error = None

        try:
            async with semaphore:
                stats["active_requests"] += 1
                stats["max_concurrent"] = max(
                    stats["max_concurrent"], stats["active_requests"]
                )

                while retries <= max_retries:
                    try:
                        request_start = time.time()
                        await search_publications(query)
                        latency = time.time() - request_start
                        stats["latencies"].append(latency)
                        stats["successful_requests"] += 1
                        return
                    except Exception as e:
                        last_error = e
                        retries += 1
                        if retries <= max_retries:
                            # Exponential backoff: 100ms, 200ms, 400ms, etc.
                            await asyncio.sleep(0.1 * (2 ** (retries - 1)))
                        continue

                # If we get here, all retries failed
                stats["failed_requests"] += 1
                error_name = type(last_error).__name__
                stats["error_counts"][error_name] = (
                    stats["error_counts"].get(error_name, 0) + 1
                )
                return last_error
        finally:
            stats["active_requests"] = max(0, stats["active_requests"] - 1)

    # Create and manage tasks with controlled concurrency
    tasks = set()
    stats["start_time"] = time.time()

    try:
        # Start initial batch of tasks
        for _ in range(min(concurrency * 2, num_requests)):
            if stats["total_requests"] >= num_requests:
                break
            stats["total_requests"] += 1
            task = asyncio.create_task(make_request())
            tasks.add(task)
            task.add_done_callback(tasks.discard)

        # Process remaining tasks as others complete
        while stats["total_requests"] < num_requests and tasks:
            # Wait for at least one task to complete
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )

            # Start new tasks to replace completed ones
            for _ in range(len(done)):
                if stats["total_requests"] < num_requests:
                    stats["total_requests"] += 1
                    task = asyncio.create_task(make_request())
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)

        # Wait for all remaining tasks to complete and process results
        if tasks:
            done, _ = await asyncio.wait(tasks, timeout=30.0)
            # Process any remaining errors from completed tasks
            for task in done:
                if task.done() and not task.cancelled():
                    try:
                        await task
                    except Exception:
                        # These errors were already counted in make_request
                        pass

    except asyncio.CancelledError:
        # Clean up any remaining tasks
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.wait(tasks, timeout=5.0)
        raise

    total_time = time.time() - stats["start_time"]

    # Print results
    print(f"\n[load_test] Results (completed in {total_time:.2f} seconds):")
    print(f"  Total requests: {stats['total_requests']}")
    print(
        f"  Successful: {stats['successful_requests']} ({(stats['successful_requests'] / stats['total_requests'] * 100):.1f}%)"
    )
    print(
        f"  Failed: {stats['failed_requests']} ({(stats['failed_requests'] / stats['total_requests'] * 100):.1f}%)"
    )
    print(f"  Max concurrent requests: {stats['max_concurrent']}")

    if stats["error_counts"]:
        print("\n  Error breakdown:")
        for error, count in sorted(
            stats["error_counts"].items(), key=lambda x: x[1], reverse=True
        ):
            print(
                f"    {error}: {count} ({(count / stats['total_requests'] * 100):.1f}%)"
            )

    if stats["latencies"]:
        rps = len(stats["latencies"]) / total_time
        sorted_latencies = sorted(stats["latencies"])
        p50 = sorted_latencies[int(len(sorted_latencies) * 0.5)] * 1000
        p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)] * 1000
        p99 = (
            sorted_latencies[int(len(sorted_latencies) * 0.99)] * 1000
            if len(sorted_latencies) >= 100
            else 0.0
        )

        print("\n  Successful request metrics:")
        print(f"    Requests per second: {rps:.2f}")
        print(f"    Latency (p50): {p50:.2f}ms")
        print(f"    Latency (p95): {p95:.2f}ms")
        if p99 > 0:
            print(f"    Latency (p99): {p99:.2f}ms")


async def test_tool(
    tool: str, collection_id: int | None, publication_id: str | None, query: str
):
    response = None
    if tool == "search_publications":
        if query is None:
            raise ValueError("query is required for search_publications")
        response = await search_publications(query, None)
    elif tool == "list_publications":
        response = await list_publications(collection_id)
    elif tool == "get_publication":
        if publication_id is None:
            raise ValueError("publication_id is required for get_publication")
        response = await get_publication(publication_id)
    elif tool == "list_collections":
        response = await list_collections()
    elif tool == "get_collection":
        if collection_id is None:
            raise ValueError("collection_id is required for get_collection")
        response = await get_collection(collection_id)
    elif tool == "get_usage_report_summary":
        response = await get_usage_report_summary(None)
    else:
        raise ValueError(f"Unknown tool: {tool}")
    return print(f"[test_tool] {tool}: {pyjson.dumps(response, indent=2)}")


# Entrypoint for command-line usage
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Cashmere MCP client utilities and load‑testing helper"
    )
    parser.add_argument(
        "--mode",
        choices=[
            "load",
            "rps",
            "test_all",
            "list_tools",
            "list_resources",
            "get_usage_report_summary",
        ],
        help="Which helper to run (default: load)",
    )
    parser.add_argument(
        "--tool",
        choices=[
            "search_publications",
            "list_publications",
            "get_publication",
            "list_collections",
            "get_collection",
        ],
        help="Which tool to test (default: search_publications)",
    )
    parser.add_argument(
        "--collection_id",
        type=int,
        default=None,
        help="Collection ID to use for list_publications and get_publication tests",
    )
    parser.add_argument(
        "--publication_id",
        type=str,
        default=None,
        help="Publication ID to use for get_publication tests",
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Query to use for search_publications tests",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=2000,
        help="Number of requests to send when --mode load is selected",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Max concurrent requests (defaults to --requests)",
    )
    args = parser.parse_args()

    if args.mode == "load":
        asyncio.run(load_test(num_requests=args.requests, concurrency=args.concurrency))
    elif args.mode == "rps":
        asyncio.run(test_requests_per_second())
    elif args.mode == "test_all":
        asyncio.run(test_all_tools())
    elif args.mode == "list_tools":
        asyncio.run(list_tools())
    elif args.mode == "list_resources":
        asyncio.run(list_resources())
    elif args.mode == "get_usage_report_summary":
        asyncio.run(get_usage_report_summary())
    elif args.tool:
        asyncio.run(
            test_tool(args.tool, args.collection_id, args.publication_id, args.query)
        )
    else:
        parser.print_help()
        sys.exit(1)
