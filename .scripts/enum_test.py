import sys
sys.path.append(r"/app")
from app.domain.models import DonationStatusEnum
print(f"Enum name: {DonationStatusEnum.ASSIGNED.name}")
print(f"Enum value: {DonationStatusEnum.ASSIGNED.value}")
