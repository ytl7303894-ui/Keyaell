# 
import json
import os

files = {
    'keys.json': {},
    'users.json': {},
    'pending_payments.json': {},
    'orders.json': {},
    'owner_keys.json': {}
}

for filename, data in files.items():
    if not os.path.exists(filename):
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"✅ Created: {filename}")

# Create screenshots folder
if not os.path.exists('screenshots'):
    os.makedirs('screenshots')
    print("✅ Created: screenshots/")

print("\n✅ All files created!")