import re

with open(r'f:\Food Donation Platform\frontend\app\app.js', 'r', encoding='utf-8') as f:
    text = f.read()

header = """/**
 * FoodBridge - Main Angular Module, Router & Controllers
 *
 * NOTE: The Angular module with ngRoute is initialized in index.html BEFORE
 * this file loads. This file sets up routes and controllers.
 */

var app = angular.module("foodBridgeApp");

// Centralized role mapping for terminology upgrade
app.constant('ROLE_LABELS', {
    volunteer: "Delivery Partner"
});

// ─────────────────────────────────────────────────────────────────────────────
"""

text = re.sub(r'(?s)^.*?app\.controller', header + 'app.controller', text, count=1)

with open(r'f:\Food Donation Platform\frontend\app\app.js', 'w', encoding='utf-8') as f:
    f.write(text)
print("app.js fixed")
