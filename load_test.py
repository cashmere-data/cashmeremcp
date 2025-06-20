"""
Load testing script for Cashmere MCP search_publications API.

Usage:
    python load_test.py [--num-requests 2000] [--concurrency 50] [--max-retries 3]

This script will run a load test using queries from sample_search_queries.json.
"""

import asyncio
import json as pyjson
import random
import time
import argparse
from typing import Optional

from cashmeremcp.cashmere_client import async_search_publications


def parse_args():
    parser = argparse.ArgumentParser(description="Cashmere MCP Load Test")
    parser.add_argument("--num-requests", type=int, default=2000, help="Total number of requests to make")
    parser.add_argument("--concurrency", type=int, default=None, help="Maximum number of concurrent requests")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum number of retry attempts for failed requests")
    return parser.parse_args()


async def load_test(num_requests: int = 2000, concurrency: Optional[int] = None, max_retries: int = 3) -> None:
    """
    Run a load test with the specified number of requests and concurrency.
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
                        print(f"query: {query}")
                        await async_search_publications(query)
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


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        load_test(
            num_requests=args.num_requests,
            concurrency=args.concurrency,
            max_retries=args.max_retries,
        )
    )
