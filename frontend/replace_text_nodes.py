import os, glob
import re

search_dir = r"f:\Food Donation Platform\frontend\app"
html_files = glob.glob(os.path.join(search_dir, "**", "*.html"), recursive=True)
html_files.append(r"f:\Food Donation Platform\frontend\index.html")

def replacer(match):
    # This match will contain either a text block (group 1) or an HTML tag (group 2)
    # We only replace if it's outside a tag.
    text = match.group(0)
    if text.startswith('<'):
        return text
    else:
        # replace Volunteer/volunteer with Delivery Partner
        # and Volunteers/volunteers with Delivery Partners
        text = re.sub(r'\b[Vv]olunteers\b', 'Delivery Partners', text)
        text = re.sub(r'\b[Vv]olunteer\b', 'Delivery Partner', text)
        return text

for filepath in html_files:
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Parse tags vs text
        # Regex explanation: (<[^>]+>) captures HTML tags.
        # ([^<]+) captures everything else.
        new_content = re.sub(r'<[^>]+>|[^<]+', replacer, content)
            
        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f'Updated text nodes: {filepath}')
