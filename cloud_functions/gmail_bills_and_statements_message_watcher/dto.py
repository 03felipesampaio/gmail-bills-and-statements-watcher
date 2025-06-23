from dataclasses import dataclass
from datetime import datetime

@dataclass
class UserWatchRecord:
    user_id: str
    last_refresh: datetime
    expiration: datetime
    history_id: str