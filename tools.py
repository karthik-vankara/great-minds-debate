import numexpr
import wikipedia
from langchain_core.tools import tool


@tool
def wikipedia_search(query: str) -> str:
    """Search Wikipedia for a topic and return a concise summary. Use this to cite real facts, historical events, or scientific data during a debate."""
    try:
        results = wikipedia.search(query, results=5)
        if not results:
            return f"No Wikipedia results found for '{query}'."
        # Try each search result until one works
        for title in results:
            try:
                return wikipedia.summary(title, sentences=3, auto_suggest=False)
            except wikipedia.DisambiguationError:
                continue
            except wikipedia.PageError:
                continue
        return f"No Wikipedia page found for '{query}'."
    except Exception as e:
        return f"Wikipedia search failed: {e}"


@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression and return the result. Use this for statistics, comparisons, or any numerical computation during a debate."""
    try:
        result = numexpr.evaluate(expression).item()
        return str(result)
    except Exception as e:
        return f"Calculation error: {e}"


DEBATE_TOOLS = [wikipedia_search, calculator]
