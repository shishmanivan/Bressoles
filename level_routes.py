"""Map selector cards to stable scenario IDs used by data and saved runs."""


CAMPAIGN_TO_CONTENT_LEVEL = {
    6: 8,  # The 1850 marathon keeps its existing data and save identity.
}


TEST_TO_CONTENT_LEVEL = {
    **CAMPAIGN_TO_CONTENT_LEVEL,
    13: 6,
}

def get_campaign_content_level(campaign_level):
    try:
        level = int(campaign_level)
    except (TypeError, ValueError):
        return campaign_level
    return CAMPAIGN_TO_CONTENT_LEVEL.get(level, level)

def get_test_content_level(test_level):
    try:
        level = int(test_level)
    except (TypeError, ValueError):
        return test_level
    return TEST_TO_CONTENT_LEVEL.get(level, level)
