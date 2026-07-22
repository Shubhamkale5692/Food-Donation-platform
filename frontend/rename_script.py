import os, glob

search_dir = r"f:\Food Donation Platform\frontend\app"
html_files = glob.glob(os.path.join(search_dir, "**", "*.html"), recursive=True)
js_files = glob.glob(os.path.join(search_dir, "**", "*.js"), recursive=True)

all_files = html_files + js_files
all_files.append(r"f:\Food Donation Platform\frontend\index.html")

replacements = [
    # General labels
    ("Volunteer Management", "Delivery Partner Management"),
    ("Volunteer Performance", "Delivery Partner Performance"),
    ("Assign Volunteer", "Assign Delivery Partner"),
    ("Track Volunteer", "Track Delivery Partner"),
    ("Volunteer List", "Delivery Partner List"),
    ("Volunteer Name", "Delivery Partner Name"),
    ("Volunteer Analytics", "Delivery Partner Analytics"),
    ("Top Volunteers", "Top Delivery Partners"),
    ("Volunteer Reports", "Delivery Partner Reports"),
    ("Volunteer Assignment", "Delivery Partner Assignment"),
    ("Volunteer Tracking", "Delivery Partner Tracking"),
    ("Filter by Volunteer", "Filter by Delivery Partner"),
    ("Volunteer Dashboard", "Delivery Partner Dashboard"),
    
    # Capitalized generic phrases and tags
    ("Assign volunteer", "Assign Delivery Partner"),
    ("assign volunteer", "assign Delivery Partner"),
    ("Assigning volunteer", "Assigning Delivery Partner"),
    ("assigned volunteer", "assigned Delivery Partner"),
    ("View volunteers", "View Delivery Partners"),
    ("view volunteers", "view Delivery Partners"),
    ("Find a Volunteer", "Find a Delivery Partner"),
    ("Find a volunteer", "Find a Delivery Partner"),
    (">Volunteer<", ">Delivery Partner<"),
    ("> Volunteers <", "> Delivery Partners <"),
    ("> Volunteer <", "> Delivery Partner <"),
    ("For Volunteers:", "For Delivery Partners:"),
    ("As a volunteer", "As a Delivery Partner"),
    ("Become a Volunteer", "Become a Delivery Partner"),
    ("We appreciate our volunteers!", "We appreciate our Delivery Partners!"),
    ("Become a volunteer", "Become a Delivery Partner"),
    ("Become a Volunteer Today", "Become a Delivery Partner Today"),
    ("Our Volunteers", "Our Delivery Partners"),
    ("Volunteers are the backbone", "Delivery Partners are the backbone"),
    ("Our volunteers are", "Our Delivery Partners are"),
    ("Volunteer Impact", "Delivery Partner Impact"),
    ("Top Volunteer:", "Top Delivery Partner:"),
    ("Available Volunteers", "Available Delivery Partners"),
    ("Select a volunteer", "Select a Delivery Partner"),
    ("No volunteers available", "No Delivery Partners available"),
    ("Manage volunteers", "Manage Delivery Partners"),
    ("Manage Volunteers", "Manage Delivery Partners"),
    ("total volunteers", "total Delivery Partners"),
    ("Total Volunteers", "Total Delivery Partners"),
    ("Pending Volunteers", "Pending Delivery Partners"),
    ("Approve Volunteer", "Approve Delivery Partner"),
    ("Reject Volunteer", "Reject Delivery Partner"),
    ("Register as Volunteer", "Register as Delivery Partner"),
    ("Are you a volunteer?", "Are you a Delivery Partner?"),
    ("For Volunteers -", "For Delivery Partners -"),
    ("Select Volunteer", "Select Delivery Partner"),
    
    # Notifications and alerts (usually in JS files)
    ('"Volunteer Assigned Successfully!"', '"Delivery Partner Assigned Successfully!"'),
    ("'Volunteer Assigned Successfully!'", "'Delivery Partner Assigned Successfully!'"),
    ('"Volunteer assigned successfully!"', '"Delivery Partner assigned successfully!"'),
    ('"No available volunteers at the moment."', '"No available Delivery Partners at the moment."'),
    ('"Could not assign volunteer."', '"Could not assign Delivery Partner."'),
    ('"AI Volunteer assignment failed. Falling back to manual assignment."', '"AI Delivery Partner assignment failed. Falling back to manual assignment."'),
    ('"AI could not find an available volunteer. Please use manual assignment."', '"AI could not find an available Delivery Partner. Please use manual assignment."'),
    ('&& err.data.detail) ? err.data.detail : "Could not assign volunteer."', '&& err.data.detail) ? err.data.detail : "Could not assign Delivery Partner."'),
    ('"Approve this volunteer?"', '"Approve this Delivery Partner?"'),
    ('"Volunteer approved!"', '"Delivery Partner approved!"'),
    ('"Reject this volunteer request?"', '"Reject this Delivery Partner request?"'),
    ('"Volunteer rejected."', '"Delivery Partner rejected."')
]

for filepath in set(all_files):
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        new_content = content
        for old, new in replacements:
            new_content = new_content.replace(old, new)
            
        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f'Updated: {filepath}')
