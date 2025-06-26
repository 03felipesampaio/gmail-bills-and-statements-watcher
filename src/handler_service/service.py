from loguru import logger

def parse_data_from_event(event_data) -> dict:
    pass


def find_start_history_id(user_last_history_id: int, event_history_id: int) -> int:
    """
    Determines the starting history ID for processing Gmail events.
    If the user's last known history ID is not set (i.e., falsy), returns the event's history ID.
    Otherwise, returns the next history ID after the user's last known history ID.
    Args:
        user_last_history_id (int): The last history ID processed for the user. Can be 0 or None if not set.
        event_history_id (int): The history ID associated with the current event.
    Returns:
        int: The starting history ID to use for processing.
    """
    if not user_last_history_id:
        return int(event_history_id)
    
    return int(user_last_history_id) + 1


def process_history_events