import re

path = 'f:/Food Donation Platform/backend/app/interfaces/donation_router.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

out = []
i = 0
while i < len(lines):
    # Detect start of old block
    if (lines[i].rstrip('\r\n') == '    if volunteer_id:' and
        i + 1 < len(lines) and 'db.query(models.User)' in lines[i + 1]):
        # Skip until after the broken availability block
        # Insert our fixed block
        out.append('    if volunteer_id:\n')
        out.append('        vol = db.query(models.User).filter(models.User.id == volunteer_id).first()\n')
        out.append('        if not vol:\n')
        out.append('            raise HTTPException(status_code=404, detail="Volunteer not found")\n')
        out.append('        log.info(\n')
        out.append('            "[assign_route] Volunteer %s | status=%s | availability=%s",\n')
        out.append('            vol.id, vol.status, vol.availability\n')
        out.append('        )\n')
        out.append('        if vol.status != "approved":\n')
        out.append('            raise HTTPException(\n')
        out.append('                status_code=400,\n')
        out.append('                detail=f"Volunteer is \'{vol.status}\' \u2014 only approved volunteers can be assigned.",\n')
        out.append('            )\n')
        out.append('        if vol.availability not in ("available", "online"):\n')
        out.append('            raise HTTPException(\n')
        out.append('                status_code=400,\n')
        out.append('                detail=f"Selected volunteer is currently \'{vol.availability}\' and cannot be assigned.",\n')
        out.append('            )\n')
        # Skip old lines until we reach the delivery = line
        while i < len(lines) and 'delivery = donation_service.assign_volunteer' not in lines[i]:
            i += 1
        # Add a blank line separator
        out.append('\n')
    else:
        out.append(lines[i])
        i += 1

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(out)

print("donation_router.py patched!")
