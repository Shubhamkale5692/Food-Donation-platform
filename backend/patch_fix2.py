"""
Surgical patch script for donation_router.py and donation_service.py
Fixes the AI Assignment execution bug:
- Removes wrong 'online' from availability check
- Ensures volunteer_id direct assignment bypasses auto-assign
- Adds strong debug logging
"""
import re

# === FIX 1: donation_router.py ===
router_path = 'f:/Food Donation Platform/backend/app/interfaces/donation_router.py'
with open(router_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    # Find the volunteer validation block
    if '    if volunteer_id:' in line and i + 1 < len(lines) and 'db.query(models.User).filter(models.User.id == volunteer_id)' in lines[i+1]:
        # Replace the entire block up to the delivery = ... call
        new_lines.append('    if volunteer_id:\n')
        new_lines.append('        vol = db.query(models.User).filter(models.User.id == volunteer_id).first()\n')
        new_lines.append('        if not vol:\n')
        new_lines.append('            raise HTTPException(status_code=404, detail="Volunteer not found")\n')
        new_lines.append('        log.info(\n')
        new_lines.append('            "[assign_route] DEBUG volunteer_id=%s | status=%s | availability=%s | is_online=%s",\n')
        new_lines.append('            str(volunteer_id), vol.status, vol.availability, vol.is_online\n')
        new_lines.append('        )\n')
        new_lines.append('        if vol.status != "approved":\n')
        new_lines.append('            raise HTTPException(\n')
        new_lines.append('                status_code=400,\n')
        new_lines.append('                detail=f"Volunteer is not approved (status={vol.status}). Only approved volunteers can be assigned.",\n')
        new_lines.append('            )\n')
        new_lines.append('        # Only block if explicitly marked busy — available/None/online/any other value is fine\n')
        new_lines.append('        if vol.availability == "busy":\n')
        new_lines.append('            raise HTTPException(\n')
        new_lines.append('                status_code=400,\n')
        new_lines.append('                detail="Selected volunteer is currently busy and cannot be assigned.",\n')
        new_lines.append('            )\n')
        new_lines.append('\n')
        # Skip original lines until we reach the delivery = line
        while i < len(lines) and 'delivery = donation_service.assign_volunteer' not in lines[i]:
            i += 1
    else:
        new_lines.append(line)
        i += 1

with open(router_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("FIXED: donation_router.py")


# === FIX 2: donation_service.py — ensure flush+refresh after commit ===
svc_path = 'f:/Food Donation Platform/backend/app/services/donation_service.py'
with open(svc_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the try/except-commit block to add refresh on donation too
old_commit = """    try:
        db.add(delivery)
        db.commit()
        db.refresh(delivery)
        _assign_log.info(\"[assign_volunteer] SUCCESS  delivery=%s\", delivery.id)
        return delivery
    except Exception as exc:
        db.rollback()
        _assign_log.exception(\"[assign_volunteer] DB error: %s\", exc)
        return None"""

new_commit = """    try:
        db.add(delivery)
        db.flush()  # Flush first to catch constraint errors before commit
        db.commit()
        db.refresh(delivery)
        db.refresh(donation)   # Verify donation was actually updated
        db.refresh(best_volunteer)  # Verify volunteer availability update
        _assign_log.info(
            \"[assign_volunteer] SUCCESS delivery=%s | donation.status=%s | donation.volunteer_id=%s | volunteer.availability=%s\",
            delivery.id, donation.status, donation.volunteer_id, best_volunteer.availability
        )
        return delivery
    except Exception as exc:
        db.rollback()
        _assign_log.exception(\"[assign_volunteer] DB COMMIT ERROR: %s\", exc)
        return None"""

new_content = content.replace(old_commit, new_commit)
if new_content == content:
    print("WARNING: donation_service.py commit block not replaced - checking manually")
else:
    with open(svc_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("FIXED: donation_service.py commit block")
