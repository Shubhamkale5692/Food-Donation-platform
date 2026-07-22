
import os

filepath = r'f:\Food Donation Platform\frontend\app\app.js'
if not os.path.exists(filepath):
    print(f"File not found: {filepath}")
    exit(1)

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Target 1: Delivery Tracking
target1 = """          NgoService.getDeliveryTracking()
            .then(function(trackingRes) {
              $scope.myDeliveries = trackingRes.data;
              console.log("[FoodBridge] NGO Dashboard myDeliveries:", $scope.myDeliveries.length, "ngoId:", loggedInNgoId);
            })
            .catch(function(err) {
              console.error('[FoodBridge] Failed to load delivery tracking:', err);
              $scope.myDeliveries = [];
            });"""

replacement1 = """          NgoService.getDeliveryTracking()
            .then(function(trackingRes) {
              $scope.deliveries = trackingRes.data || [];
              console.log("[FoodBridge] NGO Dashboard deliveries:", $scope.deliveries.length, "ngoId:", loggedInNgoId);
            })
            .catch(function(err) {
              console.error('[FoodBridge] Failed to load delivery tracking:', err);
              $scope.deliveries = [];
            });"""

# Target 2: Outer Catch Block
target2 = """        .catch(function (err) {
          console.error('[FoodBridge] NGO dashboard load error:', err);
          $scope.error = "Could not load donations. Please check your connection or contact support.";
        })"""

replacement2 = """        .catch(function (err) {
          console.error('[FoodBridge] NGO dashboard load error:', err);
          
          // FIX 3: Conditional Error Alert
          // Only show popup for server errors (500+) or no connection
          var isServerError = !err.status || err.status >= 500;
          if (isServerError) {
              $scope.error = "Could not load donations. Please check your connection or contact support.";
          }
        })"""

new_content = content
if target1 in content:
    new_content = new_content.replace(target1, replacement1)
    print("Matched Target 1")
elif target1.replace('\\n', '\\r\\n') in content:
    new_content = new_content.replace(target1.replace('\\n', '\\r\\n'), replacement1.replace('\\n', '\\r\\n'))
    print("Matched Target 1 (CRLF)")
else:
    print("Target 1 not found")

if target2 in content:
    new_content = new_content.replace(target2, replacement2)
    print("Matched Target 2")
elif target2.replace('\\n', '\\r\\n') in content:
    new_content = new_content.replace(target2.replace('\\n', '\\r\\n'), replacement2.replace('\\n', '\\r\\n'))
    print("Matched Target 2 (CRLF)")
else:
    print("Target 2 not found")

if new_content != content:
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Successfully patched app.js")
else:
    print("No changes made to app.js")
    # Debug snippet
    idx1 = content.find("NgoService.getDeliveryTracking()")
    if idx1 != -1:
        print("Found NgoService start at:", idx1)
        print("Snippet:", repr(content[idx1:idx1+200]))
    idx2 = content.find(".catch(function (err) {")
    if idx2 != -1:
        print("Found catch start at:", idx2)
        print("Snippet:", repr(content[idx2:idx2+200]))
