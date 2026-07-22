import sys
import os

print(f"Python: {sys.version}")
print(f"CWD: {os.getcwd()}")
print(f"Path: {sys.path}")

try:
    import fastapi
    print("fastapi imported")
except ImportError as e:
    print(f"fastapi import failed: {e}")

try:
    from app.main import app
    print("app.main imported")
except Exception as e:
    print(f"app.main import failed: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.domain import models
    print(f"models.DonationStatusEnum: {list(models.DonationStatusEnum)}")
except Exception as e:
    print(f"app.domain.models import failed: {e}")
    import traceback
    traceback.print_exc()
