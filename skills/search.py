"""search.py - Web search skill module.

Provides a simple wrapper around a web search API. In a real implementation you would integrate
with a search provider (e.g., Bing, Google Custom Search). Here we expose a stub function
`web_search(query: str) -> list[str]` that returns a list of dummy URLs for demonstration.
"""


def web_search(query: str) -> list[str]:
    """Return a list of dummy search result URLs for the given query.

    Args:
        query: The search query string.
    Returns:
        A list of URL strings representing search results.
    """
    # Placeholder implementation – replace with real API call as needed.
    return [
        f"https://example.com/search?q={query.replace(' ', '+')}&page=1",
        f"https://example.com/search?q={query.replace(' ', '+')}&page=2",
        f"https://example.com/search?q={query.replace(' ', '+')}&page=3",
    ]
