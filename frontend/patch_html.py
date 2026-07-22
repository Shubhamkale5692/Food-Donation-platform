with open("index.html", "r", encoding="utf-8") as f:
    content = f.read()

target = "</body>"
replacement = '  <audio id="notificationSound" src="assets/notification.mp3" preload="auto"></audio>\n  </body>'

if "notificationSound" not in content and target in content:
    content = content.replace(target, replacement)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched index.html")
else:
    print("Already patched or target not found")
