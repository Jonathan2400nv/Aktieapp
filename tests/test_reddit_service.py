import pytest
from unittest.mock import patch, MagicMock


def _make_post(title, score, num_comments, subreddit_name):
    post = MagicMock()
    post.title = title
    post.score = score
    post.num_comments = num_comments
    post.subreddit.display_name = subreddit_name
    return post


class TestFetchHotPosts:
    def test_returns_list_of_dicts_with_correct_keys(self):
        from services.reddit_service import fetch_hot_posts
        mock_post = _make_post("AAPL moon", 5000, 300, "wallstreetbets")
        mock_reddit = MagicMock()
        mock_reddit.subreddit.return_value.hot.return_value = [mock_post]
        with patch('praw.Reddit', return_value=mock_reddit):
            result = fetch_hot_posts()
        assert isinstance(result, list)
        assert len(result) > 0
        assert {'title', 'score', 'comments', 'subreddit'} <= result[0].keys()

    def test_collects_from_multiple_subreddits(self):
        from services.reddit_service import fetch_hot_posts
        mock_post = _make_post("Test", 100, 10, "stocks")
        mock_reddit = MagicMock()
        mock_reddit.subreddit.return_value.hot.return_value = [mock_post]
        with patch('praw.Reddit', return_value=mock_reddit):
            result = fetch_hot_posts(subreddits=("wallstreetbets", "stocks"), limit=5)
        assert len(result) == 2

    def test_returns_none_on_exception(self):
        from services.reddit_service import fetch_hot_posts
        with patch('praw.Reddit', side_effect=Exception("auth error")):
            result = fetch_hot_posts()
        assert result is None
