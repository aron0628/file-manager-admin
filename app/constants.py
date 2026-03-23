from enum import Enum


class Category(str, Enum):
    FINANCE = "Finance"
    MARKETING = "Marketing"
    ADMIN = "Admin"
    LEGAL = "Legal"
    HR = "HR"
    UNCATEGORIZED = "Uncategorized"


CATEGORY_CHOICES = [c.value for c in Category]


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


class ParseJobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"
    LOST = "lost"


ACTIVE_PARSE_STATUSES = {ParseJobStatus.PENDING.value, ParseJobStatus.PROCESSING.value}
