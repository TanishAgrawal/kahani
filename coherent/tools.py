import os
import json
from parallel import Parallel
from dotenv import load_dotenv

load_dotenv()

def search_fact(queries: list[str]) -> list[dict]:
    """Searches the web and list sources along with a summary

    Args:
        queries (list[str]): The exact list of questions/topics which need to be searched

    Returns:
        list: A list of dictionary containing excerpt and url 

    """
    client = Parallel(api_key=os.getenv("PARALLEL_API_KEY"))
    search = client.search(
    objective="Find out if the following search queries are true or not (dates, chronology, facts).",
    search_queries=queries,
    advanced_settings={"max_results":10}
    )

    final = []

    for result in search.results:
        buffer = {"url":result.url, "excerpt": result.excerpts}
        final.append(buffer)

    return final