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
    # API key for a CustomApp whose tool_config has disabled/hidden tools and hidden_params.
    # Hidden-tool/param checks run only when this is set; primary CASHMERE_API_KEY keeps full validation.
    TOOL_CONFIG_API_KEY: str = ""
    # Same JSON shape as CustomApp.tool_config in the DB (see app repo). Used with TOOL_CONFIG_API_KEY:
    # disabled tools (enabled: false) must be absent from list_tools; for enabled tools, hidden_params
    # must be absent from inputSchema. Default "{}" skips these checks.
    TOOL_CONFIG: str = "{}"
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


def test_call(func, *args, extra_result_test = None, **kwargs):
    try:
        logging.info(f"{func.__name__} {args} {kwargs}")
        result = func(*args, **kwargs)
        logging.info(f"{func.__name__} succeeded")
        if extra_result_test:
            extra_result_test(result)
        return result
    except Exception as e:
        tb = traceback.format_exc()
        msg = f"Function {func.__name__} {args} {kwargs} failed with error: {e}\nTraceback:\n{tb}"
        logging.error(msg)
        send_slack_message(msg)
        exit(1)


def expectations_from_tool_config(
    tool_config: dict,
) -> tuple[list[str], dict[str, list[str]]]:
    """
    Derive expected disabled tool names and per-tool hidden params from DB-shaped tool_config.
    """
    disabled: list[str] = []
    hidden_by_tool: dict[str, list[str]] = {}
    for tool_name, cfg in tool_config.items():
        if not isinstance(cfg, dict):
            continue
        if not cfg.get("enabled", True):
            disabled.append(tool_name)
            continue
        hidden = cfg.get("hidden_params") or []
        if hidden:
            hidden_by_tool[tool_name] = list(hidden)
    return disabled, hidden_by_tool


def parse_tool_config_expectations(cfg_raw: str) -> tuple[list[str], dict[str, list[str]]]:
    parsed = json.loads(cfg_raw)
    if not isinstance(parsed, dict):
        raise ValueError("TOOL_CONFIG must be a JSON object")
    return expectations_from_tool_config(parsed)


def test_dynamic_descriptions(result):
    # Presence of this string means dynamic collections got applied and
    # returned by the list_tool call (and that list_tools is active)
    test_str_from_dynamic_descriptions = "This tool has access to the following collections"
    if test_str_from_dynamic_descriptions not in str(result):
        raise Exception("Failed to get dynamic descriptions")


def test_hidden_tools(tools: list[dict], expected_hidden: list[str]):
    """
    Make sure that tools configured as hidden are absent from list_tools.
    expected_hidden: ["tool_name1", "tool_name2", ...]
    """
    tool_names = {t["name"] for t in tools}
    for name in expected_hidden:
        if name in tool_names:
            raise Exception(
                f"Tool '{name}' should be hidden but appears in list_tools"
            )


def test_hidden_tool_params(tools: list[dict], expected_hidden: dict[str, list[str]]):
    """
    Make sure that params configured as hidden are absent from tool inputSchemas.
    expected_hidden: {"tool_name": ["param1", "param2"], ...}
    """
    tool_map = {t["name"]: t for t in tools}
    for tool_name, hidden_params in expected_hidden.items():
        if tool_name not in tool_map:
            raise Exception(f"Tool '{tool_name}' not found in tool list")
        schema = tool_map[tool_name].get("inputSchema") or {}
        props = schema.get("properties", {})
        required = schema.get("required", [])
        for param in hidden_params:
            if param in props:
                raise Exception(
                    f"Tool '{tool_name}': param '{param}' should be hidden but appears in inputSchema.properties"
                )
            if param in required:
                raise Exception(
                    f"Tool '{tool_name}': param '{param}' should be hidden but appears in inputSchema.required"
                )


def main():
    test_call(cashmere_client.list_tools, extra_result_test=test_dynamic_descriptions)
    if settings.TOOL_CONFIG_API_KEY:
        cfg_raw = (settings.TOOL_CONFIG or "").strip()
        if not cfg_raw or cfg_raw == "{}":
            logging.info(
                "TOOL_CONFIG_API_KEY set but TOOL_CONFIG empty; skipping tool_config list_tools checks"
            )
        else:
            expected_disabled, expected_hidden_params = test_call(
                parse_tool_config_expectations,
                cfg_raw,
            )
            if not expected_disabled and not expected_hidden_params:
                logging.info(
                    "TOOL_CONFIG has no disabled tools or hidden_params; skipping list_tools_with_key"
                )
            else:
                tool_config_tools = test_call(
                    cashmere_client.list_tools_with_key,
                    settings.TOOL_CONFIG_API_KEY,
                )
                if expected_disabled:
                    test_call(
                        test_hidden_tools,
                        tool_config_tools,
                        expected_disabled,
                    )
                if expected_hidden_params:
                    test_call(
                        test_hidden_tool_params,
                        tool_config_tools,
                        expected_hidden_params,
                    )
    else:
        logging.info(
            "TOOL_CONFIG_API_KEY not set; skipping tool_config checks "
            "(set it with TOOL_CONFIG to validate CustomApp.tool_config for a second app)"
        )
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
