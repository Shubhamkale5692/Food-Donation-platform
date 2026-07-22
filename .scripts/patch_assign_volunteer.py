
import os

filepath = r'f:\Food Donation Platform\backend\app\services\donation_service.py'
if not os.path.exists(filepath):
    print(f"File not found: {filepath}")
    exit(1)

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Target block in assign_volunteer
target = """        existing = (
            db.query(models.Delivery)
            .filter(models.Delivery.donation_id == donation_id)
            .first()
        )
        if existing:
            _assign_log.warning(
                "[assign_volunteer] Delivery already exists for donation %s",
                donation_id,
            )
            return existing"""

replacement = """        existing_delivery = (
            db.query(models.Delivery)
            .filter(models.Delivery.donation_id == donation_id)
            .first()
        )
        
        # FIX 3: If delivery exists (created during claim), update it.
        # Otherwise, we will create a new one below.
        if existing_delivery:
            _assign_log.info("[assign_volunteer] Found existing delivery %s, updating it.", existing_delivery.id)
            otp = f"{secrets.randbelow(OTP_MAX - OTP_MIN + 1) + OTP_MIN:06d}"
            existing_delivery.volunteer_id = volunteer_id
            existing_delivery.status = models.DeliveryStatusEnum.ASSIGNED
            existing_delivery.otp = otp
            delivery = existing_delivery
        else:
            _assign_log.info("[assign_volunteer] Creating new delivery record.")
            otp = f"{secrets.randbelow(OTP_MAX - OTP_MIN + 1) + OTP_MIN:06d}"
            delivery = models.Delivery(
                donation_id=donation_id,
                ngo_id=ngo_id,
                volunteer_id=volunteer_id,
                otp=otp,
                status=models.DeliveryStatusEnum.ASSIGNED,
            )
            db.add(delivery)"""

# Also need to remove the old delivery creation block further down
target_old_creation = """        delivery = models.Delivery(
            donation_id=donation_id,
            ngo_id=ngo_id,
            volunteer_id=best_volunteer.id,
            otp=otp,
            status=models.DeliveryStatusEnum.ASSIGNED,
        )

        db.add(delivery)"""

# I will replace the first block and then use a more robust regex-like replacement if needed
# Actually, the logic is cleaner if I just replace from line 418 to 459 approximately.

if target in content:
    # First, let's find the otp generation line which we need to keep or move
    content = content.replace(target, replacement)
    # Remove the old creation block and the redundant otp generation
    content = content.replace('        otp = f"{secrets.randbelow(OTP_MAX - OTP_MIN + 1) + OTP_MIN:06d}"', '', 1) 
    content = content.replace(target_old_creation, '')
    
    # Clean up any double blank lines caused by removal
    import re
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully patched assign_volunteer in donation_service.py")
else:
    print("Target block not found in donation_service.py")
