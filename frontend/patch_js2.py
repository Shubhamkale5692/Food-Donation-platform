"""
Rewrites the aiAssignVolunteer and manualAssignVolunteer functions in app.js
with correct immediate scope update + dashboard refresh + debug logging.
"""

path = 'f:/Food Donation Platform/frontend/app/app.js'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old_ai_fn = """    // ── AI Volunteer Assignment ───────────────────────────────────────────────
    $scope.aiAssignVolunteer = function (donation, event) {
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
    };"""

new_ai_fn = """    // ── AI Volunteer Assignment ───────────────────────────────────────────────
    $scope.aiAssignVolunteer = function (donation, event) {
      var btn = event ? event.currentTarget : null;
      var originalText = btn ? btn.innerHTML : "";
      if (btn) {
         btn.disabled = true;
         btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Getting AI recommendation...';
      }
      console.log("[FoodBridge] aiAssignVolunteer called | donation_id:", donation.id, "| status:", donation.status);

      AIService.assignVolunteer(donation.id)
        .then(function (aiRes) {
            var volName = aiRes.data.volunteer_name || "a volunteer";
            var conf = parseFloat(aiRes.data.confidence_score || 0).toFixed(0);
            var volId = aiRes.data.best_volunteer_id;
            var distance = aiRes.data.distance_km;
            var isOnline = aiRes.data.is_online ? "🟢 Online" : "⚪ Offline";
            console.log("[FoodBridge] AI recommendation | vol_id:", volId, "| name:", volName, "| conf:", conf);

            if (!volId) {
                $scope.error = "AI could not find an available volunteer. Please use manual assignment.";
                $timeout(function() { $scope.error = null; }, 5000);
                if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
                // Auto-focus manual dropdown
                var select = document.getElementById("vol-select-" + donation.id);
                if (select) select.focus();
                return;
            }

            if (btn) {
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Waiting for confirmation...';
            }

            var confLabel = parseFloat(conf) > 80 ? "Highly Recommended" : "Recommended";
            var distanceStr = (distance !== null && distance !== undefined) ? distance + " km away, " : "";
            var confirmMsg = "Assign " + volName + " (" + distanceStr + isOnline + ")\\n" + confLabel + " – Confidence: " + conf + "%\\n\\nProceed?";

            if (confirm(confirmMsg)) {
                if (btn) {
                    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Assigning...';
                }
                console.log("[FoodBridge] User confirmed. Calling assignVolunteer | donation_id:", donation.id, "| volunteer_id:", volId);

                DonationService.assignVolunteer(donation.id, volId)
                  .then(function (res) {
                      console.log("[FoodBridge] Assignment SUCCESS response:", res.data);
                      flashSuccess("✅ Volunteer Assigned Successfully!", 4000);
                      // Immediately update scope to prevent donation being re-shown as available
                      donation.status = 'assigned';
                      donation.volunteer_id = volId;
                      donation.selectedVolunteerId = null;
                      // Push update to myDeliveries for immediate NGO tracking visibility
                      var alreadyIn = $scope.myDeliveries.some(function(d) { return d.id === donation.id; });
                      if (!alreadyIn) { $scope.myDeliveries.push(donation); }
                      // Remove from Incoming list
                      $scope.availableDonations = $scope.availableDonations.filter(function(d) { return d.id !== donation.id; });
                      // Full dashboard refresh
                      loadNgoDashboard();
                      loadNgoStats();
                      loadAllVolunteers();
                      loadAvailableVolunteers();
                      if (btn) {
                          btn.disabled = true;
                          btn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Assigned';
                      }
                  })
                  .catch(function (err) {
                      var errMsg = (err.data && err.data.detail) ? err.data.detail : "Could not assign volunteer.";
                      console.error("[FoodBridge] Assignment FAILED:", errMsg, err);
                      $scope.error = errMsg;
                      $timeout(function() { $scope.error = null; }, 6000);
                      if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
                  });
            } else {
                 if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
            }
        })
        .catch(function (err) {
            var errMsg = (err.data && err.data.detail) ? err.data.detail : "AI service unavailable.";
            console.error("[FoodBridge] AI recommendation FAILED:", errMsg, err);
            $scope.error = "AI assignment failed: " + errMsg + " — Please use manual assignment.";
            $timeout(function() { $scope.error = null; }, 6000);
            var select = document.getElementById("vol-select-" + donation.id);
            if (select) { select.focus(); }
            if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
        });
    };"""

new_content = content.replace(old_ai_fn, new_ai_fn)
if new_content == content:
    print("WARNING: aiAssignVolunteer not replaced! Saving diagnostic...")
    # Print a snippet of what exists
    idx = content.find('aiAssignVolunteer = function')
    print("Found at index:", idx)
    print("Snippet:", repr(content[idx:idx+200]))
else:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("SUCCESS: app.js aiAssignVolunteer rewritten!")
