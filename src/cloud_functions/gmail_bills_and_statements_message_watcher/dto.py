from dataclasses import dataclass
from datetime import datetime

@dataclass
class UserRecord:
    user_id: str
    last_refresh: datetime
    expiration: datetime
    history_id: str