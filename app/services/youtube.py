"""
YouTube Data API v3 service.
Searches for exercise tutorial videos.
"""
import httpx
from app.config import settings

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


async def search_exercise_video(exercise_name: str, max_results: int = 1) -> list[dict]:
    """
    Search YouTube for an exercise tutorial.
    Returns list of {title, url, thumbnail} dicts.
    """
    if not settings.youtube_api_key:
        return []

    query = f"{exercise_name} exercise tutorial proper form"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            YOUTUBE_SEARCH_URL,
            params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "videoDuration": "short",
                "maxResults": max_results,
                "key": settings.youtube_api_key,
            },
        )
        if resp.status_code != 200:
            return []

        data = resp.json()
        results = []
        for item in data.get("items", []):
            video_id = item["id"].get("videoId", "")
            snippet = item.get("snippet", {})
            results.append({
                "title": snippet.get("title", exercise_name),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                "channel": snippet.get("channelTitle", ""),
            })
        return results


async def get_workout_videos(exercises: list[str]) -> dict[str, str]:
    """
    Get YouTube URLs for a list of exercise names.
    Returns dict: {exercise_name: youtube_url}
    """
    result = {}
    for exercise in exercises[:5]:  # limit to 5 to stay within quota
        videos = await search_exercise_video(exercise, max_results=1)
        if videos:
            result[exercise] = videos[0]["url"]
    return result
