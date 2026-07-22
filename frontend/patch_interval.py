import re

path = 'f:/Food Donation Platform/frontend/app/app.js'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r'    loadAvailableVolunteers\(\);\s+\$scope\.loadPendingVolunteers = function\(\) \{'

replacement = """    loadAvailableVolunteers();

    // Auto-refresh mechanism every 20 seconds
    var refreshInterval = $interval(function() {
        loadNgoDashboard();
        loadNgoStats();
        loadAvailableVolunteers();
    }, 20000);

    $scope.$on('$destroy', function() {
        if (refreshInterval) {
            $interval.cancel(refreshInterval);
        }
    });

    $scope.loadPendingVolunteers = function() {"""

new_text = re.sub(pattern, replacement, text)

with open(path, 'w', encoding='utf-8') as f:
    f.write(new_text)
print("Added interval!")
