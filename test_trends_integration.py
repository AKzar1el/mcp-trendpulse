import asyncio
import sys
from mcp_trendpulse.news import get_trends, get_growth, get_ranked_trends, get_top_trends

async def main():
    print("==================================================")
    print("Testing get_trends for 'artificial intelligence'...")
    try:
        trends = await get_trends(keyword="artificial intelligence", source="google search", data_mode="weekly")
        print(f"Success! Fetched {len(trends)} historical data points.")
        if trends:
            print("Sample data points:")
            for pt in trends[:5]:
                print(f"  Date: {pt['date']}, Value: {pt['value']}")
    except Exception as e:
        print(f"Failed: {e}")

    print("\n==================================================")
    print("Testing get_growth for 'electric vehicles'...")
    try:
        growth = await get_growth(keyword="electric vehicles", source="google search", percent_growth=["3M", "1Y"])
        print(f"Success! Growth metrics: {growth}")
    except Exception as e:
        print(f"Failed: {e}")

    print("\n==================================================")
    print("Testing get_ranked_trends...")
    try:
        ranked = await get_ranked_trends(source="google search", sort="wow_pct_change", limit=5)
        print(f"Success! Fetched {len(ranked)} ranked trends.")
        if ranked:
            for item in ranked:
                print(f"  Keyword: {item['keyword']}, Volume: {item['volume']}, Growth: {item['growth_pct']}%")
    except Exception as e:
        print(f"Failed: {e}")

    print("\n==================================================")
    print("Testing get_top_trends...")
    try:
        top = await get_top_trends(type="Google Trends", limit=5)
        print(f"Success! Fetched {len(top)} top trends.")
        if top:
            for item in top:
                print(f"  Keyword: {item['keyword']}, Volume: {item['volume']}")
    except Exception as e:
        print(f"Failed: {e}")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(main())
