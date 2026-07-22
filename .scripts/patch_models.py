"""
In-place patch for models.py to fix SQLAlchemy Enum sending .name (uppercase)
instead of .value (lowercase) to PostgreSQL.
"""
import re

path = r"f:\Food Donation Platform\backend\app\domain\models.py"
with open(path, "rb") as f:
    content = f.read().decode("utf-8")

OLD_STATUS = "    status = Column(\r\n        Enum(DonationStatusEnum), default=DonationStatusEnum.PENDING, index=True\r\n    )"
NEW_STATUS = "    status = Column(\r\n        Enum(DonationStatusEnum, values_callable=lambda x: [e.value for e in x], native_enum=False),\r\n        default=DonationStatusEnum.PENDING, index=True\r\n    )"

OLD_FRESH = "    freshness_status = Column(\r\n        Enum(FreshnessStatusEnum), default=FreshnessStatusEnum.UNKNOWN\r\n    )  # AI Tag"
NEW_FRESH = "    freshness_status = Column(\r\n        Enum(FreshnessStatusEnum, values_callable=lambda x: [e.value for e in x], native_enum=False),\r\n        default=FreshnessStatusEnum.UNKNOWN\r\n    )  # AI Tag"

if OLD_STATUS in content:
    content = content.replace(OLD_STATUS, NEW_STATUS)
    print("Patched DonationStatusEnum column")
else:
    print("ERROR: Could not find DonationStatusEnum column pattern")

if OLD_FRESH in content:
    content = content.replace(OLD_FRESH, NEW_FRESH)
    print("Patched FreshnessStatusEnum column")
else:
    print("ERROR: Could not find FreshnessStatusEnum column pattern")

with open(path, "wb") as f:
    f.write(content.encode("utf-8"))

print("Done!")
