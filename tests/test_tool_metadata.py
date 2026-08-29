from fastmcp import Client

from mcp_trendpulse import server


TOOL_SELECTION_MARKERS = {
    "get_news_by_keyword": ("free-form", "get_news_by_topic"),
    "get_news_by_location": ("place-focused", "get_news_by_keyword"),
    "get_news_by_topic": ("topic category", "get_news_by_keyword"),
    "get_top_news": ("general headline", "without a keyword"),
    "get_trending_terms": ("trending now", "get_trends"),
    "get_trends": ("historical", "not absolute search volume"),
    "get_growth": ("momentum", "get_trends"),
    "get_ranked_trends": ("ranked", "get_top_trends"),
    "get_top_trends": ("current topic discovery", "get_ranked_trends"),
    "get_news_by_site": ("one publisher", "get_news_by_keyword"),
    "get_article_content": ("already have an article url", "do not use it for discovery"),
    "get_interest_by_region": ("geographic", "get_trends"),
    "get_related_queries": ("literal search queries", "get_related_topics"),
    "get_related_topics": ("topic entities", "get_related_queries"),
    "get_suggestions": ("autocomplete", "get_related_queries"),
    "get_categories": ("category ids", "do not guess"),
}


async def test_community_tool_metadata_is_explicit_and_actionable():
    async with Client(server.mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    assert set(tools) == set(TOOL_SELECTION_MARKERS)

    for tool_name, required_phrases in TOOL_SELECTION_MARKERS.items():
        tool = tools[tool_name]
        assert tool.description
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.openWorldHint is True
        assert tool.annotations.destructiveHint is False

        description = tool.description.lower()
        for phrase in required_phrases:
            assert phrase in description
