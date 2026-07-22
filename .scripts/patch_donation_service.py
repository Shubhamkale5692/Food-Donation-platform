
import os

# Use absolute path for Windows
filepath = r'f:\Food Donation Platform\backend\app\services\donation_service.py'
if not os.path.exists(filepath):
    print(f"File not found: {filepath}")
    exit(1)

with open(filepath, 'r') as f:
    content = f.read()

target = """    donation.status = models.DonationStatusEnum.ACCEPTED
    donation.ngo_id = ngo_id
    if donation.pickup_address:
        donation.pickup_location = donation.pickup_address
    db.commit()
    db.refresh(donation)
    _donation_log.info("NGO %s accepted donation %s", ngo_id, donation_id)
    return donation"""

replacement = """    donation.status = models.DonationStatusEnum.ACCEPTED
    donation.ngo_id = ngo_id
    if donation.pickup_address:
        donation.pickup_location = donation.pickup_address

    # FIX 2: CREATE a delivery record
    delivery = models.Delivery(
        donation_id=donation.id,
        ngo_id=ngo_id,
        volunteer_id=None,
        status=models.DeliveryStatusEnum.PENDING
    )
    db.add(delivery)

    db.commit()
    db.refresh(donation)
    _donation_log.info("NGO %s accepted donation %s", ngo_id, donation_id)
    return donation"""

if target in content:
    new_content = content.replace(target, replacement)
    with open(filepath, 'w') as f:
        f.write(new_content)
    print("Successfully patched donation_service.py")
elif target.replace('\n', '\r\n') in content:
    new_content = content.replace(target.replace('\n', '\r\n'), replacement.replace('\n', '\r\n'))
    with open(filepath, 'w') as f:
        f.write(new_content)
    print("Successfully patched donation_service.py (CRLF)")
else:
    print("Target block not found in donation_service.py")
    # Debug: Print a snippet of the file to see why matching failed
    start_idx = content.find("donation.status = models.DonationStatusEnum.ACCEPTED")
    if start_idx != -1:
        print("Found start at:", start_idx)
        print("Snippet:", repr(content[start_idx:start_idx+300]))
    else:
        print("Could not even find the start of the block.")
