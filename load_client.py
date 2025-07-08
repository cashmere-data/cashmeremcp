import asyncio
import json
import random
import sys
import time

from cashmere_client import async_search_publications


# 3 handshakes, 1 tool/resource call, 1 cleanup
REQUESTS_PER_CALL = 5


async def test_requests_per_second(
    duration_seconds: int = 10, max_retries: int = 3, max_concurrent: int = 3
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
            query_pool = json.load(f)["search_queries"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
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
                        res = await async_search_publications(query)
                        print(
                            f"[search_publications] Query: {query} Publications: {len(res) if res else 0}"
                        )
                        latency = (time.time() - request_start) / REQUESTS_PER_CALL
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
                stats["total_requests"] += REQUESTS_PER_CALL
                task = asyncio.create_task(make_request())
                tasks.add(task)
                task.add_done_callback(tasks.discard)

            # Small sleep to prevent busy waiting
            await asyncio.sleep(0.001)

        # Wait for remaining tasks to complete with a timeout and process results
        if tasks:
            done, _ = await asyncio.wait(tasks, timeout=0.1)
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
            await asyncio.wait(tasks, timeout=0.1)
        raise

    # Print summary
    elapsed = time.time() - start_time
    rps = stats["total_requests"] / elapsed if elapsed > 0 else 0

    print(f"\nTest completed in {elapsed:.2f} seconds")
    print(f"Total requests: {stats['total_requests']}")
    print(f"Successful client calls: {stats['successful_requests']}")
    print(f"Failed client calls: {stats['failed_requests']}")
    print(f"Max concurrent client calls: {stats['max_concurrent']}")
    print(
        f"Success rate: {(stats['successful_requests'] / (stats['successful_requests'] + stats['failed_requests']) * 100):.2f}%"
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
    num_calls: int = 2000, concurrency: int | None = None, max_retries: int = 3
) -> None:
    """
    Run a load test with the specified number of requests and concurrency.

    Args:
        num_calls: Total number of client calls to make (default: 2000)
        concurrency: Maximum number of concurrent requests (default: min(100, num_requests))
        max_retries: Maximum number of retry attempts for failed requests (default: 3)
    """
    concurrency = min(concurrency or num_calls, 100)  # Cap concurrency at 100

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
            query_pool = json.load(f)["search_queries"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
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
                    print(f"[search initial] Query: {query}")
                    if retries > 0:
                        print(f"[retrying] Query: {query}, retry: {retries}")
                    try:
                        request_start = time.time()
                        res = await async_search_publications(query)
                        latency = (time.time() - request_start) / REQUESTS_PER_CALL
                        stats["latencies"].append(latency)
                        print(
                            f"[search_publications] Query: {query} Publications: {len(res) if res else 0} Latency: {latency * 1000:.2f}ms"
                        )
                        stats["successful_requests"] += 1
                        return
                    except Exception as e:
                        print(f"Exception: {e}")
                        raise
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
        for _ in range(min(concurrency * 2, num_calls)):
            if stats["total_requests"] >= num_calls * REQUESTS_PER_CALL:
                break
            stats["total_requests"] += REQUESTS_PER_CALL
            task = asyncio.create_task(make_request())
            tasks.add(task)
            task.add_done_callback(tasks.discard)

        # Process remaining tasks as others complete
        while stats["total_requests"] < num_calls * REQUESTS_PER_CALL and tasks:
            # Wait for at least one task to complete
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )

            # Start new tasks to replace completed ones
            for _ in range(len(done)):
                if stats["total_requests"] < num_calls * REQUESTS_PER_CALL:
                    stats["total_requests"] += REQUESTS_PER_CALL
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
        f"  Successful client calls: {stats['successful_requests']} ({(stats['successful_requests'] / stats['total_requests'] * REQUESTS_PER_CALL * 100):.1f}%)"
    )
    print(
        f"  Failed client calls: {stats['failed_requests']} ({(stats['failed_requests'] / stats['total_requests'] * REQUESTS_PER_CALL * 100):.1f}%)"
    )
    print(f"  Max concurrent client calls: {stats['max_concurrent']}")

    if stats["error_counts"]:
        print("\n  Error breakdown:")
        for error, count in sorted(
            stats["error_counts"].items(), key=lambda x: x[1], reverse=True
        ):
            print(
                f"    {error}: {count} ({(count / stats['total_requests'] * 100):.1f}%)"
            )

    if stats["latencies"]:
        rps = stats['total_requests'] / total_time
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


# Entrypoint for command-line usage
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Cashmere MCP load‑testing helper"
    )
    parser.add_argument(
        "--mode",
        choices=[
            "load",
            "rps",
        ],
        default="load",
        help="Which helper to run (default: load)",
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Query to use for search_publications tests",
    )
    parser.add_argument(
        "--calls",
        type=int,
        default=2000,
        help="Number of client calls to make when --mode load is selected",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Max concurrent requests",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Duration to run in seconds",
    )
    args = parser.parse_args()

    if args.mode == "load":
        asyncio.run(
            load_test(
                num_calls=args.calls,
                concurrency=args.concurrency,
            )
        )
    elif args.mode == "rps":
        asyncio.run(
            test_requests_per_second(
                duration_seconds=args.duration,
                max_concurrent=args.concurrency,
            )
        )
    else:
        parser.print_help()
        sys.exit(1)
