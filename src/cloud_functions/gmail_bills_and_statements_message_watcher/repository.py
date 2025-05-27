from datetime import datetime
import dto


def get_users_last_refresh(db) -> list[dto.UserRecord]:
    return [dto.UserRecord('me', datetime.now(), datetime.now(), "5672")]


def update_user_last_refresh(db, user_id: str, last_refresh: datetime, expiration: datetime, history_id: str) -> dto.UserRecord:
    """
    Update the user's last refresh and expiration in the database.
    Args:
        db: The database connection.
        user_id (str): The user's ID.
        last_refresh (datetime): The last refresh timestamp in milliseconds.
        expiration (datetime): The expiration timestamp in milliseconds.
    Returns:
        dto.UserRecord: The updated user record.
    """
    # This function would update the user's last refresh and expiration in the database
    return dto.UserRecord(
        user_id=user_id,
        last_refresh=last_refresh,
        expiration=expiration,
        history_id="1234567890"  # This would be the new history ID from the Gmail API response
    )