import pytest
from unittest.mock import patch, MagicMock

SAMPLE_POSTS = [
    {"title": "AAPL earnings beat", "score": 5000, "subreddit": "stocks"},
    {"title": "GME squeeze incoming", "score": 8000, "subreddit": "wallstreetbets"},
]


class TestGetRedditSummary:
    def test_returns_string_on_success(self):
        from services.claude_service import get_reddit_summary
        mock_client = MagicMock()
        mock_client.messages.create.return_value.content = [MagicMock(text="Resumé på dansk.")]
        with patch('anthropic.Anthropic', return_value=mock_client):
            with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
                result = get_reddit_summary(SAMPLE_POSTS)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_none_when_no_api_key(self):
        from services.claude_service import get_reddit_summary
        with patch.dict('os.environ', {}, clear=True):
            result = get_reddit_summary(SAMPLE_POSTS)
        assert result is None

    def test_returns_none_on_api_exception(self):
        from services.claude_service import get_reddit_summary
        with patch('anthropic.Anthropic') as mock_cls:
            mock_cls.return_value.messages.create.side_effect = Exception("rate limit")
            with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
                result = get_reddit_summary(SAMPLE_POSTS)
        assert result is None

    def test_returns_none_on_empty_posts(self):
        from services.claude_service import get_reddit_summary
        result = get_reddit_summary([])
        assert result is None
