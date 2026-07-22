import re

path = 'f:/Food Donation Platform/frontend/app/app.js'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r'\$scope\.aiAssignVolunteer = function \(donation\) \{.*?\};\n'

replacement = """$scope.aiAssignVolunteer = function (donation, event) {
      // Find the button to show loading
      var btn = event ? event.currentTarget : null;
      var originalText = btn ? btn.innerHTML : "";
      if (btn) {
         btn.disabled = true;
         btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Assigning volunteer...';
      }

      AIService.assignVolunteer(donation.id)
        .then(function (aiRes) {
            var volName = aiRes.data.volunteer_name || "a volunteer";
            var conf = aiRes.data.confidence_score;
            var volId = aiRes.data.best_volunteer_id;
            var distance = aiRes.data.distance_km;
            var isOnline = aiRes.data.is_online ? "🟢 Online" : "⚪ Offline";
            
            if (!volId) {
                $scope.error = "No available volunteers at the moment.";
                $timeout(function() { $scope.error = null; }, 4000);
                if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
                return;
            }
            
            var confLabel = conf > 80 ? "Highly Recommended" : "Recommended";
            var distanceStr = (distance !== null && distance !== undefined) ? distance + " km away, " : "";
            var confirmMsg = "Assign " + volName + " (" + distanceStr + isOnline + ") – " + confLabel + " (Confidence: " + conf + "%)?";

            if (confirm(confirmMsg)) {
                DonationService.assignVolunteer(donation.id, volId)
                  .then(function () { 
                      flashSuccess("Volunteer Assigned Successfully!", 3000);
                      donation.status = 'assigned';
                      loadNgoDashboard(); 
                      loadNgoStats(); 
                      loadAllVolunteers();
                      donation.selectedVolunteerId = null;
                      
                      if (typeof $scope.loadData === 'function') $scope.loadData();
                  })
                  .catch(function (err) { 
                      $scope.error = (err.data && err.data.detail) ? err.data.detail : "Could not assign volunteer."; 
                      if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
                  });
            } else {
                 if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
            }
        })
        .catch(function (err) {
            $scope.error = "AI Volunteer assignment failed. Falling back to manual assignment.";
            // Auto Fallback to Manual Assign by focusing it
            var select = document.getElementById("vol-select-" + donation.id);
            if (select) select.focus();
            if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
        });
    };
"""

new_text = re.sub(pattern, replacement, text, flags=re.DOTALL)

with open(path, 'w', encoding='utf-8') as f:
    f.write(new_text)
print("Replaced app.js!")
