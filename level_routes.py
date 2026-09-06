"""Test-only level slots that reuse existing gameplay scenarios."""


TEST_TO_CONTENT_LEVEL = {
    13: 6,
}

def get_test_content_level(test_level):
    try:
        level = int(test_level)
    except (TypeError, ValueError):
        return test_level
    return TEST_TO_CONTENT_LEVEL.get(level, level)
