import re

path = 'f:/Food Donation Platform/backend/app/services/donation_service.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r'    if volunteer_id:\s+best_volunteer = \(\s+db\.query\(models\.User\)\s+\.filter\(\s+models\.User\.id == volunteer_id,\s+models\.User\.role == models\.RoleEnum\.VOLUNTEER,\s+models\.User\.status == "approved",\s+models\.User\.availability == "available",\s+models\.User\.is_active == True,\s+\)\s+\.first\(\)\s+\)\s+if not best_volunteer:\s+_assign_log\.warning\(\s+"\[assign_volunteer\] Requested volunteer %s not found or not approved",\s+volunteer_id,\s+\)\s+# Fall through to auto-assign'

replacement = """    if volunteer_id:
        best_volunteer = (
            db.query(models.User)
            .filter(models.User.id == volunteer_id)
            .first()
        )
        if not best_volunteer:
            _assign_log.warning(
                "[assign_volunteer] Requested volunteer %s not found",
                volunteer_id,
            )
            return None"""

new_text = re.sub(pattern, replacement, text)

with open(path, 'w', encoding='utf-8') as f:
    f.write(new_text)
print("Replaced!")
