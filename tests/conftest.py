import sys
from unittest.mock import MagicMock

_st_mock = MagicMock()


def _noop_cache_data(*args, **kwargs):
    # Handles both @st.cache_data and @st.cache_data(ttl=...)
    if args and callable(args[0]):
        return args[0]
    return lambda f: f


_st_mock.cache_data = _noop_cache_data
_st_mock.secrets = {}
sys.modules['streamlit'] = _st_mock
