# Cashmere MCP Client

A Python client for interacting with the Cashmere MCP API, providing both synchronous and asynchronous interfaces for accessing publications, collections, and usage data.

## Features

- **Publication Management**: Search, list, and retrieve publication details
- **Collection Management**: List and retrieve collection information
- **Usage Reporting**: Get usage statistics and reports
- **Dual Interfaces**: Both synchronous and asynchronous API support
- **Command-Line Interface**: Easy-to-use CLI for common operations

## Installation

### Using pip (recommended)

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

2. Install the package and its dependencies:
   ```bash
   pip install -e .
   ```

   For development with all optional dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

### For Development

1. Clone the repository and set up the development environment:
   ```bash
   git clone https://github.com/yourusername/cashmeremcp.git
   cd cashmeremcp
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   pip install -r requirements-dev.txt
   ```

2. Install pre-commit hooks (optional but recommended):
   ```bash
   pre-commit install
   ```

## Configuration

Create a `.env.local` file in your project directory with your API credentials:
```
CASHMERE_API_KEY=your_api_key_here
CASHMERE_MCP_SERVER_URL=your_server_url_here
```

## Usage

### Python API

```python
from cashmere_client import (
    list_publications,
    get_publication,
    search_publications,
    list_collections,
    get_collection,
    get_usage_report_summary
)

# List publications
publications = list_publications(limit=10)
print(f"Found {publications['count']} publications")

# Get a specific publication
publication = get_publication("publication-uuid-here")
print(f"Title: {publication['data'].get('title')}")

# Search publications
results = search_publications("search query")
for result in results:
    print(f"- {result['omnipub_title']}")

# List collections
collections = list_collections()
for collection in collections['items']:
    print(f"- {collection['name']} (ID: {collection['id']})")

# Get usage report
usage = get_usage_report_summary()
print(f"Total usage: {usage}")
```

### Asynchronous API

```python
import asyncio
from cashmere_client import (
    async_list_publications,
    async_get_publication,
    async_search_publications
)

async def main():
    # List publications asynchronously
    publications = await async_list_publications(limit=5)
    print(f"Found {publications['count']} publications")

    # Get publication asynchronously
    publication = await async_get_publication("publication-uuid-here")
    print(f"Title: {publication['data'].get('title')}")

    # Search asynchronously
    results = await async_search_publications("search query")
    for result in results:
        print(f"- {result['omnipub_title']}")

asyncio.run(main())
```

### Command Line Interface

The package includes a command-line interface for common operations:

```bash
# List available tools
python -m cashmere_client list-tools

# List available resources
python -m cashmere_client list-resources

# Search publications
python -m cashmere_client search "your search query" --external-ids id1 id2

# List publications
python -m cashmere_client list-publications --limit 10 --offset 0

# Get a specific publication
python -m cashmere_client get-publication publication-uuid-here

# List collections
python -m cashmere_client list-collections --limit 10

# Get a specific collection
python -m cashmere_client get-collection 123

# Get usage report
python -m cashmere_client usage --external-ids id1 id2
```

## Data Models

The client uses typed dictionaries to represent API responses. The main models are:

- `SearchPublicationItem`: Represents a search result item
- `Publication`: Contains detailed publication information
- `PublicationDataFull`: Full publication data including metadata
- `Collection`: Collection information
- `CollectionsResponse`: Paginated collection response
- `PublicationsResponse`: Paginated publications response

## Error Handling

The client raises appropriate exceptions for different error conditions:

- `ValueError`: For invalid input parameters
- `RuntimeError`: For API call failures
- `KeyError`: For missing required fields in responses

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

Apache 2.0
