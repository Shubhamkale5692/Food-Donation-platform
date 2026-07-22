
import os

filepath = r'f:\Food Donation Platform\frontend\app\app.js'
if not os.path.exists(filepath):
    print(f"File not found: {filepath}")
    exit(1)

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all occurrences of myDeliveries with deliveries
new_content = content.replace('myDeliveries', 'deliveries')

if new_content != content:
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Successfully renamed myDeliveries to deliveries in app.js")
else:
    print("No occurrences of myDeliveries found in app.js")
