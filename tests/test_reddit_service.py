import pytest
from unittest.mock import patch, MagicMock


def _make_response(subreddit_name, titles=("Test post",)):
    children = [
        {"data": {"title": t, "score": 100, "num_comments": 10, "subreddit": subreddit_name}}
        for t in titles
    ]
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": {"children": children}}
    mock_resp.raise_for_status.return_value = None
    return mock_resp


class TestFetchHotPosts:
    def test_returns_list_of_dicts_with_correct_keys(self):
        from services.reddit_service import fetch_hot_posts
        with patch('requests.get', return_value=_make_response("wallstreetbets", ["AAPL moon"])):
            result = fetch_hot_posts(subreddits=("wallstreetbets",))
        assert isinstance(result, list)
        assert len(result) > 0
        assert {'title', 'score', 'comments', 'subreddit'} <= result[0].keys()

    def test_collects_from_multiple_subreddits(self):
        from services.reddit_service import fetch_hot_posts
        with patch('requests.get', side_effect=[
            _make_response("wallstreetbets", ["Post A"]),
            _make_response("stocks", ["Post B"]),
        ]):
            result = fetch_hot_posts(subreddits=("wallstreetbets", "stocks"), limit=1)
        assert len(result) == 2

    def test_returns_none_on_exception(self):
        from services.reddit_service import fetch_hot_posts
        with patch('requests.get', side_effect=Exception("network error")):
            result = fetch_hot_posts()
        assert result is None
