import sys

try:
    with open('backend_err_3.txt', 'r', encoding='utf-16') as f:
        content = f.read()
    
    lines = content.split('\n')
    
    # Just print the last 20 lines to a new utf-8 file
    with open('trace.txt', 'w', encoding='utf-8') as out:
        out.write('\n'.join(lines[-30:]))
except Exception as e:
    print(e)
