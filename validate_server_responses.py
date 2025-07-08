import json
import logging
import random
import traceback

import cashmere_client
import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)


class Settings(BaseSettings):
    SLACK_WEBHOOK_URL: str = ""
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

settings = Settings()


def send_slack_message(message: str):
    if not settings.SLACK_WEBHOOK_URL:
        logging.info("Not alerting via slack")
        return
    try:
        response = httpx.post(
            settings.SLACK_WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            json={
                "text": "{}\n{}".format(
                    ":rotating_light: *MCP Server Validation Error* :rotating_light:",
                    message,
                ),
            },
        )
        logging.info(response)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to send Slack message: {e}")


def get_query():
    try:
        with open("sample_search_queries.json") as f:
            query_pool = json.load(f)["search_queries"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logging.warning(f"Warning: Could not load sample queries: {e}. Using fallback.")
        query_pool = [f"What's the good word on footbal games?"]
    return random.choice(query_pool)


def test_call(func, *args, **kwargs):
    try:
        logging.info(f"{func.__name__} {args} {kwargs}")
        result = func(*args, **kwargs)
        logging.info(f"{func.__name__} succeeded")
        return result
    except Exception as e:
        tb = traceback.format_exc()
        msg = f"Function {func.__name__} {args} {kwargs} failed with error: {e}\nTraceback:\n{tb}"
        logging.error(msg)
        send_slack_message(msg)
        exit(1)


def main():
    test_call(cashmere_client.list_tools)
    test_call(cashmere_client.list_resources)
    test_call(cashmere_client.search_publications, query=get_query())
    collections_res = test_call(cashmere_client.list_collections, limit=10, offset=0)
    collection_ids = [item['id'] for item in collections_res['items']] # type: ignore
    test_call(cashmere_client.get_collection, random.choice(collection_ids))
    publications_res = test_call(cashmere_client.list_publications, limit=10, offset=0)
    publication_uuids = [item['uuid'] for item in publications_res['items']] # type: ignore
    test_call(cashmere_client.get_publication, random.choice(publication_uuids))
    test_call(cashmere_client.get_usage_report_summary)


if __name__ == "__main__":
    main()
