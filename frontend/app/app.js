/**
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
app.controller("NgoController", ["$scope", "DonationService", "AIService", "$interval", "MapService", "NgoService", "$timeout", "LiveTrackingService", "ChatService", "AuthService", "RouteManager", "BeneficiaryService",
  function ($scope, DonationService, AIService, $interval, MapService, NgoService, $timeout, LiveTrackingService, ChatService, AuthService, RouteManager, BeneficiaryService) {
    
    $scope.eta = 0;
    $scope.$watch(function() { return RouteManager.eta; }, function(newVal) {
        if (newVal !== null && newVal !== undefined) {
            $scope.eta = newVal;
        }
    });

    $scope.getElapsedTime = function (startTime) {
        if (!startTime) return "0 mins";
        var start = new Date(startTime);
        var now = new Date();
        var diffMs = now - start;
        if (diffMs < 0) return "0 mins";
        return Math.floor(diffMs / 60000) + " mins";
    };

    // ── Section / Navigation state ─────────────────────────────────────────
    $scope.activeSection = 'overview';
    $scope.setSection = function(section) {
      $scope.activeSection = section;
      if (section === 'tracking')         { $timeout(initNgoMap, 300); }
      if (section === 'reports')          { $timeout(initCharts, 300); }
      if (section === 'volunteers')       { loadAllVolunteers(); }
      if (section === 'inventory')        { loadInventory(); }
      if (section === 'distribution')     { loadDistributionRecords(); }
      if (section === 'profile')          { loadNgoProfile(); }
      if (section === 'beneficiaries')    { loadBeneficiaries(); }
      if (section === 'food-testing')     { loadReceivedDonations(); }
      if (section === 'dist-management')  { loadDistributionQueue(); }
      if (section === 'waste-management') { loadWasteList(); }
      if (section === 'beneficiaries')   { loadBeneficiaries(); }
    };

    // ── Real-Time Data Synchronization ──────────────────────────────────────
    // STEP 10 FIX: Changed to 20 seconds to reduce backend load
    $scope.manualRefresh = function() {
        $scope.loading = true;
        loadNgoDashboard();
        loadNgoStats();
        loadAllVolunteers();
        loadInventory();
        loadDistributionRecords();
        setTimeout(function() {
            $scope.loading = false;
        }, 1000);
    };

    // ── Core data arrays ──────────────────────────────────────────────────
    $scope.availableDonations  = [];
    $scope.deliveries        = [];
    $scope.acceptedDonations   = [];
    $scope.pendingVolunteers   = [];
    $scope.allVolunteers       = [];
    $scope.availableVolunteers = [];  // Approved volunteers for assign dropdown
    $scope.distributionRecords = [];
    $scope.inventory           = [];
    // ── Food Testing & Decision System arrays ──────────────────────────────
    $scope.receivedDonations   = [];  // Completed donations awaiting testing
    $scope.distributionQueue   = [];  // Tested and cleared for distribution
$scope.wasteList           = [];  // Rejected / spoiled donations
    $scope.beneficiaries       = [];  // Beneficiary list
    $scope.beneficiaryForm     = {};   // Form for create/edit
    $scope.editingBeneficiary  = null;
    // ───────────────────────────────────────────────────────────────────────────
    $scope.ngoStats            = { active_donations:0, accepted_donations:0, active_volunteers:0, items_distributed:0, food_waste_diverted:0, total_donations:0, total_volunteers:0 };
    
    // Helper function to calculate total waste quantity
    $scope.getTotalWasteQuantity = function() {
        if (!$scope.wasteList || $scope.wasteList.length === 0) return 0;
        return $scope.wasteList.reduce(function(sum, item) {
            return sum + (item.quantity || 0);
        }, 0);
    };
    $scope.ngoProfile          = {};
    $scope.editProfile         = false;
    $scope.profileForm         = {};
    $scope.loading             = false;
    $scope.statsLoading        = false;
    $scope.error               = null;
    $scope.successMsg          = null;
    $scope.notificationCount   = 0;
    $scope.selectedDonation    = null;

    function flashSuccess(message, timeoutMs) {
        $scope.successMsg = message;
        setTimeout(function() { $scope.successMsg = null; }, timeoutMs || 3000);
    }
    $scope.saveSettings = function() {
        flashSuccess("Settings saved!", 2000);
    };

    // ── Map / Tracking state ───────────────────────────────────────────────
    $scope.viewTab          = 'active';
    $scope.mapMode          = 'tracking';
    $scope.activeTracking   = null;
    $scope.activeTrackingDonationId = null;
    $scope.trackingStage    = 0;
    $scope.trackingProgress = 0;


    var map, volunteerMarker, donorMarker, ngoMarker, currentPolyline = null;
    var chartsInitialized = false;
    var donationTrendChart, mealsChart, volPerfChart;

    // ── Map Initialization ─────────────────────────────────────────────────
    function initNgoMap() {
        if (map) { try { map.invalidateSize(); } catch(e){} return; }
        var mapDiv = document.getElementById("ngo-interactive-map");
        if (!mapDiv) return;
        var centerPos = { lat: 28.6139, lng: 77.2090 };
        map = MapService.initMap("ngo-interactive-map", centerPos, 12);
    }
    setTimeout(initNgoMap, 500);

    // AI Heatmap for NGO (uses leaflet.heat instead of google.maps.visualization)
    var heatmapMap;
    var heatmapLayer;
    function initHeatmap(dataPoints) {
        var mapElement = document.getElementById('ngo-hunger-heatmap');
        if (!mapElement) return;

        if (!heatmapMap) {
            heatmapMap = MapService.initMap("ngo-hunger-heatmap", { lat: 28.6139, lng: 77.2090 }, 11);
        }

        // leaflet.heat expects: [[lat, lng, intensity], ...]
        var heatPoints = dataPoints.map(function(pt) {
            return [pt.lat, pt.lng, pt.weight || 0.5];
        });

        if (heatmapLayer) {
            try { heatmapMap.removeLayer(heatmapLayer); } catch(e){}
        }

        if (typeof L.heatLayer === 'function') {
            heatmapLayer = L.heatLayer(heatPoints, {
                radius: 30,
                blur: 20,
                maxZoom: 17,
                max: 1.0,
                gradient: { 0.3: 'blue', 0.6: 'yellow', 1.0: 'red' }
            }).addTo(heatmapMap);
        }
    }

    // ── Load NGO Stats ─────────────────────────────────────────────────────
    function loadNgoStats() {
        $scope.statsLoading = true;
        NgoService.getNgoStats()
            .then(function(res) { 
                $scope.ngoStats = res.data; 
                console.log("[FoodBridge] NGO stats loaded:", res.data);
            })
            .catch(function(err) { 
                console.warn("[FoodBridge] NGO stats error:", err); 
                $scope.ngoStats = { active_donations:0, accepted_donations:0, active_volunteers:0, items_distributed:0, food_waste_diverted:0, total_donations:0, total_volunteers:0 };
            })
            .finally(function() { $scope.statsLoading = false; });
    }

    // ── Load All Volunteers ────────────────────────────────────────────────
    function loadAllVolunteers() {
        NgoService.getAllVolunteers()
            .then(function(res) { 
                var vols = res.data || [];
                console.log("[FoodBridge] NGO Volunteers list:", vols.map(function(v) { return {id: v.id, name: v.name, status: v.volunteer_status}; }));
                $scope.pendingVolunteers = vols.filter(function(v) { return v.volunteer_status === 'pending'; });
                // Filter out rejected so they don't clutter the main list
                $scope.allVolunteers = vols.filter(function(v) { return v.volunteer_status !== 'rejected'; });
            })
            .catch(function(err) { console.warn("[FoodBridge] Get volunteers error:", err); });
    }

    // ── Load Available (Approved) Volunteers for Assign Dropdown ──────────
    function loadAvailableVolunteers() {
        NgoService.getAvailableVolunteers()
            .then(function(res) {
                console.log("Available Delivery Partners:", res.data); // Added per debugging instructions
                $scope.availableVolunteers = (res.data || []).map(function(v) {
                    var isAvail = v.availability === "available" || v.is_available;
                    var onlineLabel = isAvail ? '🟢 Available' : '🔴 Busy';
                    v.availabilityLabel = isAvail ? 'Available' : 'Busy';
                    // STEP 5 FIX: Default distance to "N/A" when null
                    v.distance = v.distance || "N/A";
                    v.displayName = onlineLabel + ' | ' + v.name +
                        ' - ' + v.distance + ' away';
                    v.name = v.displayName;
                    return v;
                });
                console.log("[FoodBridge] Available volunteers for assignment:", $scope.availableVolunteers.length, $scope.availableVolunteers);
            })
            .catch(function(err) {
                console.warn("[FoodBridge] getAvailableVolunteers error:", err);
                $scope.availableVolunteers = [];
            });
    }

    $scope.approveVolunteer = function (id) {
        if(!confirm("Approve this Delivery Partner?")) return;
        
        // Optimistic UI: instantly remove from pending list so dashboard updates immediately
        $scope.pendingVolunteers = $scope.pendingVolunteers.filter(function(v) { return v.id !== id; });
        // Update status in allVolunteers list instantly too
        $scope.allVolunteers.forEach(function(v) {
            if (v.id === id) { v.volunteer_status = 'approved'; }
        });
        
        NgoService.approveVolunteer(id)
            .then(function(res) {
                $scope.successMsg = (res.data && res.data.message) ? res.data.message : "Delivery Partner approved!";
                setTimeout(function(){ $scope.successMsg = null; }, 4000);
                // Sync from server after short delay to ensure DB committed
                setTimeout(function() {
                    loadAllVolunteers();
                    loadNgoStats();
                }, 800);
            })
            .catch(function(err) {
                // Rollback optimistic update on failure — re-fetch from server
                $scope.error = (err.data && err.data.detail) ? err.data.detail : "Action failed. Please try again.";
                setTimeout(function(){ $scope.error = null; }, 5000);
                loadAllVolunteers(); // Re-fetch to restore correct state
                console.error("[FoodBridge] Error approving volunteer:", err);
            });
    };

    $scope.rejectVolunteer = function (id) {
        if(!confirm("Reject this Delivery Partner request?")) return;
        
        // Optimistic UI: instantly remove from pending list
        $scope.pendingVolunteers = $scope.pendingVolunteers.filter(function(v) { return v.id !== id; });
        // Remove from allVolunteers table (rejected are hidden)
        $scope.allVolunteers = $scope.allVolunteers.filter(function(v) { return v.id !== id; });
        
        NgoService.rejectVolunteer(id)
            .then(function(res) {
                $scope.successMsg = (res.data && res.data.message) ? res.data.message : "Delivery Partner rejected.";
                setTimeout(function(){ $scope.successMsg = null; }, 4000);
                // Sync from server after short delay
                setTimeout(function() {
                    loadAllVolunteers();
                    loadNgoStats();
                }, 800);
            })
            .catch(function(err) {
                $scope.error = (err.data && err.data.detail) ? err.data.detail : "Action failed. Please try again.";
                setTimeout(function(){ $scope.error = null; }, 5000);
                loadAllVolunteers(); // Re-fetch to restore correct state
                console.error("[FoodBridge] Error rejecting volunteer:", err);
            });
    };

    // ── Load Inventory ─────────────────────────────────────────────────────
    function loadInventory() {
        NgoService.getNgoInventory()
            .then(function(res) { $scope.inventory = res.data; })
            .catch(function(err) { console.warn("[FoodBridge] Inventory error:", err); });
    }

    // ── Food Testing & Decision System functions ───────────────────────────

    function loadReceivedDonations() {
        NgoService.getReceivedDonations()
            .then(function(res) { $scope.receivedDonations = res.data || []; })
            .catch(function(err) { console.warn("[FoodBridge] ReceivedDonations error:", err); });
    }

    function loadDistributionQueue() {
        NgoService.getDistributionQueue()
            .then(function(res) { 
                $scope.distributionQueue = res.data || []; 
                loadBeneficiaries(); // Load beneficiaries so they are ready for the dropdown
            })
            .catch(function(err) { console.warn("[FoodBridge] DistributionQueue error:", err); });
    }

    function loadWasteList() {
        NgoService.getWasteList()
            .then(function(res) { $scope.wasteList = res.data || []; })
            .catch(function(err) { console.warn("[FoodBridge] WasteList error:", err); });
    }

    function loadBeneficiaries() {
        BeneficiaryService.getBeneficiaries()
            .then(function(res) { 
                $scope.beneficiaries = res.data || []; 
                console.log("[FoodBridge] Beneficiaries loaded:", $scope.beneficiaries.length);
                console.log("active see-----",$scope.activeSection)
            })
            .catch(function(err) { 
                console.warn("[FoodBridge] Beneficiaries error:", err); 
                $scope.beneficiaries = [];
            });
    }

    $scope.createBeneficiary = function() {
        var data = $scope.newBeneficiaryForm;
        if (!data || !data.name || !data.type) {
            alert("Please enter name and type for the beneficiary.");
            return;
        }
        BeneficiaryService.createBeneficiary(data)
            .then(function(res) {
                $scope.beneficiaries.push(res.data);
                $scope.newBeneficiaryForm = {};
                flashSuccess("Beneficiary created successfully!", 3000);
                $scope.loadBeneficiaries(); // Refresh list
            })
            .catch(function(err) {
                var msg = (err.data && err.data.detail) ? err.data.detail : "Failed to create beneficiary.";
                alert(msg);
            });
    };

    $scope.startEditBeneficiary = function(b) {
        $scope.editingBeneficiary = b;
        // Use angular.copy to create a detached object for editing
        $scope.beneficiaryForm = angular.copy(b);
        
        // Use timeout to ensure scope is applied before showing modal
        $timeout(function() {
            var modal = new bootstrap.Modal(document.getElementById('editBeneficiaryModal'));
            modal.show();
        });
    };

    $scope.cancelEditBeneficiary = function() {
        $scope.editingBeneficiary = null;
        $scope.beneficiaryForm = {};
    };

    $scope.saveBeneficiary = function() {
        if (!$scope.editingBeneficiary) return;
        
        // Clean up data to send only what's in the schema
        var rawData = $scope.beneficiaryForm;
        var data = {
            name: rawData.name,
            type: rawData.type,
            address: rawData.address,
            contact_number: rawData.contact_number,
            capacity: rawData.capacity,
            latitude: rawData.latitude,
            longitude: rawData.longitude
        };
        
        BeneficiaryService.updateBeneficiary($scope.editingBeneficiary.id, data)
            .then(function(res) {
                var idx = $scope.beneficiaries.findIndex(function(b) { return b.id === $scope.editingBeneficiary.id; });
                if (idx > -1) {
                    $scope.beneficiaries[idx] = res.data;
                }
                $scope.editingBeneficiary = null;
                $scope.beneficiaryForm = {};
                flashSuccess("Beneficiary updated successfully!", 3000);
            })
            .catch(function(err) {
                var msg = (err.data && err.data.detail) ? err.data.detail : "Failed to update beneficiary.";
                alert(msg);
            });
    };

    $scope.deleteBeneficiary = function(b) {
        if (!confirm("Are you sure you want to delete this beneficiary?")) return;
        BeneficiaryService.deleteBeneficiary(b.id)
            .then(function() {
                $scope.beneficiaries = $scope.beneficiaries.filter(function(item) { return item.id !== b.id; });
                flashSuccess("Beneficiary deleted successfully!", 3000);
            })
            .catch(function(err) {
                var msg = (err.data && err.data.detail) ? err.data.detail : "Failed to delete beneficiary.";
                alert(msg);
            });
    };

    /**
     * Submit a food quality test for a received donation.
     * quality: 'fresh' | 'moderate' | 'spoiled'
     */
    $scope.testFood = function(d) {
        var quality = d.food_quality;
        if (!quality) {
            alert("Please select a food quality before submitting.");
            return;
        }
        d._testing = true;
        NgoService.testFood(d.id, quality, d.remarks || "")
            .then(function(res) {
                var decision = res.data.decision;
                d.decision  = decision;
                d._tested   = true;
                d._testing  = false;

                var label = decision === 'distribute' ? '✅ Ready for Distribution'
                           : decision === 'urgent'   ? '⚠️ Urgent Delivery Required'
                           : '❌ Marked as Waste';
                
                flashSuccess("Food test submitted: " + label, 3000);

                var idx = $scope.receivedDonations.indexOf(d);
                if (idx > -1) {
                    $scope.receivedDonations.splice(idx, 1);
                }
                    
                if (decision === 'rejected') {
                    loadWasteList();
                } else {
                    loadDistributionQueue();
                }
            })
            .catch(function(err) {
                d._testing = false;
                var msg = (err && err.data && err.data.detail) ? err.data.detail : "Food test failed. Please try again.";
                d._testError = msg;
                console.error("[FoodBridge] testFood error:", err);
            });
    };

    // ───────────────────────────────────────────────────── end Food Testing ─

    // ── Load Distribution Records ──────────────────────────────────────────
    function loadDistributionRecords() {
        NgoService.getDistributionRecords()
            .then(function(res) {
                var records = res.data || [];
                var processedRecords = records.map(function(d) {
                    if (!d.created_at && d.completed_at) {
                        d.created_at = (typeof d.completed_at === "string")
                            ? d.completed_at.replace(" ", "T")
                            : d.completed_at;
                    }
                    return d;
                });
                
                // Update both lists to ensure consistency
                $scope.distributionRecords = processedRecords;
                $scope.distributionQueue = processedRecords;
                console.log("[FoodBridge] Distribution records/queue loaded:", processedRecords.length);
            })
            .catch(function(err) {
                console.warn("[FoodBridge] Distribution endpoint error:", err);
                // Only use fallback if we don't already have data from dashboard load
                if (!$scope.distributionRecords.length) {
                    DonationService.getDonations()
                        .then(function(res) {
                            var all = res.data || [];
                            $scope.distributionRecords = all.filter(function(d) {
                                var status = String(d.status || "").toLowerCase();
                                var statusOk = status === "completed" || status === "ready_for_distribution" || status === "distributed";
                                var tested = d.food_quality && d.decision && (d.decision === 'distribute' || d.decision === 'urgent');
                                return statusOk && tested;
                            });
                        })
                        .catch(function(fallbackErr) {
                            console.warn("[FoodBridge] Distribution fallback error:", fallbackErr);
                        });
                }
            });
    }

    // ── Chart.js Initialization ────────────────────────────────────────────
    function initCharts() {
        console.log("[FoodBridge] Initializing charts...");
        if (typeof Chart === 'undefined') { 
            console.warn("Chart.js not loaded."); 
            return; 
        }
        NgoService.getNgoAnalytics()
            .then(function(res) {
                console.log("[FoodBridge] Analytics data:", res.data);
                var data = res.data;
                var monthly = data.monthly || [];
                var labels   = monthly.map(function(m) { return m.month; });
                var donations = monthly.map(function(m) { return m.donations; });
                var meals    = monthly.map(function(m) { return m.meals; });
                var people   = monthly.map(function(m) { return m.people_helped; });
                var volPerf  = data.volunteer_performance || [];

                var ctx1 = document.getElementById('donationTrendChart');
                if (ctx1) {
                    if (donationTrendChart) donationTrendChart.destroy();
                    donationTrendChart = new Chart(ctx1, {
                        type: 'line',
                        data: { labels: labels, datasets: [{ label: 'Donations', data: donations,
                            borderColor: '#27ae60', backgroundColor: 'rgba(39,174,96,0.12)',
                            borderWidth: 3, fill: true, tension: 0.45,
                            pointBackgroundColor: '#27ae60', pointRadius: 5 }] },
                        options: { responsive: true, maintainAspectRatio: false,
                            plugins: { legend: { display: false } },
                            scales: { x: { grid: { display: false } }, y: { beginAtZero: true } } }
                    });
                }

                var ctx2 = document.getElementById('mealsChart');
                if (ctx2) {
                    if (mealsChart) mealsChart.destroy();
                    mealsChart = new Chart(ctx2, {
                        type: 'bar',
                        data: { labels: labels, datasets: [
                            { label: 'Meals', data: meals, backgroundColor: 'rgba(52,152,219,0.8)', borderRadius: 6 },
                            { label: 'People Helped', data: people, backgroundColor: 'rgba(155,89,182,0.8)', borderRadius: 6 }
                        ]},
                        options: { responsive: true, maintainAspectRatio: false,
                            plugins: { legend: { position: 'top' } },
                            scales: { x: { grid: { display: false } }, y: { beginAtZero: true } } }
                    });
                }

                var ctx3 = document.getElementById('volPerfChart');
                if (ctx3) {
                    if (volPerfChart) volPerfChart.destroy();
                    volPerfChart = new Chart(ctx3, {
                        type: 'bar',
                        data: { labels: volPerf.map(function(v){ return v.name; }),
                            datasets: [{ label: 'Deliveries',
                                data: volPerf.map(function(v){ return v.completed; }),
                                backgroundColor: ['#27ae60','#2980b9','#8e44ad','#e67e22','#e74c3c'],
                                borderRadius: 8 }] },
                        options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                            plugins: { legend: { display: false } },
                            scales: { x: { beginAtZero: true }, y: { grid: { display: false } } } }
                    });
                }
                chartsInitialized = true;
            })
            .catch(function(err) { console.warn("[FoodBridge] Analytics error:", err); });
    }

    // ── Load NGO Profile ───────────────────────────────────────────────────
    function loadNgoProfile() {
        NgoService.getNgoProfile()
            .then(function(res) { 
                $scope.ngoProfile = res.data; 
                console.log("[FoodBridge] NGO profile loaded:", res.data);
            })
            .catch(function(err) { 
                console.warn("[FoodBridge] Profile error:", err); 
                $scope.ngoProfile = {};
            });
    }

    function parseOptionalCoordinate(value, label) {
        if (value === null || value === undefined || value === "") {
            return { ok: true, value: null };
        }
        var parsed = parseFloat(value);
        if (!isFinite(parsed)) {
            return { ok: false, message: "Invalid " + label + " value." };
        }
        return { ok: true, value: parsed };
    }

    $scope.startEditProfile = function() {
        $scope.profileForm = {
            name: $scope.ngoProfile.name,
            phone: $scope.ngoProfile.phone,
            address: $scope.ngoProfile.address,
            latitude: $scope.ngoProfile.latitude,
            longitude: $scope.ngoProfile.longitude
        };
        $scope.editProfile = true;
    };
    $scope.cancelEditProfile = function() { $scope.editProfile = false; $scope.profileForm = {}; };
    $scope.saveProfile = function() {
        var latResult = parseOptionalCoordinate($scope.profileForm.latitude, "latitude");
        if (!latResult.value) {
            $scope.error = latResult.message;
            return;
        }
        var lngResult = parseOptionalCoordinate($scope.profileForm.longitude, "longitude");
        if (!lngResult.value) {
            $scope.error = lngResult.message;
            return;
        }

        var payload = angular.extend({}, $scope.profileForm, {
            latitude: latResult.value,
            longitude: lngResult.value
        });

        NgoService.updateNgoProfile(payload)
            .then(function(res) {
                if (res && res.data) {
                    $scope.ngoProfile.name    = res.data.name || $scope.ngoProfile.name;
                    $scope.ngoProfile.phone   = res.data.phone || $scope.ngoProfile.phone;
                    $scope.ngoProfile.address = res.data.address || $scope.ngoProfile.address;
                    if (Object.prototype.hasOwnProperty.call(res.data, "latitude")) {
                        $scope.ngoProfile.latitude = res.data.latitude;
                    }
                    if (Object.prototype.hasOwnProperty.call(res.data, "longitude")) {
                        $scope.ngoProfile.longitude = res.data.longitude;
                    }
                }
                $scope.editProfile = false;
                $scope.successMsg = "Profile updated successfully!";
                setTimeout(function() { $scope.successMsg = null; }, 3000);
            })
            .catch(function(err) {
                var detail = (err && err.data && err.data.detail) ? err.data.detail : null;
                if (Array.isArray(detail)) {
                    detail = detail.map(function(d) { return d.msg || JSON.stringify(d); }).join(", ");
                }
                $scope.error = detail ? ("Could not update profile: " + detail) : ("Could not update profile. (HTTP " + (err.status || "unknown") + ")");
            });
    };

    // Status helpers
    var ACTIVE_STATUSES   = ["pending", "accepted", "assigned", "in_progress"];
    var INACTIVE_STATUSES = ["completed", "cancelled"];

    // Get NGO ID from localStorage to properly scope deliveries
    function getStoredNgoId() {
        try {
            // For NGO users, use fb_ngo_id (the NGO entity ID)
            // For other users, use fb_user_id (their user ID)
            return window.localStorage.getItem('fb_ngo_id') || window.localStorage.getItem('fb_user_id') || null;
        } catch (e) {
            console.warn("Cannot access localStorage:", e);
            return null;
        }
    }
    var loggedInNgoId = getStoredNgoId();
    var loggedInNgoIdStr = loggedInNgoId ? String(loggedInNgoId) : null;

    function isUuidMatch(donationNgoId, currentNgoId) {
        if (!donationNgoId || !currentNgoId) return false;
        return String(donationNgoId).toLowerCase() === String(currentNgoId).toLowerCase();
    }

    function normalizeStatus(status) {
        if (!status) return '';
        return String(status).toLowerCase().trim();
    }

    function loadNgoDashboard() {
      if (!$scope.availableDonations.length && !$scope.deliveries.length) {
          $scope.loading = true;
      }
      loadAvailableVolunteers();

      var listDone = false;
      var trackingDone = false;
      var listErr = null;
      var trackingErr = null;

      function maybeFinalizeDashboardLoad() {
        if (!(listDone && trackingDone)) {
          return;
        }
        $scope.loading = false;

        // Only show critical alert when delivery tracking itself failed
        // (because this powers the "Active Deliveries" panel).
        var trackingCritical = trackingErr && (!trackingErr.status || trackingErr.status >= 500);
        var listCritical = listErr && (!listErr.status || listErr.status >= 500);

        if (trackingCritical) {
          $scope.error = "Could not load delivery tracking. Please check your connection or contact support.";
        } else if (listCritical && !$scope.deliveries.length) {
          // Keep a fallback for complete dashboard failures, but avoid
          // false alerts when tracking data is already visible.
          $scope.error = "Could not load donations. Please check your connection or contact support.";
        } else {
          $scope.error = null;
        }
      }

      // Ensure frontend specifically hits /donations/pending for incoming tab as required
      DonationService.getPendingDonations()
        .then(function(res) {
          $scope.availableDonations = res.data || [];
          $scope.notificationCount = $scope.availableDonations.length;
          console.log("[FoodBridge] Pending donations loaded:", $scope.availableDonations.length);
        })
        .catch(function(err) {
          console.error('[FoodBridge] Failed to load pending donations:', err);
        });

      // Load core donations list (used for analytics/accepted/completed cards)
      DonationService.getDonations()
        .then(function (res) {
          var all = res.data || [];
          console.log("[FoodBridge] Fetched donations for NGO dashboard:", all.length, "donations");
          console.log("[FoodBridge] NGO ID for filtering:", loggedInNgoIdStr);
          console.log("[FoodBridge] Sample donation ngo_id:", all.length > 0 ? all[0].ngo_id : "N/A");

          // Fixed filtering with proper UUID comparison
          $scope.acceptedDonations = all.filter(function(d) {
            var statusOk = normalizeStatus(d.status) === 'accepted';
            var ngoMatch = !loggedInNgoIdStr || isUuidMatch(d.ngo_id, loggedInNgoIdStr);
            return statusOk && ngoMatch;
          });

          console.log("[FoodBridge] Filtered accepted donations:", $scope.acceptedDonations.length);
          console.log("[FoodBridge] Filtered distribution records:", $scope.distributionRecords.length);
        })
        .catch(function (err) {
          listErr = err;
          console.error('[FoodBridge] NGO donations list load error:', err);
          $scope.acceptedDonations = [];
        })
        .finally(function () {
          listDone = true;
          maybeFinalizeDashboardLoad();
        });

      // Load delivery tracking independently so Active Deliveries can render
      // even if /donations list endpoint has issues.
      NgoService.getDeliveryTracking()
        .then(function(trackingRes) {
          $scope.deliveries = trackingRes.data || [];
          console.log("[FoodBridge] NGO Dashboard deliveries:", $scope.deliveries.length, "ngoId:", loggedInNgoId);
          if ($scope.activeTrackingDonationId) {
            var activeDelivery = $scope.deliveries.find(function(d) {
              return String(d.id || d.donation_id) === String($scope.activeTrackingDonationId);
            });
            if (activeDelivery) {
              $scope.trackVolunteer(activeDelivery, { preserveSection: true, silent: true });
            }
          }
        })
        .catch(function(err) {
          trackingErr = err;
          console.error('[FoodBridge] Failed to load delivery tracking:', err);
          $scope.deliveries = [];
        })
        .finally(function() {
          trackingDone = true;
          maybeFinalizeDashboardLoad();
        });

      AIService.getHungerHeatmap().then(function(res) {
        $scope.hungerHeatmap = res.data;
      });

      // Always load distribution records from their own source to ensure consistency
      loadDistributionRecords();
    }
    loadNgoDashboard();
    loadNgoStats();
    loadNgoProfile();
    loadAllVolunteers();
    loadInventory();
    loadAvailableVolunteers();

    // Auto-refresh mechanism every 10 seconds for real-time updates
    var refreshInterval = $interval(function() {
        loadNgoDashboard();
        loadNgoStats();
        loadAvailableVolunteers();
        // loadDistributionRecords() is now called inside loadNgoDashboard()
    }, 10000);
    
    // Live tracking for NGO
    var ngoTrackingInterval = null;
    var currentNgoTrackingDonationId = null;
    var ngoTrackedDonation = null;
    var ngoVolMarker = null;
    var ngoRoutePolyline = null;
    
    $scope.startLiveTracking = function(donationId) {
      if (currentNgoTrackingDonationId === donationId) return;
      $scope.stopLiveTracking();
      
      console.log('[NGO] Starting live tracking for:', donationId);
      currentNgoTrackingDonationId = donationId;
      
      // Connect to WebSocket for real-time updates
      LiveTrackingService.connect(donationId, function(location) {
        console.log('[NGO] Volunteer location update:', location);
        $scope.$apply(function() {
          $scope.latestVolunteerLocation = location;
          // Update map with new location
          updateNgoMapWithLocation(location, location.status);
        });
      }, function(newStatus) {
        console.log('[NGO] Donation status changed:', newStatus);
        $scope.$apply(function() {
          loadNgoDashboard(); // Reload to get updated status
          if (ngoTrackedDonation) {
            ngoTrackedDonation.status = newStatus;
          }
        });
      });
      
      // Also poll as backup every 5 seconds
      ngoTrackingInterval = $interval(function() {
        LiveTrackingService.getLocation(donationId).then(function(res) {
          if (res.data && res.data.has_location) {
            var loc = res.data;
            $scope.$apply(function() {
              $scope.latestVolunteerLocation = {
                latitude: loc.latitude,
                longitude: loc.longitude,
                timestamp: loc.timestamp,
                status: loc.donation_status
              };
            });
            // Update map with polled location
            updateNgoMapWithLocation(loc, loc.donation_status);
          }
        }).catch(function(err) {
          console.warn('[NGO] Poll location error:', err);
        });
      }, 5000);
    };
    
    // Update NGO map with location and route
    function updateNgoMapWithLocation(location, status) {
      if (!map || !location) return;
      
      var headingToNgo = status === 'in_progress' || status === 'picked_up' || status === 'delivered';
      
      // Find tracked donation if not stored
      if (!ngoTrackedDonation && currentNgoTrackingDonationId) {
        ngoTrackedDonation = $scope.acceptedDonations.find(function(d) {
          return d.id === currentNgoTrackingDonationId;
        });
      }
      
      if (!ngoTrackedDonation) return;
      
      var volPos = { lat: location.latitude, lng: location.longitude };
      var ngoPos = {
        lat: parseFloat(ngoTrackedDonation.ngo_latitude),
        lng: parseFloat(ngoTrackedDonation.ngo_longitude)
      };
      
      // NGO always shows route to NGO
      if (!ngoPos.lat || !ngoPos.lng) return;
      
      var color = '#4CAF50';
      
      // Update or create volunteer marker
      if (ngoVolMarker) {
        MapService.moveMarkerSmoothly(ngoVolMarker, volPos);
      } else {
        ngoVolMarker = MapService.createMarker(map, volPos, 'vehicle', 'Volunteer');
      }
      
      // Clear and redraw route
      MapService.clearRoute(ngoRoutePolyline);
      
      MapService.drawRoute(map, volPos, ngoPos, [], color, { profile: 'driving' })
        .then(function(routeRes) {
          ngoRoutePolyline = routeRes.polyline;
          map.fitBounds(routeRes.bounds, { padding: [50, 50] });
          console.log('[NGO] Route updated, distance:', routeRes.distanceText);
        })
        .catch(function(err) {
          console.warn('[NGO] Route update failed:', err);
        });
    }
    
    $scope.stopLiveTracking = function() {
      if (ngoTrackingInterval) {
        $interval.cancel(ngoTrackingInterval);
        ngoTrackingInterval = null;
      }
      LiveTrackingService.disconnect();
      currentNgoTrackingDonationId = null;
      ngoTrackedDonation = null;
      $scope.latestVolunteerLocation = null;
      
      // Clean up map markers
      if (ngoVolMarker && map) {
        MapService.removeMarker(map, ngoVolMarker);
        ngoVolMarker = null;
      }
      MapService.clearRoute(ngoRoutePolyline);
      ngoRoutePolyline = null;
    };

    $scope.$on('$destroy', function() {
        if (refreshInterval) {
            $interval.cancel(refreshInterval);
        }
        $scope.stopLiveTracking();
    });

    $scope.loadPendingVolunteers = function() {
        NgoService.getPendingVolunteers()
            .then(function(res) { $scope.pendingVolunteers = res.data; })
            .catch(function(err) { console.error("Failed to load pending volunteers:", err); });
    };
    $scope.loadPendingVolunteers();

    // STEP 3 FIX: Removed duplicate approveVolunteer / rejectVolunteer definitions.
    // The correct definitions with confirm dialogs are above (lines ~1064-1081).

    // ── WebSocket real-time updates (extended) ─────────────────────────────
    $scope.$on('ws_update', function() {
        loadNgoDashboard();
        loadNgoStats();
        if ($scope.activeSection === 'volunteers')       { $scope.loadPendingVolunteers(); loadAllVolunteers(); }
        if ($scope.activeSection === 'inventory')        { loadInventory(); }
        if ($scope.activeSection === 'distribution')     { loadDistributionRecords(); }
        if ($scope.activeSection === 'food-testing')     { loadReceivedDonations(); }
        if ($scope.activeSection === 'dist-management')  { loadDistributionQueue(); }
        if ($scope.activeSection === 'waste-management') { loadWasteList(); }
        if ($scope.activeSection === 'beneficiaries')    { loadBeneficiaries(); }
    });

    // ── Accept / Claim Donation ────────────────────────────────────────────
    $scope.claimDonation = function (donation) {
      try {
        var donationId = donation.id || donation.donation_id;
        console.log("[FoodBridge] claimDonation called for donation ID:", donationId);
        console.log("[FoodBridge] Full donation object:", donation);
        if (!donationId) {
          console.error("[FoodBridge] No donation ID found!", donation);
          $scope.error = "Cannot identify donation. Please refresh and try again.";
          return;
        }
        $scope.loading = true;
        $scope.error = null;
        $scope.successMsg = null;
        
        DonationService.claimDonation(donationId)
          .then(function (res) {
            console.log("[FoodBridge] NGO accept success: ", res.data);
            // Remove from availableDonations immediately for better UX
            var donationIdStr = String(donationId);
            $scope.availableDonations = $scope.availableDonations.filter(function(d) { 
              return String(d.id || d.donation_id) !== donationIdStr; 
            });
            // Add the accepted donation to deliveries for immediate display in Delivery Tracking
            var acceptedDonation = res.data;
            if (acceptedDonation) {
              // Ensure it has proper status for display
              acceptedDonation.status = 'accepted';
              // Add to deliveries if not already there
              var alreadyExists = $scope.deliveries.some(function(d) { 
                return String(d.id || d.donation_id) === String(acceptedDonation.id); 
              });
              if (!alreadyExists) {
                $scope.deliveries.push(acceptedDonation);
              }
              console.log("[FoodBridge] Added to deliveries for Delivery Tracking tab");
            }
            loadNgoDashboard(); 
            loadNgoStats();
            $scope.successMsg = "Donation accepted! It will appear in Delivery Tracking for volunteer assignment.";
            setTimeout(function() { $scope.successMsg = null; }, 4000);
          })
          .catch(function (err) {
            console.error("[FoodBridge] Claim donation error:", err);
            var msg = "Could not accept donation.";
            if (err.data && err.data.detail) {
              msg = err.data.detail;
            } else if (err.status) {
              msg = "Error (" + err.status + "): Could not accept donation.";
            }
            $scope.error = msg;
            setTimeout(function() { $scope.error = null; }, 5000);
          })
          .finally(function() {
            $scope.loading = false;
          });
      } catch (e) {
        console.error("[FoodBridge] Exception in claimDonation:", e);
        $scope.error = "An unexpected error occurred: " + e.message;
        setTimeout(function() { $scope.error = null; }, 5000);
      }
    };
    $scope.viewDonationDetails = function(d) { $scope.selectedDonation = d; };
    $scope.closeDonationDetails = function() { $scope.selectedDonation = null; };

    // ── Confirm Donation Received (Lifecycle Final Step) ──────────────────
    $scope.confirmReceived = function(donation) {
        var donationId = donation.id || donation.donation_id;
        if (!donationId) return;

        if (!confirm("Are you sure you want to mark this donation as RECEIVED? This is the final step in the tracking cycle.")) {
            return;
        }

        donation.confirming = true;
        DonationService.confirmDonationReceived(donationId)
            .then(function(res) {
                donation.status = 'completed'; // Legacy sync
                donation.lifecycle_status = 'RECEIVED';
                flashSuccess("🎉 Donation officially received and lifecycle completed!", 4000);
                
                // Refresh data to show in Distribution records
                loadNgoDashboard();
                loadNgoStats();
                loadInventory();
                
                // If it was the active tracking item, update it
                if ($scope.activeTracking && (String($scope.activeTracking.id) === String(donationId))) {
                    $scope.activeTracking.lifecycle_status = 'RECEIVED';
                    $scope.activeTracking.timelineSteps = $rootScope.getTimelineSteps($scope.activeTracking);
                }
            })
            .catch(function(err) {
                var msg = (err.data && err.data.detail) ? err.data.detail : "Could not confirm receipt.";
                alert("Error: " + msg);
            })
            .finally(function() {
                donation.confirming = false;
            });
    };

    // ── AI Delivery Partner Assignment ───────────────────────────────────────────────
    $scope.aiAssignVolunteer = function (donation, event) {
      var donationId = donation.id || donation.donation_id;
      if (!donationId) {
          alert("Invalid donation ID for assignment.");
          return;
      }
      // NOTE: Do NOT guard on availableVolunteers.length here.
      // The AI service independently finds the best volunteer —
      // the frontend list may be empty but AI can still succeed.

      var btn = event ? event.currentTarget : null;
      var originalText = btn ? btn.innerHTML : "";
      if (btn) {
         btn.disabled = true;
         btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Getting AI recommendation...';
      }
      console.log("[FoodBridge] aiAssignVolunteer called | donation_id:", donationId, "| status:", donation.status);

      AIService.assignVolunteer(donationId)
        .then(function (aiRes) {
            var volName = aiRes.data.volunteer_name || "a volunteer";
            var conf = parseFloat(aiRes.data.confidence_score || 0).toFixed(0);
            var volId = aiRes.data.best_volunteer_id;
            var distance = aiRes.data.distance_km || "N/A";

            if (!volId) {
                alert("No suitable volunteer found by AI. Please use manual assignment.");
                if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
                return;
            }

            var confirmAssign = confirm(
                "Assign " + volName + " (" + distance + " km away) – 🟢 Available – Confidence: " + conf + "% ?"
            );

            if (!confirmAssign) {
                if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
                return;
            }

            if (btn) {
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Assigning...';
            }

            // STEP 6 DEBUG: log assign payload before API call
            console.log("Assign Payload (AI):", donationId, volId);

            DonationService.assignVolunteer(donationId, volId)
              .then(function (res) {
                  console.log("✅ AI Assign Success", res.data);

                  // 🟢 UPDATE UI INSTANTLY — no reload
                  donation.status = "assigned";
                  donation.id = donationId;
                  if (aiRes.data && aiRes.data.reason) {
                      donation.reason = aiRes.data.reason;
                  }
                  $scope.availableDonations = $scope.availableDonations.filter(function(d) { return d.id !== donation.id; });
                  $scope.deliveries.push(donation);

                  alert("✅ Volunteer Assigned Successfully!");

                  if (btn) {
                      btn.disabled = true;
                      btn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Assigned';
                  }
              })
              .catch(function (err) {
                  console.error("❌ AI Assign Failed", err);
                  var msg = (err.data && err.data.detail) ? err.data.detail : "Assignment failed. Check backend.";
                  alert("❌ " + msg);
                  if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
              });
        })
        .catch(function (err) {
            console.error("❌ AI recommendation FAILED", err);
            var msg = (err.data && err.data.detail) ? err.data.detail : "AI service unavailable. Please use manual assignment.";
            alert(msg);
            if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
        });
    };

    // ── Manual Delivery Partner Assignment ──────────────────────────────────────────
    $scope.manualAssignVolunteer = function (donation, volunteerId) {
        var donationId = donation.id || donation.donation_id;
        if (!donationId) {
            alert("Invalid donation ID for assignment.");
            return;
        }
        if (!volunteerId) {
            alert("Invalid volunteer selected.");
            return;
        }
        // STEP 6 DEBUG: log assign payload before API call
        console.log("Assign Payload (Manual):", donationId, volunteerId);

        DonationService.assignVolunteer(donationId, volunteerId)
          .then(function (res) {
               console.log("volunteer assign: ", res.data); // DEBUG + SAFETY
               console.log("✅ Manual Assign Success", res.data);
               flashSuccess("✅ Volunteer Assigned Successfully!", 3000);
               donation.status = 'assigned';
               donation.id = donationId;
               donation.selectedVolunteerId = null;
               // 🟢 UPDATE UI INSTANTLY — do NOT re-check volunteers or reload
               $scope.availableDonations = $scope.availableDonations.filter(function(d) { return d.id !== donation.id; });
               var alreadyIn = $scope.deliveries.some(function(d) { return d.id === donation.id; });
               if (!alreadyIn) { $scope.deliveries.push(donation); }
           })
          .catch(function (err) {
               console.error("❌ Assign Error", err);
               var msg = (err.data && err.data.detail) ? err.data.detail : "Assignment failed. Check backend.";
               alert("❌ " + msg);
               $scope.error = msg;
          });
    };

    // Backward-compatible handler used by legacy button in ngo.html
    $scope.assignVolunteer = function(donation) {
        var donationId = donation && (donation.id || donation.donation_id);
        if (!donationId) {
            alert("Invalid donation selected.");
            return;
        }
        var selectedVolunteerId = donation.selectedVolunteerId;
        if (!selectedVolunteerId && $scope.availableVolunteers.length > 0) {
            selectedVolunteerId = $scope.availableVolunteers[0].id;
        }
        if (!selectedVolunteerId) {
            alert("No available volunteers to assign.");
            return;
        }
        $scope.manualAssignVolunteer({ id: donationId, donation_id: donationId, status: donation.status || 'accepted' }, selectedVolunteerId);
    };

    // AI-powered distribution assignment for tested donations
    $scope.aiAssignDistributionPartner = function(donation, event) {
        var donationId = donation && (donation.id || donation.donation_id);
        if (!donationId) {
            alert("Invalid donation selected.");
            return;
        }

        var btn = event ? event.currentTarget : null;
        var originalText = btn ? btn.innerHTML : "";
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>AI Assigning...';
        }

        console.log("[FoodBridge] aiAssignDistributionPartner called | donation_id:", donationId);
        
        if (!donation.selectedBeneficiaryId) {
            donation._beneficiaryRequired = true;
            if (typeof flashError === 'function') flashError("Please select a recipient / beneficiary first.");
            else alert("Please select a recipient / beneficiary first.");
            if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
            return;
        }
        donation._beneficiaryRequired = false;

        NgoService.assignDistributionPartner(donationId, donation.selectedBeneficiaryId)
            .then(function(res) {
                var data = res.data;
                if (!data.success) {
                    alert(data.detail || "Assignment failed.");
                    if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
                    return;
                }

                var partnerName = data.partner_name || "a partner";
                var distance = data.distance_km || "N/A";
                var isUrgent = data.is_urgent;
                var reason = data.reason || "";

                var confirmMsg = "🤖 AI Assignment\n\n";
                confirmMsg += "Partner: " + partnerName + "\n";
                confirmMsg += "Distance: " + distance + " km\n";
                confirmMsg += "Priority: " + (isUrgent ? "⚠️ URGENT" : "Normal") + "\n";
                confirmMsg += "\n" + reason + "\n\nConfirm assignment?";

                var confirmAssign = confirm(confirmMsg);

                if (!confirmAssign) {
                    if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
                    return;
                }

                // Update UI
                donation.assigned_partner_id = data.partner_id;
                donation.assigned_partner_name = partnerName;
                donation.assignment_reason = reason;
                donation.assignment_score = data.score;
                donation.is_urgent_assignment = isUrgent;
                donation.assignment_type = "ai";
                donation.volunteer_id = data.partner_id;
                donation.distribution_otp = data.distribution_otp;
                donation.status = 'assigned';
                donation.distribution_status = 'in_progress';

                flashSuccess("✅ Partner " + partnerName + " assigned for distribution!", 4000);
            })
            .catch(function(err) {
                var detail = "Assignment failed";
                if (err && err.data) {
                    if (typeof err.data.detail === 'string') {
                        detail = err.data.detail;
                    } else if (typeof err.data.message === 'string') {
                        detail = err.data.message;
                    } else if (Array.isArray(err.data.detail)) {
                        detail = err.data.detail.map(function(e) { return e.msg || JSON.stringify(e); }).join(', ');
                    }
                }
                if (!detail || detail === "Assignment failed") {
                    detail = "Assignment failed. No Delivery Partner available nearby. Try manual assignment.";
                }
                alert(detail);
                console.warn("[FoodBridge] Distribution assignment error:", err);
            })
            .finally(function() {
                if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
            });
    };

    // Manual distribution assignment - open modal to select volunteer
    $scope.manualAssignDistributionPartner = function(donation) {
        console.log("[FoodBridge] manualAssignDistributionPartner called", donation);
        var donationId = donation && (donation.id || donation.donation_id);
        if (!donationId) {
            alert("Invalid donation selected.");
            return;
        }

        // If already assigned for distribution, show message
        var currentStatus = (donation.status || "").toLowerCase();
        if (currentStatus === 'assigned' && (donation.volunteer_id || donation.assigned_partner_id)) {
            var partnerName = donation.assigned_partner_name || donation.volunteer_name || "a partner";
            alert("This donation already has " + partnerName + " assigned.");
            return;
        }

        // Set selected task and open modal
        $scope.selectedDistributionTask = donation;
        $scope.showManualAssignModal = true;
        
        // Show vanilla JS modal
        var modalEl = document.getElementById('manualAssignModal');
        if(modalEl) modalEl.style.display = 'block';
        
        console.log("[FoodBridge] Modal should show now, showManualAssignModal:", $scope.showManualAssignModal);
        $scope.selectedManualVolunteer = null;
        $scope.manualAssignLoading = true;

        // Load available volunteers
        NgoService.getAvailableVolunteers()
            .then(function(res) {
                $scope.availableVolunteersForManual = res.data || [];
                console.log("[FoodBridge] Manual assignment volunteers loaded:", $scope.availableVolunteersForManual.length, JSON.stringify(res.data));
                $scope.manualAssignLoading = false;
            })
            .catch(function(err) {
                console.warn("[FoodBridge] Failed to load for manual assign:", err);
                alert("Failed to load volunteers: " + (err.data && err.data.detail ? err.data.detail : "Unknown error"));
                $scope.manualAssignLoading = false;
                $scope.showManualAssignModal = false;
            });
    };

    // Confirm manual assignment
    $scope.confirmManualDistributionAssign = function() {
        var donation = $scope.selectedDistributionTask;
        var volunteerId = $scope.selectedManualVolunteer;

        if (!volunteerId) {
            alert("Please select a volunteer.");
            return;
        }

        var donationId = donation && (donation.id || donation.donation_id);
        if (!donationId) {
            alert("Invalid donation.");
            return;
        }

        var btn = document.getElementById('confirm-manual-assign-btn');
        var originalText = btn ? btn.innerHTML : "";
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Assigning...';
        }

        if (!donation.selectedBeneficiaryId) {
            donation._beneficiaryRequired = true;
            alert("Please select a recipient / beneficiary first.");
            if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
            return;
        }
        donation._beneficiaryRequired = false;

        NgoService.assignDistributionPartnerManual(donationId, volunteerId, donation.selectedBeneficiaryId)
            .then(function(res) {
                var data = res.data;
                if (!data.success) {
                    alert(data.detail || "Assignment failed.");
                    return;
                }

                // Update UI
                donation.assigned_partner_id = data.partner_id;
                donation.assigned_partner_name = data.partner_name;
                donation.assignment_type = "manual";
                donation.volunteer_id = data.partner_id;
                donation.distribution_otp = data.distribution_otp;
                donation.status = 'assigned';
                donation.distribution_status = 'in_progress';

                $scope.showManualAssignModal = false;
                var modalEl = document.getElementById('manualAssignModal');
                if(modalEl) modalEl.style.display = 'none';
                flashSuccess("✅ Partner " + data.partner_name + " assigned manually!", 4000);
            })
            .catch(function(err) {
                var detail = err.data && err.data.detail ? err.data.detail : "Assignment failed";
                alert(detail);
            })
            .finally(function() {
                if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
            });
    };

    // Close manual assign modal
    $scope.closeManualAssignModal = function() {
        $scope.showManualAssignModal = false;
        $scope.selectedDistributionTask = null;
        $scope.selectedManualVolunteer = null;
        var modalEl = document.getElementById('manualAssignModal');
        if(modalEl) modalEl.style.display = 'none';
    };

    // ── Chat Feature ─────────────────────────────────────────────────────────
    $scope.chatPanelOpen = false;
    $scope.chatMessages = [];
    $scope.chatParticipants = [];
    $scope.chatSelectedReceiver = null;
    $scope.chatMessageText = "";
    $scope.chatLoading = false;
    $scope.chatSending = false;
    $scope.currentDonationId = null;
    $scope.currentUserId = null;

    function getCurrentUserId() {
      var userId = localStorage.getItem("fb_user_id");
      if (userId) {
        try { return JSON.parse(userId); } catch(e) { return userId; }
      }
      return null;
    }
    $scope.currentUserId = getCurrentUserId();

    $scope.openChat = function(donation, targetRole) {
      var donationId = donation.id || donation;
      console.log("Opening chat for donation:", donationId, "with role:", targetRole);
      $scope.chatPanelOpen = true;
      $scope.currentDonationId = donationId;
      $scope.chatMessageText = "";
      $scope.chatLoading = true;
      $scope.selectedReceiverName = "";
      $scope.chatError = "";

      var token = AuthService.getToken();
      ChatService.connect(donationId, token);

      ChatService.getParticipants(donation.id).then(function(res) {
        $scope.chatParticipants = res.data.participants || [];
        console.log("Participants:", $scope.chatParticipants);
        
        if (targetRole) {
          var target = $scope.chatParticipants.find(function(p) { 
            return p.role && p.role.toLowerCase() === targetRole.toLowerCase(); 
          });
          if (target) {
            $scope.chatSelectedReceiver = target.user_id;
            $scope.selectedReceiverId = target.user_id;
            $scope.selectedReceiverName = target.name;
            console.log("Selected receiver:", target.user_id, target.name);
          }
        } else if ($scope.chatParticipants.length > 0) {
          var others = $scope.chatParticipants.filter(function(p) {
            return p.user_id !== $scope.currentUserId;
          });
          if (others.length > 0) {
            $scope.chatSelectedReceiver = others[0].user_id;
            $scope.selectedReceiverId = others[0].user_id;
            $scope.selectedReceiverName = others[0].name;
          }
        }
      }).catch(function(err) {
        console.error("Failed to load participants:", err);
      });

      ChatService.getMessages(donation.id).then(function(res) {
        $scope.chatMessages = res.data || [];
        $scope.chatLoading = false;
        scrollChatToBottom();
      }).catch(function(err) {
        console.error("Failed to load messages:", err);
        $scope.chatLoading = false;
      });
    };

    $scope.closeChat = function() {
      $scope.chatPanelOpen = false;
      if ($scope.currentDonationId) {
        ChatService.disconnect();
      }
    };

    $scope.sendChatMessage = function() {
      console.log("sendChatMessage called:", { chatMessageText: $scope.chatMessageText, chatSelectedReceiver: $scope.chatSelectedReceiver, currentDonationId: $scope.currentDonationId });
      if (!$scope.chatMessageText || !$scope.chatSelectedReceiver || !$scope.currentDonationId) {
        return;
      }
      $scope.chatSending = true;

      ChatService.sendMessage($scope.chatSelectedReceiver, $scope.currentDonationId, $scope.chatMessageText)
        .then(function(res) {
          $scope.chatMessageText = "";
          if (res.data && res.data.data) {
            var msgs = res.data.data;
            if (msgs.id) {
              $scope.chatMessages.push(msgs);
            }
          }
          scrollChatToBottom();
        }).catch(function(err) {
          console.error("Send message error:", err);
        }).finally(function() {
          $scope.chatSending = false;
        });
    };

    $scope.chatSendOnEnter = function(event) {
      if (event.key === 'Enter') {
        $scope.sendChatMessage();
      }
    };

    function scrollChatToBottom() {
      setTimeout(function() {
        var container = document.getElementById("chatMessagesContainer");
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      }, 100);
    }

    $scope.$on("chat:message", function(event, data) {
      if (data.donation_id === $scope.currentDonationId) {
        var exists = $scope.chatMessages.some(function(m) { return m.id === data.id; });
        if (!exists) {
          $scope.chatMessages.push(data);
          scrollChatToBottom();
        }
      }
    });

    $scope.$on("chat:poll-update", function(event, messages) {
      if ($scope.currentDonationId) {
        var filtered = messages.filter(function(m) { return m.donation_id === $scope.currentDonationId; });
        if (filtered.length > 0) {
          $scope.chatMessages = filtered;
        }
      }
    });

    $scope.$on("$destroy", function() {
      ChatService.disconnect();
    });

    // ── Live Map Tracking (preserved) ──────────────────────────────────────
    function parseMapCoordinate(value) {
        var n = parseFloat(value);
        return isFinite(n) ? n : null;
    }

    function normalizeTrackingStatus(statusValue) {
        if (statusValue && typeof statusValue === 'object' && statusValue.value) {
            return String(statusValue.value).toLowerCase();
        }
        return String(statusValue || '').toLowerCase();
    }

    function resolveNgoDestinationFromDelivery(del, trackingData) {
        var lat = parseMapCoordinate((trackingData && trackingData.ngo_latitude) || del.ngo_latitude);
        var lng = parseMapCoordinate((trackingData && trackingData.ngo_longitude) || del.ngo_longitude);
        if (lat === null || lng === null) return null;
        return {
            lat: lat,
            lng: lng,
            label: (trackingData && trackingData.ngo_name) || del.ngo_name || 'NGO Destination',
            address: (trackingData && trackingData.ngo_address) || del.ngo_address || ''
        };
    }

    $scope.trackVolunteer = function(del, options) {
        options = options || {};
        var shouldFocusTracking = !options.preserveSection;
        var silentRefresh = !!options.silent;
        var donationId = del.id || del.donation_id;
        
        // Store reference for live tracking
        ngoTrackedDonation = del;
        
        // Start live tracking
        if (donationId) {
            $scope.startLiveTracking(donationId);
        }
        
        if (!donationId) {
            $scope.activeTracking = { food_type: del.food_type, distance_remaining: 'Not Assigned', time_remaining: '--' };
            return;
        }
        $scope.activeTrackingDonationId = String(donationId);
        if (shouldFocusTracking) {
            $scope.activeSection = 'tracking';
            $scope.mapMode = 'tracking';
        } else if ($scope.activeSection === 'tracking') {
            $scope.mapMode = 'tracking';
        }

        var normalizedStatus = normalizeTrackingStatus(del.status);
        if(normalizedStatus === 'pending') { $scope.trackingStage = 1; $scope.trackingProgress = 15; }
        else if(normalizedStatus === 'accepted' || normalizedStatus === 'assigned') { $scope.trackingStage = 2; $scope.trackingProgress = 40; }
        else if(normalizedStatus === 'in_progress' || normalizedStatus === 'picked_up') { $scope.trackingStage = 3; $scope.trackingProgress = 70; }
        else if(normalizedStatus === 'completed' || normalizedStatus === 'delivered') { $scope.trackingStage = 4; $scope.trackingProgress = 100; }

        $scope.activeTracking = {
            food_type: del.food_type,
            pickup_location: del.pickup_location,
            ngo_address: del.ngo_address,
            distance_remaining: 'Tracking...',
            time_remaining: '...'
        };
        setTimeout(function() { if (!map) initNgoMap(); }, 300);

        DonationService.trackDelivery(donationId)
         .then(function(res) {
            $scope.error = null;
            var trackingData = res.data || {};
            var volPos = {
                lat: parseMapCoordinate(trackingData.latitude),
                lng: parseMapCoordinate(trackingData.longitude)
            };
            var donorPos = {
                lat: parseMapCoordinate(del.pickup_latitude || del.latitude || trackingData.pickup_latitude),
                lng: parseMapCoordinate(del.pickup_longitude || del.longitude || trackingData.pickup_longitude)
            };
            var ngoPos = resolveNgoDestinationFromDelivery(del, trackingData);
            var effectiveStatus = normalizeTrackingStatus(trackingData.status || del.status);
            var headingToNgo = effectiveStatus === 'in_progress' || effectiveStatus === 'picked_up';
            var destination = (headingToNgo && ngoPos) ? ngoPos : donorPos;
            var routeProfile = headingToNgo ? 'cycling' : 'driving';

            if (volPos.lat === null || volPos.lng === null || !destination || destination.lat === null || destination.lng === null) {
                $scope.activeTracking.distance_remaining = 'Unavailable';
                $scope.activeTracking.time_remaining = '--';
                if (!silentRefresh) {
                    $scope.error = "Tracking coordinates are incomplete for this delivery.";
                }
                return;
            }

            MapService.clearRoute(currentPolyline);
            if(volunteerMarker) { try { map.removeLayer(volunteerMarker); } catch(e){} }
            if(donorMarker) { try { map.removeLayer(donorMarker); } catch(e){} }
            if(ngoMarker) { try { map.removeLayer(ngoMarker); } catch(e){} }

            volunteerMarker = MapService.createMarker(map, volPos, 'vehicle', 'Volunteer');
            donorMarker = MapService.createMarker(map, donorPos, 'donor', 'Pickup Point');
            if (ngoPos) {
                ngoMarker = MapService.createMarker(map, ngoPos, 'ngo', ngoPos.label);
            }

            MapService.drawRoute(map, volPos, destination, [], '#0d6efd', { profile: routeProfile }).then(function(routeRes) {
                currentPolyline = routeRes.polyline;
                map.fitBounds(routeRes.bounds);
                $scope.$apply(function() {
                    $scope.activeTracking.distance_remaining = routeRes.distanceText;
                    $scope.activeTracking.time_remaining = routeRes.durationText;
                    if (ngoPos && !$scope.activeTracking.ngo_address) {
                        $scope.activeTracking.ngo_address = ngoPos.address;
                    }
                });
            }).catch(function() {
                $scope.$apply(function() {
                    $scope.activeTracking.distance_remaining = 'Unavailable';
                    $scope.activeTracking.time_remaining = '--';
                });
            });
         })
         .catch(function(err) {
             $scope.activeTracking.distance_remaining = 'Not Assigned';
             $scope.activeTracking.time_remaining = '--';
             var detail = err && err.data && err.data.detail ? String(err.data.detail) : '';
             if (!silentRefresh && detail.toLowerCase().indexOf('available after volunteer receives') !== -1) {
                 $scope.error = "Live tracking starts after volunteer collects the donation.";
             }
            var donorPos = {
                lat: parseMapCoordinate(del.pickup_latitude || del.latitude),
                lng: parseMapCoordinate(del.pickup_longitude || del.longitude)
            };
            if (map && donorPos.lat !== null && donorPos.lng !== null) {
                MapService.clearRoute(currentPolyline);
                if(volunteerMarker) { try { map.removeLayer(volunteerMarker); } catch(e){} }
                if(donorMarker) { try { map.removeLayer(donorMarker); } catch(e){} }
                if(ngoMarker) { try { map.removeLayer(ngoMarker); } catch(e){} }
                map.setView([donorPos.lat, donorPos.lng], 15);
                donorMarker = MapService.createMarker(map, donorPos, 'donor', 'Pickup Point');
            }
         });
    };
  }
]);

// ─────────────────────────────────────────────────────────────────────────────
//  VolunteerController
// ─────────────────────────────────────────────────────────────────────────────
app.controller("VolunteerController", ["$scope", "DonationService", "VolunteerService", "MapService", "$interval", "AuthService", "$http", "API_BASE_URL", "LiveTrackingService", "ChatService", "RouteManager",
  function ($scope, DonationService, VolunteerService, MapService, $interval, AuthService, $http, API_BASE_URL, LiveTrackingService, ChatService, RouteManager) {
      
    $scope.eta = 0;
    $scope.$watch(function() { return RouteManager.eta; }, function(newVal) {
        if (newVal !== null && newVal !== undefined) {
            $scope.eta = newVal;
        }
    });

    $scope.getElapsedTime = function (startTime) {
        if (!startTime) return "0 mins";
        var start = new Date(startTime);
        var now = new Date();
        var diffMs = now - start;
        if (diffMs < 0) return "0 mins";
        return Math.floor(diffMs / 60000) + " mins";
    };

    // ── NEW DASHBOARD STATE ─────────────────────────────────────────────────────
    $scope.volActiveSection = 'overview';
    $scope.volSummary = {};
    $scope.rewardsData = {};
    $scope.activeDelivery = {};
    $scope.certificates = [];
    $scope.volLoading = false;
    $scope.historySearch = '';
    $scope.historyFilter = '';
    $scope.volunteerName = '';
    
    // ── Profile State ──────────────────────────────────────────────────────────
    $scope.volProfile = {};
    $scope.volProfileForm = {};
    $scope.editingVolProfile = false;
    $scope.profileLoading = false;
    $scope.savingVolProfile = false;
    $scope.volProfileSaved = false;
    $scope.currentUserEmail = '';
    
    // Load profile data
    $scope.loadVolProfile = function() {
        $scope.profileLoading = true;
        $http.get(API_BASE_URL + '/auth/profile').then(function(res) {
            var data = res.data;
            $scope.volProfile = {
                name: data.name || '',
                phone: data.phone || '',
                address: data.address || '',
                latitude: data.latitude || null,
                longitude: data.longitude || null,
                email: data.email || ''
            };
            $scope.currentUserEmail = data.email || '';
            $scope.volProfileForm = angular.copy($scope.volProfile);
        }).catch(function(err) {
            console.warn('[Volunteer] Failed to load profile:', err);
        }).finally(function() {
            $scope.profileLoading = false;
        });
    };
    $scope.loadVolProfile();
    
    // Toggle edit mode
    $scope.toggleEditVolProfile = function() {
        if ($scope.editingVolProfile) {
            // Cancel - reset form
            $scope.volProfileForm = angular.copy($scope.volProfile);
        }
        $scope.editingVolProfile = !$scope.editingVolProfile;
        $scope.volProfileSaved = false;
    };
    
    // Save profile
    $scope.saveVolProfile = function() {
        $scope.savingVolProfile = true;
        $scope.volProfileSaved = false;
        
        var payload = {
            name: $scope.volProfileForm.name || '',
            phone: $scope.volProfileForm.phone || '',
            address: $scope.volProfileForm.address || '',
            latitude: $scope.volProfileForm.latitude || null,
            longitude: $scope.volProfileForm.longitude || null
        };
        
        $http.put(API_BASE_URL + '/auth/profile', payload).then(function(res) {
            $scope.volProfile = angular.copy($scope.volProfileForm);
            $scope.volProfileSaved = true;
            $scope.editingVolProfile = false;
            
            // Reload profile to ensure data is fresh from database
            $scope.loadVolProfile();
            
            // Update local storage
            var userStr = window.localStorage.getItem('user');
            if (userStr) {
                var user = JSON.parse(userStr);
                user.name = $scope.volProfile.name;
                window.localStorage.setItem('user', JSON.stringify(user));
            }
        }).catch(function(err) {
            console.error('[Volunteer] Failed to save profile:', err);
            alert('Failed to save profile. Please try again.');
        }).finally(function() {
            $scope.savingVolProfile = false;
        });
    };
    
    // Add global error handler and toast notification
    $scope.showErrorToast = function(message) {
        var existingToast = document.querySelector('.toast-notification.error');
        if (existingToast) {
            existingToast.remove();
        }
        
        var toast = document.createElement('div');
        toast.className = 'toast-notification error toast-error';
        toast.style.cssText = 'position:fixed;top:20px;right:20px;z-index:99999;padding:15px 25px;border-radius:8px;background:#dc3545;color:white;box-shadow:0 4px 12px rgba(0,0,0,0.15);font-weight:500;max-width:350px;';
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(function() {
            toast.style.transition = 'opacity 0.3s';
            toast.style.opacity = '0';
            setTimeout(function() { 
                if (toast.parentNode) document.body.removeChild(toast); 
            }, 300);
        }, 4000);
    };
    
    $scope.showSuccessToast = function(message) {
        var existingToast = document.querySelector('.toast-notification.success');
        if (existingToast) {
            existingToast.remove();
        }
        
        var toast = document.createElement('div');
        toast.className = 'toast-notification success toast-success';
        toast.style.cssText = 'position:fixed;top:20px;right:20px;z-index:99999;padding:15px 25px;border-radius:8px;background:#28a745;color:white;box-shadow:0 4px 12px rgba(0,0,0,0.15);font-weight:500;max-width:350px;';
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(function() {
            toast.style.transition = 'opacity 0.3s';
            toast.style.opacity = '0';
            setTimeout(function() { 
                if (toast.parentNode) document.body.removeChild(toast); 
            }, 300);
        }, 3000);
    };
    
    // Override showToast to use error/success variants
    $scope.showToast = function(message, type) {
        if (type === 'error' || type === 'danger') {
            $scope.showErrorToast(message);
        } else if (type === 'success') {
            $scope.showSuccessToast(message);
        } else {
            // Default toast
            var toast = document.createElement('div');
            toast.className = 'toast-notification';
            toast.style.cssText = 'position:fixed;top:20px;right:20px;z-index:99999;padding:15px 25px;border-radius:8px;background:#6c757d;color:white;box-shadow:0 4px 12px rgba(0,0,0,0.15);';
            toast.textContent = message;
            document.body.appendChild(toast);
            setTimeout(function() {
                toast.style.opacity = '0';
                setTimeout(function() { if (toast.parentNode) document.body.removeChild(toast); }, 300);
            }, 3000);
        }
    };
    
    // Add global HTTP interceptor for error handling
    $http.defaults.transformResponse.push(function(data, headersGetter) {
        return data;
    });
    
    // Helper function to display success rate properly (shows "-" when no deliveries)
    $scope.getSuccessRateDisplay = function() {
        if (!$scope.volSummary || $scope.volSummary.total_deliveries === 0 || $scope.volSummary.total_deliveries === undefined) {
            return '-';
        }
        return ($scope.volSummary.success_rate || 0) + '%';
    };
    
    // Helper function for profile save message
    $scope.getProfileSaveMessage = function() {
        if ($scope.volProfileSaved && $scope.editingVolProfile === false) {
            return 'Profile saved successfully!';
        }
        return '';
    };
    
    // ── Load Delivery Partner Dashboard Data ────────────────────────────────────────
    $scope.loadVolunteerDashboard = function() {
        $scope.volLoading = true;
        
        // Load summary
        VolunteerService.getDashboardSummary().then(function(res) {
            $scope.volSummary = res.data;
        }).catch(function(err) {
            console.warn('[Volunteer] Failed to load summary:', err);
        });
        
        // Load rewards
        VolunteerService.getRewards().then(function(res) {
            $scope.rewardsData = res.data;
        }).catch(function(err) {
            console.warn('[Volunteer] Failed to load rewards:', err);
        });
        
        // Load active delivery
        VolunteerService.getActiveDelivery().then(function(res) {
            $scope.activeDelivery = res.data;
        }).catch(function(err) {
            console.warn('[Volunteer] Failed to load active delivery:', err);
        });
        
        // Auto-refresh active delivery every 10 seconds
        var activeDeliveryRefresh = $interval(function() {
            VolunteerService.getActiveDelivery().then(function(res) {
                $scope.activeDelivery = res.data;
            }).catch(function(err) {
                console.warn('[Volunteer] Failed to refresh active delivery:', err);
            });
        }, 30000);
        
        // Load certificates
        $http.get(API_BASE_URL + '/user/certificates').then(function(res) {
            $scope.certificates = res.data || [];
        }).catch(function(err) {
            console.warn('[Volunteer] Failed to load certificates:', err);
        });
        
        // Load name from user data
        var userStr = window.localStorage.getItem('user');
        if (userStr) {
            try {
                var user = JSON.parse(userStr);
                $scope.volunteerName = user.name || 'Volunteer';
            } catch(e) {
                $scope.volunteerName = 'Volunteer';
            }
        }
        
        $scope.volLoading = false;
    };
    
    // Load on init
    $scope.loadVolunteerDashboard();
    
    // ── Helper Functions ───────────────────────────────────────────────────────
    $scope.getVolSectionTitle = function() {
        var titles = {
            'overview': 'Dashboard Overview',
            'active': 'Active Delivery',
            'history': 'Delivery History',
            'achievements': 'Achievements',
            'rewards': 'Rewards',
            'map': 'Map View',
            'profile': 'My Profile'
        };
        return titles[$scope.volActiveSection] || 'Dashboard';
    };
    
    $scope.getProgressPercent = function() {
        if (!$scope.volSummary.target || !$scope.volSummary.completed) return 0;
        return Math.min(100, ($scope.volSummary.completed / $scope.volSummary.target) * 100);
    };
    
    $scope.getRewardProgress = function() {
        if (!$scope.rewardsData.target || !$scope.rewardsData.completed) return 0;
        return Math.min(100, ($scope.rewardsData.completed / $scope.rewardsData.target) * 100);
    };
    
    $scope.isStatusCompleted = function(status) {
        if (!$scope.activeDelivery || !$scope.activeDelivery.delivery) return false;
        var currentStatus = $scope.activeDelivery.delivery.status;
        var order = { 
            'assigned': 0, 
            'picked_up': 1, 
            'in_progress': 2, 
            'completed': 3,
            'pending': 0 
        };
        var currentOrder = order[currentStatus] || 0;
        var statusOrder = order[status] || 0;
        return currentOrder > statusOrder;
    };
    
    $scope.getActiveStatusLabel = function(status) {
        var labels = {
            'assigned': 'Assigned',
            'picked_up': 'Picked Up',
            'in_progress': 'In Transit',
            'completed': 'Completed',
            'pending': 'Pending',
            'ready_for_distribution': 'Ready for Distribution',
            'distributed': 'Distributed',
            'out_for_delivery': 'Out for Delivery',
            'delivered': 'Delivered'
        };
        return labels[status] || status || 'Unknown';
    };
    
    $scope.previewCertificate = function(cert) {
        if (cert.certificate_url) {
            window.open(cert.certificate_url, '_blank');
        }
    };
    
    // Cached filtered deliveries for history (performance optimization)
    $scope.cachedHistoryDeliveries = [];
    $scope.historyCacheTime = 0;
    $scope.historyCacheTTL = 500; // Cache for 500ms
    
    // Set history filter and update cached results
    $scope.setHistoryFilter = function(filter) {
        $scope.historyFilter = filter;
        // Always update immediately when filter changes (no caching for user action)
        $scope.cachedHistoryDeliveries = $scope.filterHistoryDeliveries();
        $scope.historyCacheTime = Date.now();
    };
    
    // Update history filter (called when search changes)
    $scope.updateHistoryFilter = function() {
        var now = Date.now();
        if (now - $scope.historyCacheTime > $scope.historyCacheTTL) {
            $scope.cachedHistoryDeliveries = $scope.filterHistoryDeliveries();
            $scope.historyCacheTime = now;
        }
    };
    
    // Filter deliveries for history with proper status handling
    $scope.filterHistoryDeliveries = function() {
        var filtered = $scope.deliveries || [];
        
        // Filter by status if selected
        if ($scope.historyFilter) {
            filtered = filtered.filter(function(del) {
                return $scope.getDeliveryStatus(del) === $scope.historyFilter;
            });
        }
        
        // Filter by search text
        if ($scope.historySearch) {
            var search = $scope.historySearch.toLowerCase();
            filtered = filtered.filter(function(del) {
                return (del.food_type && del.food_type.toLowerCase().includes(search)) ||
                       (del.ngo_name && del.ngo_name.toLowerCase().includes(search)) ||
                       (del.pickup_location && del.pickup_location.toLowerCase().includes(search));
            });
        }
        
        return filtered;
    };
    
    // Get delivery status from various possible fields
    $scope.getDeliveryStatus = function(del) {
        if (!del) return 'unknown';
        
        // Check donation.delivery_status first (new field)
        if (del.donation && del.donation.delivery_status) {
            var ds = del.donation.delivery_status;
            if (typeof ds === 'string') return ds.toLowerCase();
            if (ds.value) return ds.value.toLowerCase();
            return String(ds).toLowerCase();
        }
        
        // Check delivery_status field
        if (del.delivery_status) {
            var ds = del.delivery_status;
            if (typeof ds === 'string') return ds.toLowerCase();
            if (ds.value) return ds.value.toLowerCase();
            return String(ds).toLowerCase();
        }
        
        // Check donation.status field
        if (del.donation && del.donation.status) {
            var status = del.donation.status;
            if (typeof status === 'string') return status.toLowerCase();
            if (status.value) return status.value.toLowerCase();
            return String(status).toLowerCase();
        }
        
        // Check status field
        if (del.status) {
            var s = del.status;
            if (typeof s === 'string') return s.toLowerCase();
            if (s.value) return s.value.toLowerCase();
            return String(s).toLowerCase();
        }
        
        return 'unknown';
    };
    
    // ── Original State ────────────────────────────────────────────────────────
    $scope.deliveries = [];
    $scope.assignedDeliveries = [];
    $scope.inTransitDeliveries = [];
    $scope.activeTab = 'assigned';
    $scope.loading = false;
    $scope.error = null;
    $scope.volunteerStatus = AuthService.getUserRole() ? "approved" : "pending";

    var userStr = window.localStorage.getItem("user");
    $scope.availability = (userStr && JSON.parse(userStr).availability) || "available";

    // ── Chat Feature ─────────────────────────────────────────────────────────
    $scope.chatPanelOpen = false;
    $scope.chatMessages = [];
    $scope.chatParticipants = [];
    $scope.chatSelectedReceiver = null;
    $scope.selectedReceiverId = null;
    $scope.selectedReceiverName = "";
      $scope.chatError = "";
    $scope.chatMessageText = "";
    $scope.chatLoading = false;
    $scope.chatSending = false;
    $scope.currentDonationId = null;
    $scope.currentUserId = null;
    $scope.emergencySending = false;

    function getCurrentUserId() {
      var userId = localStorage.getItem("fb_user_id");
      if (userId) {
        try { return JSON.parse(userId); } catch(e) { return userId; }
      }
      return null;
    }
    $scope.currentUserId = getCurrentUserId();

    $scope.openChat = function(donation, targetRole) {
      var donationId = donation.id || donation;
      console.log("Opening chat for donation:", donationId, "with role:", targetRole);
      $scope.chatPanelOpen = true;
      $scope.currentDonationId = donationId;
      $scope.chatMessageText = "";
      $scope.chatLoading = true;
      $scope.selectedReceiverName = "";
      $scope.chatError = "";

      var token = AuthService.getToken();
      ChatService.connect(donationId, token);

      ChatService.getParticipants(donation.id).then(function(res) {
        $scope.chatParticipants = res.data.participants || [];
        console.log("Participants:", $scope.chatParticipants);
        
        if (targetRole) {
          var target = $scope.chatParticipants.find(function(p) { 
            return p.role && p.role.toLowerCase() === targetRole.toLowerCase(); 
          });
          if (target) {
            $scope.chatSelectedReceiver = target.user_id;
            $scope.selectedReceiverId = target.user_id;
            $scope.selectedReceiverName = target.name;
            console.log("Selected receiver:", target.user_id, target.name);
          }
        } else if ($scope.chatParticipants.length > 0) {
          var others = $scope.chatParticipants.filter(function(p) {
            return p.user_id !== $scope.currentUserId;
          });
          if (others.length > 0) {
            $scope.chatSelectedReceiver = others[0].user_id;
            $scope.selectedReceiverId = others[0].user_id;
            $scope.selectedReceiverName = others[0].name;
          }
        }
      }).catch(function(err) {
        console.error("Failed to load participants:", err);
      });

      ChatService.getMessages(donation.id).then(function(res) {
        $scope.chatMessages = res.data || [];
        $scope.chatLoading = false;
        scrollChatToBottom();
      }).catch(function(err) {
        console.error("Failed to load messages:", err);
        $scope.chatLoading = false;
      });
    };

    $scope.closeChat = function() {
      $scope.chatPanelOpen = false;
      if ($scope.currentDonationId) {
        ChatService.disconnect();
      }
    };

    $scope.sendChatMessage = function() {
      console.log("sendChatMessage called:", { chatMessageText: $scope.chatMessageText, chatSelectedReceiver: $scope.chatSelectedReceiver, currentDonationId: $scope.currentDonationId });
      if (!$scope.chatMessageText || !$scope.chatSelectedReceiver || !$scope.currentDonationId) {
        return;
      }
      $scope.chatSending = true;

      ChatService.sendMessage($scope.chatSelectedReceiver, $scope.currentDonationId, $scope.chatMessageText)
        .then(function(res) {
          $scope.chatMessageText = "";
          if (res.data && res.data.data) {
            var msgs = res.data.data;
            if (msgs.id) {
              $scope.chatMessages.push(msgs);
            }
          }
          scrollChatToBottom();
        }).catch(function(err) {
          console.error("Send message error:", err);
        }).finally(function() {
          $scope.chatSending = false;
        });
    };

    $scope.chatSendOnEnter = function(event) {
      if (event.key === 'Enter') {
        $scope.sendChatMessage();
      }
    };

    $scope.sendEmergencyAlert = function(donation) {
      if (!confirm("Send emergency alert to NGO? This will notify them immediately.")) {
        return;
      }
      $scope.emergencySending = true;
      ChatService.sendEmergencyAlert(donation.id, "Emergency! Need help immediately!")
        .then(function(res) {
          alert("Emergency alert sent successfully!");
        }).catch(function(err) {
          console.error("Emergency alert error:", err);
          alert("Failed to send emergency alert.");
        }).finally(function() {
          $scope.emergencySending = false;
        });
    };

    $scope.openChatToDonor = function(donation) {
      console.log("Opening chat with donor for donation:", donation.id);
      $scope.chatPanelOpen = true;
      $scope.currentDonationId = donation.id;
      $scope.chatMessageText = "";
      $scope.chatLoading = true;

      var token = AuthService.getToken();
      ChatService.connect(donation.id, token);

      ChatService.getParticipants(donation.id).then(function(res) {
        $scope.chatParticipants = res.data.participants || [];
        var donor = $scope.chatParticipants.find(function(p) { return p.role === 'Donor'; });
        if (donor) {
          $scope.chatSelectedReceiver = donor.user_id;
        }
      }).catch(function(err) {
        console.error("Failed to load participants:", err);
      });

      ChatService.getMessages(donation.id).then(function(res) {
        $scope.chatMessages = res.data || [];
        $scope.chatLoading = false;
        scrollChatToBottom();
      }).catch(function(err) {
        console.error("Failed to load messages:", err);
        $scope.chatLoading = false;
      });
    };

    // Get the correct donation ID from delivery object
    function getDonationId(delivery) {
        // Try donation_id first (new field), then id (delivery ID)
        return delivery.donation_id || delivery.id;
    }
    
    $scope.openChatToNgo = function(delivery) {
        var donationId = getDonationId(delivery);
        console.log("Opening chat with NGO for donation:", donationId);
        $scope.chatPanelOpen = true;
        $scope.currentDonationId = donationId;
        $scope.chatMessageText = "";
        $scope.chatLoading = true;

        var token = AuthService.getToken();
        ChatService.connect(donationId, token);

        ChatService.getParticipants(donationId).then(function(res) {
            $scope.chatParticipants = res.data.participants || [];
            var ngo = $scope.chatParticipants.find(function(p) { return p.role === 'NGO'; });
            if (ngo) {
                $scope.chatSelectedReceiver = ngo.user_id;
                $scope.selectedReceiverName = ngo.name || 'NGO';
            }
        }).catch(function(err) {
            console.error("Failed to load participants:", err);
            $scope.showErrorToast("Failed to load chat participants");
        });

        ChatService.getMessages(donationId).then(function(res) {
            $scope.chatMessages = res.data || [];
            $scope.chatLoading = false;
            scrollChatToBottom();
        }).catch(function(err) {
            console.error("Failed to load messages:", err);
            $scope.chatLoading = false;
            $scope.showErrorToast("Failed to load chat messages");
        });
    };
    
    $scope.openChatToDonor = function(delivery) {
        var donationId = getDonationId(delivery);
        console.log("Opening chat with Donor for donation:", donationId);
        $scope.chatPanelOpen = true;
        $scope.currentDonationId = donationId;
        $scope.chatMessageText = "";
        $scope.chatLoading = true;

        var token = AuthService.getToken();
        ChatService.connect(donationId, token);

        ChatService.getParticipants(donationId).then(function(res) {
            $scope.chatParticipants = res.data.participants || [];
            var donor = $scope.chatParticipants.find(function(p) { return p.role === 'Donor'; });
            if (donor) {
                $scope.chatSelectedReceiver = donor.user_id;
                $scope.selectedReceiverName = donor.name || 'Donor';
            }
        }).catch(function(err) {
            console.error("Failed to load participants:", err);
            $scope.showErrorToast("Failed to load chat participants");
        });

        ChatService.getMessages(donationId).then(function(res) {
            $scope.chatMessages = res.data || [];
            $scope.chatLoading = false;
            scrollChatToBottom();
        }).catch(function(err) {
            console.error("Failed to load messages:", err);
            $scope.chatLoading = false;
            $scope.showErrorToast("Failed to load chat messages");
        });
    };

    $scope.fetchVolunteerParticipantPhones = function(donation) {
      console.log("Fetching participant phones for donation:", donation.id);
      donation.fetchingPhone = true;
      
      ChatService.getParticipants(donation.id).then(function(res) {
        var participants = res.data.participants || [];
        var donor = participants.find(function(p) { return p.role === 'Donor'; });
        var ngo = participants.find(function(p) { return p.role === 'NGO'; });
        
        if (donor) donation.donor_phone = donor.phone;
        if (ngo) donation.ngo_phone = ngo.phone;
        
        console.log("Participant phones - Donor:", donation.donor_phone, "NGO:", donation.ngo_phone);
      }).catch(function(err) {
        console.error("Failed to fetch phones:", err);
      }).finally(function() {
        donation.fetchingPhone = false;
      });
    };

    function scrollChatToBottom() {
      setTimeout(function() {
        var container = document.getElementById("chatMessagesContainer");
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      }, 100);
    }

    $scope.$on("chat:message", function(event, data) {
      if (data.donation_id === $scope.currentDonationId) {
        var exists = $scope.chatMessages.some(function(m) { return m.id === data.id; });
        if (!exists) {
          $scope.chatMessages.push(data);
          scrollChatToBottom();
        }
      }
    });

    $scope.$on("chat:poll-update", function(event, messages) {
      if ($scope.currentDonationId) {
        var filtered = messages.filter(function(m) { return m.donation_id === $scope.currentDonationId; });
        if (filtered.length > 0) {
          $scope.chatMessages = filtered;
        }
      }
    });

    $scope.$on("$destroy", function() {
      ChatService.disconnect();
    });
    
    // Call Donor function
    $scope.callDonor = function(donation) {
        var donationId = donation.donation_id || donation.id;
        
        // First fetch phone numbers
        ChatService.getParticipants(donationId).then(function(res) {
            var participants = res.data.participants || [];
            var donor = participants.find(function(p) { return p.role === 'Donor'; });
            
            if (donor && donor.phone) {
                window.location.href = 'tel:' + donor.phone;
            } else {
                $scope.showErrorToast("Donor phone number not available");
            }
        }).catch(function(err) {
            console.error("Failed to get donor phone:", err);
            $scope.showErrorToast("Could not get donor phone number");
        });
    };
    
    // Call NGO function
    $scope.callNgo = function(donation) {
        var donationId = donation.donation_id || donation.id;
        
        // First fetch phone numbers
        ChatService.getParticipants(donationId).then(function(res) {
            var participants = res.data.participants || [];
            var ngo = participants.find(function(p) { return p.role === 'NGO'; });
            
            if (ngo && ngo.phone) {
                window.location.href = 'tel:' + ngo.phone;
            } else {
                $scope.showErrorToast("NGO phone number not available");
            }
        }).catch(function(err) {
            console.error("Failed to get NGO phone:", err);
            $scope.showErrorToast("Could not get NGO phone number");
        });
    };
    
    function formatOtpCountdown(seconds) {
        var total = Math.max(0, parseInt(seconds || 0, 10));
        var mins = Math.floor(total / 60);
        var secs = total % 60;
        return String(mins).padStart(2, "0") + ":" + String(secs).padStart(2, "0");
    }

    function hydrateOtpFields(delivery) {
        var remaining = parseInt(delivery.otp_seconds_remaining, 10);
        if (isNaN(remaining) || remaining < 0) {
            delivery.otp_countdown_text = "--:--";
            delivery.otp_is_expiring = false;
        } else {
            delivery.otp_countdown_text = formatOtpCountdown(remaining);
            delivery.otp_is_expiring = remaining <= 120;
        }

        var cooldown = parseInt(delivery.otp_resend_available_in_seconds, 10);
        if (isNaN(cooldown) || cooldown < 0) cooldown = 0;
        delivery.otp_resend_available_in_seconds = cooldown;
        delivery.otp_cooldown_text = formatOtpCountdown(cooldown);
        delivery.otp_can_regenerate = cooldown === 0 && !delivery.otp_verified;
    }

    $scope.toggleAvailability = function() {
        var newStatus = $scope.availability === "available" ? "busy" : "available";
        $http.post(API_BASE_URL + "/volunteer/status", { availability: newStatus })
            .then(function(res) {
                $scope.availability = newStatus;
                if (userStr) {
                    var u = JSON.parse(userStr);
                    u.availability = newStatus;
                    window.localStorage.setItem("user", JSON.stringify(u));
                }
            })
            .catch(function(err) {
                console.error("Failed to update status", err);
            });
    };

    // Check volunteer approval status on load
    var storedStatus = window.localStorage.getItem("fb_volunteer_status");
    $scope.volunteerStatus = storedStatus || "approved";
    $scope.isPending = (storedStatus === "pending");
    $scope.isRejected = (storedStatus === "rejected");

    function loadDeliveries() {
      $scope.loading = true;
      VolunteerService.getMyDeliveries()
        .then(function (res) {
          var active = (res.data || []).filter(function(d) {
            return (d.status || '').toLowerCase() !== 'cancelled';
          });
          active.forEach(hydrateOtpFields);
          $scope.assignedDeliveries = active.filter(function(d) { return (d.status || '').toLowerCase() === 'assigned'; });
          $scope.inTransitDeliveries = active.filter(function(d) {
            var s = (d.status || '').toLowerCase();
            return s === 'picked_up' || s === 'in_progress' || s === 'in_transit';
          });
          $scope.deliveries = active;
          console.log("[FoodBridge] Volunteer active deliveries:", active.length);
          
          // Update cached history filter results when deliveries change
          $scope.cachedHistoryDeliveries = $scope.filterHistoryDeliveries();
          $scope.historyCacheTime = Date.now();
        })
        .catch(function (err) {
          console.warn('[FoodBridge] /assigned failed', err);
          $scope.assignedDeliveries = [];
          $scope.inTransitDeliveries = [];
          $scope.deliveries = [];
          $scope.error = (err.data && err.data.detail) ? err.data.detail : "Could not load assigned deliveries.";
        })
        .finally(function () { $scope.loading = false; });
    }
    $scope.manualRefresh = function() { loadDeliveries(); };
    loadDeliveries();
    // Auto-refresh deliveries every 10 seconds
    var deliverySync = $interval(loadDeliveries, 30000);
    var volunteerOtpTick = $interval(function() {
      ($scope.assignedDeliveries || []).forEach(function(del) {
        if (typeof del.otp_seconds_remaining === "number" && del.otp_seconds_remaining > 0) {
          del.otp_seconds_remaining -= 1;
        }
        if (typeof del.otp_resend_available_in_seconds === "number" && del.otp_resend_available_in_seconds > 0) {
          del.otp_resend_available_in_seconds -= 1;
        }
        hydrateOtpFields(del);
      });
    }, 1000);

    $scope.$on('ws_update', function(event, data) {
        if (data && data.type === "NEW_ASSIGNMENT") {
            loadDeliveries();
            if (typeof playNotification === 'function') {
                playNotification();
            }
        }
    });

    function getErrorDetail(err, fallbackMessage) {
      return (err && err.data && err.data.detail) ? err.data.detail : fallbackMessage;
    }

    $scope.generateOtp = function (donation) {
      var donationId = donation.donation_id || donation.id;
      DonationService.generateOtp(donationId)
        .then(function (res) {
            donation.otp_generated = true;
            donation.otp_verified = false;
            donation.otp_error = null;
            donation.otp_input = "";
            if (res && res.data) {
                donation.otp_generated_at = res.data.otp_generated_at;
                donation.otp_expires_at = res.data.otp_expires_at;
                donation.otp_seconds_remaining = res.data.otp_seconds_remaining;
                donation.otp_resend_available_in_seconds = res.data.otp_resend_available_in_seconds;
                donation.otp_regenerate_cooldown_seconds = res.data.otp_regenerate_cooldown_seconds;
            }
            hydrateOtpFields(donation);
            $scope.error = null;
        })
        .catch(function (err) {
            donation.otp_error = getErrorDetail(err, "Failed to generate OTP.");
            $scope.error = donation.otp_error;
            loadDeliveries();
        });
    };

    $scope.verifyOtp = function (donation, otp) {
      if (!otp) {
          donation.otp_error = "Please enter OTP.";
          $scope.error = donation.otp_error;
          return;
      }
      var donationId = donation.donation_id || donation.id;
      VolunteerService.verifyOtp(donationId, otp)
        .then(function () {
          donation.status = 'picked_up';
          donation.otp_verified = true;
          donation.otp_error = null;
          console.log('[Volunteer] OTP verified - status: picked_up, will route to NGO');
          $scope.error = null;
          loadDeliveries();
        })
        .catch(function (err) {
          donation.otp_error = getErrorDetail(err, "OTP verification failed.");
          $scope.error = donation.otp_error;
          loadDeliveries();
        });
    };

    $scope.volunteerReachedLocation = function (donation) {
      var donationId = donation.donation_id || donation.id;
      DonationService.volunteerReachedLocation(donationId)
        .then(function (res) {
          donation.volunteer_reached_donor = true;
          $scope.error = null;
          loadDeliveries();
        })
        .catch(function (err) {
          $scope.error = getErrorDetail(err, "Failed to update location status.");
        });
    };

    $scope.volunteerReceiveDonation = function (donation) {
      var donationId = donation.donation_id || donation.id;
      DonationService.volunteerReceiveDonation(donationId)
        .then(function (res) {
          donation.donation_received = true;
          donation.volunteer_reached_donor = true;
          donation.status = 'in_progress';
          console.log('[Volunteer] Donation received, status changed to in_progress - will route to NGO');
          // Start location updates for NGO tracking
          $scope.updateLocation(donationId);
          // Start live GPS tracking
          LiveTrackingService.startGpsTracking(donationId, 5000);
          // Redraw route to NGO
          $scope.showRoute(donation);
          $scope.error = null;
          loadDeliveries();
        })
        .catch(function (err) {
          $scope.error = getErrorDetail(err, "Failed to receive donation.");
        });
    };

    $scope.updateLocation = function (donationId) {
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(function (pos) {
          // Use tracking endpoint with donation context for live tracking
          VolunteerService.updateLocation(pos.coords.latitude, pos.coords.longitude, donationId)
            .then(function(res) {
              console.log('[Volunteer] Location updated:', pos.coords.latitude, pos.coords.longitude);
            })
            .catch(function(err) {
              console.warn('[Volunteer] Location update failed:', err);
            });
        });
      }
    };

    // Start live GPS tracking when volunteer receives donation
    $scope.startLiveTracking = function(donationId) {
      console.log('[Volunteer] Starting live tracking for donation:', donationId);
      LiveTrackingService.startGpsTracking(donationId, 5000);
    };

    // Stop live GPS tracking
    $scope.stopLiveTracking = function() {
      console.log('[Volunteer] Stopping live tracking');
      LiveTrackingService.stopGpsTracking();
    };

    // Mark as picked up and switch route to NGO
    $scope.markPickedUp = function(donation) {
      var donationId = donation.donation_id || donation.id;
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(function(pos) {
          LiveTrackingService.markPickedUp(donationId, pos.coords.latitude, pos.coords.longitude)
            .then(function(res) {
              console.log('[Volunteer] Marked as picked up:', res.data);
              donation.status = 'picked_up';
              // Route will now show volunteer → NGO
              loadDeliveries();
            })
            .catch(function(err) {
              console.error('[Volunteer] Failed to mark picked up:', err);
              $scope.error = 'Failed to mark as picked up';
            });
        }, function(err) {
          // Try without location
          LiveTrackingService.markPickedUp(donationId, null, null)
            .then(function(res) {
              donation.status = 'picked_up';
              loadDeliveries();
            });
        });
      }
    };

    // Poll location every 10 seconds if there's an active delivery (reduced from 5s to avoid rate limits)
    var locationInterval = setInterval(function() {
      if ($scope.deliveries && $scope.deliveries.length > 0) {
        var activeDelivery = $scope.inTransitDeliveries.length > 0 ? $scope.inTransitDeliveries[0] : 
                             $scope.assignedDeliveries.length > 0 ? $scope.assignedDeliveries[0] : null;
        if (activeDelivery) {
          var dId = activeDelivery.donation_id || activeDelivery.id;
          $scope.updateLocation(dId);
        }
      }
    }, 10000);

    $scope.$on('$destroy', function() {
        if (deliverySync) {
            $interval.cancel(deliverySync);
        }
        if (locationInterval) {
            clearInterval(locationInterval);
        }
        if (volunteerOtpTick) {
            $interval.cancel(volunteerOtpTick);
        }
        if (activeDeliveryRefresh) {
            $interval.cancel(activeDeliveryRefresh);
        }
        // Stop live tracking service
        LiveTrackingService.stopGpsTracking();
    });

    // ── Google Maps Initialization for Volunteer ────────────────────────────
    var map;
    var volunteerMarker;
    var donorMarker;
    var ngoMarker;
    var currentPolyline = null;
    $scope.activeRoute = null;
    $scope.navigationActive = null;
    var navigationRouteManager = null;

    // ── Live Navigation Functions ────────────────────────────────────────
    $scope.startNavigation = function(del) {
        if (!map || !del) return;
        
        console.log('[Volunteer] Starting navigation for:', del.id || del.donation_id);
        $scope.navigationActive = del.id || del.donation_id;
        
        // Start GPS tracking
        var donationId = del.donation_id || del.id;
        LiveTrackingService.startGpsTracking(donationId, 5000);
        
        // Get current location and draw initial route
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(function(pos) {
                var volPos = { lat: pos.coords.latitude, lng: pos.coords.longitude };
                
                // Update or create volunteer marker
                if (volunteerMarker) {
                    MapService.moveMarkerSmoothly(volunteerMarker, volPos);
                } else {
                    volunteerMarker = MapService.createMarker(map, volPos, 'vehicle', 'Your Location');
                }
                
                // Determine destination based on status
                var status = String(del.status || '').toLowerCase();
                var hasDonation = !!del.donation_received;
                var headingToNgo = hasDonation && (status === 'in_progress' || status === 'picked_up');
                
                var destLat = headingToNgo ? parseFloat(del.ngo_latitude) : parseFloat(del.pickup_latitude || del.latitude);
                var destLng = headingToNgo ? parseFloat(del.ngo_longitude) : parseFloat(del.pickup_longitude || del.longitude);
                
                if (!destLat || !destLng) {
                    console.warn('[Volunteer] Destination coordinates missing');
                    return;
                }
                
                var destPos = { lat: destLat, lng: destLng };
                var color = headingToNgo ? '#4CAF50' : '#f44336';
                
                // Clear existing route
                MapService.clearRoute(currentPolyline);
                currentPolyline = null;
                
                // Draw route
                MapService.drawRoute(map, volPos, destPos, [], color, { profile: 'driving' })
                    .then(function(routeRes) {
                        currentPolyline = routeRes.polyline;
                        map.fitBounds(routeRes.bounds, { padding: [50, 50] });
                        $scope.$apply(function() {
                            $scope.activeRoute = { 
                                distance: routeRes.distanceText, 
                                duration: routeRes.durationText 
                            };
                        });
                        console.log('[Volunteer] Navigation route drawn:', routeRes.distanceText, routeRes.durationText);
                    })
                    .catch(function(err) {
                        console.error('[Volunteer] Route drawing failed:', err);
                    });
            }, function(err) {
                console.error('[Volunteer] GPS error:', err);
            }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 });
        }
        
        // Start polling for live location updates
        var pollInterval = $interval(function() {
            if ($scope.navigationActive !== (del.id || del.donation_id)) {
                $interval.cancel(pollInterval);
                return;
            }
            
            LiveTrackingService.getLocation(donationId).then(function(res) {
                if (res.data && res.data.has_location) {
                    var loc = res.data;
                    console.log('[Volunteer] Polled location update:', loc.latitude, loc.longitude);
                    
                    // Update marker position
                    if (volunteerMarker) {
                        MapService.moveMarkerSmoothly(volunteerMarker, { lat: loc.latitude, lng: loc.longitude });
                    }
                    
                    // Redraw route with new position
                    var status = String(res.data.donation_status || '').toLowerCase();
                    var headingToNgo = status === 'in_progress' || status === 'picked_up';
                    
                    var destLat = headingToNgo ? parseFloat(del.ngo_latitude) : parseFloat(del.pickup_latitude || del.latitude);
                    var destLng = headingToNgo ? parseFloat(del.ngo_longitude) : parseFloat(del.pickup_longitude || del.longitude);
                    
                    if (destLat && destLng) {
                        var color = headingToNgo ? '#4CAF50' : '#f44336';
                        
                        MapService.clearRoute(currentPolyline);
                        
                        MapService.drawRoute(map, { lat: loc.latitude, lng: loc.longitude }, { lat: destLat, lng: destLng }, [], color, { profile: 'driving' })
                            .then(function(routeRes) {
                                currentPolyline = routeRes.polyline;
                                $scope.$apply(function() {
                                    $scope.activeRoute = { 
                                        distance: routeRes.distanceText, 
                                        duration: routeRes.durationText 
                                    };
                                });
                            });
                    }
                }
            });
        }, 5000);
    };
    
    $scope.stopNavigation = function() {
        console.log('[Volunteer] Stopping navigation');
        $scope.navigationActive = null;
        LiveTrackingService.stopGpsTracking();
        // Clear route but keep map
        MapService.clearRoute(currentPolyline);
        currentPolyline = null;
    };

    $scope.centerToDevice = function() {
        if (navigator.geolocation && map) {
            navigator.geolocation.getCurrentPosition(function(pos) {
                map.setView([pos.coords.latitude, pos.coords.longitude], 16);
            });
        }
    };

    $scope.$watch('volActiveSection', function(newVal) {
        if (newVal === 'map' || newVal === 'active') {
            setTimeout(function() {
                if (!volunteerMapInitialized) {
                    volunteerMapRetryCount = 0; // restart retries
                    initVolunteerMap();
                } else if (map) {
                    map.invalidateSize();
                }
            }, 300);
        }
    });

    var volunteerMapInitialized = false;
    var volunteerMapRetryCount = 0;
    var MAX_MAP_RETRIES = 10;
    
    function initVolunteerMap() {
      if (volunteerMapInitialized) return;
      
      var mapDiv = document.getElementById("volunteer-interactive-map");
      if (!mapDiv) {
        volunteerMapRetryCount++;
        if (volunteerMapRetryCount > MAX_MAP_RETRIES) {
          console.warn('[Volunteer] Map div not found after ' + MAX_MAP_RETRIES + ' retries, stopping');
          return;
        }
        console.warn('[Volunteer] Map div not found, retrying (' + volunteerMapRetryCount + '/' + MAX_MAP_RETRIES + ')...');
        setTimeout(initVolunteerMap, 1000);
        return;
      }

      volunteerMapInitialized = true;
      var centerPos = { lat: 28.6139, lng: 77.2090 }; // Default: New Delhi
      map = MapService.initMap("volunteer-interactive-map", centerPos, 13);

      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(function (pos) {
          var userPos = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          volunteerMarker = MapService.createMarker(map, userPos, 'vehicle', 'You are here');
          $scope.centerToDevice();
        }, function(err) {
          console.warn('[Volunteer] GPS error:', err);
        });
      }
      
      console.log('[Volunteer] Map initialized');
    }
    setTimeout(initVolunteerMap, 500);

    $scope.showRoute = function(del) {
        console.log('[Volunteer] showRoute called with:', del);
        
        if(!map || !navigator.geolocation) {
            console.warn('[Volunteer] Cannot show route - map or geolocation not available');
            $scope.error = "Map or GPS not available";
            return;
        }

        function asCoord(value) {
            if (value === null || value === undefined || value === '') return null;
            var n = parseFloat(value);
            return isFinite(n) ? n : null;
        }

        var d = del;
        var don = del.donation || {};

        var donorLat = asCoord(d.pickup_latitude) || asCoord(d.latitude) || asCoord(d.donor_latitude) ||
                       asCoord(don.pickup_latitude) || asCoord(don.latitude) || asCoord(don.donor_latitude);
                       
        var donorLng = asCoord(d.pickup_longitude) || asCoord(d.longitude) || asCoord(d.donor_longitude) ||
                       asCoord(don.pickup_longitude) || asCoord(don.longitude) || asCoord(don.donor_longitude);
        
        var ngoLat = asCoord(d.ngo_latitude) || asCoord(d.dropoff_latitude) || asCoord(don.ngo_latitude);
        var ngoLng = asCoord(d.ngo_longitude) || asCoord(d.dropoff_longitude) || asCoord(don.ngo_longitude);
        
        console.log('[Volunteer] Donor coords:', donorLat, donorLng);
        console.log('[Volunteer] NGO coords:', ngoLat, ngoLng);
        
        var status = String(del.status || '').toLowerCase();
        var hasDonation = !!del.donation_received;
        var headingToNgo = hasDonation && (status === 'in_progress' || status === 'in_transit' || status === 'picked_up');

        console.log('[Volunteer] ShowRoute - Status:', status, 'HasDonation:', hasDonation, 'HeadingToNgo:', headingToNgo);

        navigator.geolocation.getCurrentPosition(function(pos) {
            var volPos = { lat: asCoord(pos.coords.latitude), lng: asCoord(pos.coords.longitude) };
            
            if (volPos.lat === null || volPos.lng === null) {
                $scope.$apply(function() {
                    $scope.error = "Unable to get your location. Please enable GPS.";
                });
                return;
            }

            var destination, color, routeProfile, destinationLabel;

            if (headingToNgo) {
                // Going to NGO
                if (ngoLat === null || ngoLng === null) {
                    $scope.$apply(function() {
                        $scope.error = "NGO destination coordinates are missing.";
                        $scope.activeRoute = { distance: '--', duration: 'Route unavailable' };
                    });
                    return;
                }
                destination = { lat: ngoLat, lng: ngoLng };
                color = '#4CAF50';
                routeProfile = 'cycling';
                destinationLabel = 'NGO Destination';
                console.log('[Volunteer] Route to NGO:', destination);
            } else {
                // Going to Donor
                if (donorLat === null || donorLng === null) {
                    $scope.$apply(function() {
                        $scope.error = "Donor pickup coordinates are missing.";
                        $scope.activeRoute = { distance: '--', duration: 'Route unavailable' };
                    });
                    return;
                }
                destination = { lat: donorLat, lng: donorLng };
                color = '#f44336';
                routeProfile = 'driving';
                destinationLabel = 'Pickup Point';
                console.log('[Volunteer] Route to donor:', destination);
            }

            MapService.clearRoute(currentPolyline);
            if(donorMarker) { MapService.removeMarker(map, donorMarker); donorMarker = null; }
            if(ngoMarker) { MapService.removeMarker(map, ngoMarker); ngoMarker = null; }
            if(volunteerMarker) { MapService.removeMarker(map, volunteerMarker); volunteerMarker = null; }

            // Create markers
            volunteerMarker = MapService.createMarker(map, volPos, 'vehicle', 'Your Location');
            
            if (headingToNgo) {
                ngoMarker = MapService.createMarker(map, destination, 'ngo', destinationLabel);
            } else {
                donorMarker = MapService.createMarker(map, destination, 'donor', destinationLabel);
            }

            // Send location to backend for tracking
            var donationId = del.donation_id || del.id;
            if (donationId) {
                VolunteerService.updateLocation(volPos.lat, volPos.lng, donationId).catch(function(err) {
                    console.warn('[Volunteer] Location send failed:', err);
                });
                
                // Start live GPS tracking
                if (!hasDonation) {
                    LiveTrackingService.startGpsTracking(donationId, 10000);
                }
            }

            // Draw route
            MapService.drawRoute(map, volPos, destination, [], color, { profile: routeProfile }).then(function(res) {
                currentPolyline = res.polyline;
                $scope.$apply(function() {
                    $scope.activeRoute = { distance: res.distanceText, duration: res.durationText };
                    $scope.error = null;
                });
                map.fitBounds(res.bounds);
            }).catch(function(err) {
                console.error('[Volunteer] Route draw failed:', err);
                $scope.$apply(function() {
                    $scope.error = "Failed to draw route. Please try again.";
                    $scope.activeRoute = { distance: '--', duration: 'Route unavailable' };
                });
            });
        }, function(err) {
            console.error('[Volunteer] GPS error:', err);
            $scope.$apply(function() {
                $scope.error = "Unable to get your location. Please enable GPS.";
            });
        });
    };

    // Dedicated function for Navigate to NGO - always routes to NGO destination
    $scope.showRouteToNGO = function(del) {
        console.log('[Volunteer] showRouteToNGO called with:', del);
        
        if(!map || !navigator.geolocation) {
            console.warn('[Volunteer] Cannot show route - map or geolocation not available');
            $scope.error = "Map or GPS not available";
            return;
        }

        function asCoord(value) {
            if (value === null || value === undefined || value === '') return null;
            var n = parseFloat(value);
            return isFinite(n) ? n : null;
        }

        var donationData = del.donation || del;
        
        // Route to Beneficiary if distribution, else route to NGO
        var isDist = !!del.is_distribution;
        var destLat = isDist ? asCoord(del.dropoff_latitude) : asCoord(del.ngo_latitude);
        var destLng = isDist ? asCoord(del.dropoff_longitude) : asCoord(del.ngo_longitude);
        
        console.log('[Volunteer] showRouteToNGO Route Info:', {
            isDistribution: isDist,
            beneficiaryName: del.beneficiary_name,
            dropoffLat: del.dropoff_latitude,
            dropoffLng: del.dropoff_longitude,
            ngoLat: del.ngo_latitude,
            destLat: destLat
        });
        
        console.log('[Volunteer] showRouteToNGO Debug:', {
            isDist: isDist,
            del_is_dist: del.is_distribution,
            dropoff_lat: del.dropoff_latitude,
            ngo_lat: del.ngo_latitude,
            destLat: destLat,
            destLng: destLng
        });
        
        if (destLat === null || destLng === null) {
            var msg = "Destination coordinates are missing.";
            if (isDist) msg = "Beneficiary location is not set.";
            else msg = "NGO Hub location is not set.";

            $scope.error = msg;
            $scope.activeRoute = { distance: '--', duration: 'Route unavailable' };
            if (!$scope.$$phase) $scope.$apply();
            return;
        }

        var destination = { lat: destLat, lng: destLng };
        var destinationLabel = isDist ? (del.beneficiary_name || 'Beneficiary Destination') : (del.ngo_name || 'NGO Destination');
        var color = '#4CAF50';
        var routeProfile = 'cycling';

        console.log('[Volunteer] Route to NGO:', destination);

        navigator.geolocation.getCurrentPosition(function(pos) {
            var volPos = { lat: asCoord(pos.coords.latitude), lng: asCoord(pos.coords.longitude) };
            
            if (volPos.lat === null || volPos.lng === null) {
                $scope.$apply(function() {
                    $scope.error = "Unable to get your location. Please enable GPS.";
                });
                return;
            }

            MapService.clearRoute(currentPolyline);
            if(donorMarker) { MapService.removeMarker(map, donorMarker); donorMarker = null; }
            if(ngoMarker) { MapService.removeMarker(map, ngoMarker); ngoMarker = null; }
            if(volunteerMarker) { MapService.removeMarker(map, volunteerMarker); volunteerMarker = null; }

            // Create markers
            volunteerMarker = MapService.createMarker(map, volPos, 'vehicle', 'Your Location');
            ngoMarker = MapService.createMarker(map, destination, 'ngo', destinationLabel);

            // Draw route
            MapService.drawRoute(map, volPos, destination, [], color, { profile: routeProfile }).then(function(res) {
                currentPolyline = res.polyline;
                $scope.$apply(function() {
                    $scope.activeRoute = { distance: res.distanceText, duration: res.durationText };
                    $scope.error = null;
                });
                map.fitBounds(res.bounds);
            }).catch(function(err) {
                console.error('[Volunteer] Route to NGO failed:', err);
                $scope.$apply(function() {
                    $scope.error = "Failed to draw route to NGO.";
                    $scope.activeRoute = { distance: '--', duration: 'Route unavailable' };
                });
            });
        }, function(err) {
            console.error('[Volunteer] GPS error:', err);
            $scope.$apply(function() {
                $scope.error = "Unable to get your location. Please enable GPS.";
            });
        });
    };

    // Show all locations (volunteer, donor, NGO) on map with route
    $scope.showAllLocations = function(del) {
        var L = window.L;
        if(!map || !navigator.geolocation) {
            console.warn('[Volunteer] Cannot show locations - map or geolocation not available');
            return;
        }

        function asCoord(value) {
            var n = parseFloat(value);
            return isFinite(n) ? n : null;
        }

        function resolveNgoDestination() {
            var isDist = !!del.is_distribution;
            var lat = isDist ? asCoord(del.dropoff_latitude) : asCoord(del.ngo_latitude);
            var lng = isDist ? asCoord(del.dropoff_longitude) : asCoord(del.ngo_longitude);
            if (lat === null || lng === null) return null;
            return {
                lat: lat,
                lng: lng,
                label: isDist ? (del.beneficiary_name || 'Beneficiary Destination') : (del.ngo_name || 'NGO Destination'),
                address: isDist ? (del.dropoff_location || '') : (del.ngo_address || '')
            };
        }

        navigator.geolocation.getCurrentPosition(function(pos) {
            var volPos = { lat: asCoord(pos.coords.latitude), lng: asCoord(pos.coords.longitude) };
            var isDist = !!del.is_distribution;
            var donorPos = {
                lat: isDist ? asCoord(del.ngo_latitude) : asCoord(del.pickup_latitude || del.latitude),
                lng: isDist ? asCoord(del.ngo_longitude) : asCoord(del.pickup_longitude || del.longitude)
            };
            var ngoPos = resolveNgoDestination();

            console.log('[Volunteer] showAllLocations - Volunteer:', volPos, 'Donor:', donorPos, 'NGO:', ngoPos);

            // Clear existing markers and routes
            MapService.clearRoute(currentPolyline);
            if(donorMarker) { MapService.removeMarker(map, donorMarker); donorMarker = null; }
            if(ngoMarker) { MapService.removeMarker(map, ngoMarker); ngoMarker = null; }
            if(volunteerMarker) { MapService.removeMarker(map, volunteerMarker); volunteerMarker = null; }

            // Create all markers
            volunteerMarker = MapService.createMarker(map, volPos, 'vehicle', 'Your Location');
            donorMarker = MapService.createMarker(map, donorPos, isDist ? 'ngo' : 'donor', isDist ? 'Pickup Point (NGO)' : 'Pickup Point (Donor)');
            if (ngoPos) {
                ngoMarker = MapService.createMarker(map, ngoPos, isDist ? 'heart' : 'ngo', isDist ? 'Beneficiary Destination' : 'NGO Destination');
            }

            // Fit map to show all markers
            var bounds = L.latLngBounds([
                [volPos.lat, volPos.lng],
                [donorPos.lat, donorPos.lng]
            ]);
            if (ngoPos) {
                bounds.extend([ngoPos.lat, ngoPos.lng]);
            }
            map.fitBounds(bounds, { padding: [50, 50] });

            // Determine which route to show based on donation status
            var status = String(del.status || '').toLowerCase();
            var hasDonation = !!del.donation_received;
            var headingToNgo = hasDonation && (status === 'in_progress' || status === 'in_transit' || status === 'picked_up');

            var destination = headingToNgo && ngoPos ? ngoPos : donorPos;
            var color = headingToNgo ? '#4CAF50' : '#f44336';
            var routeProfile = headingToNgo ? 'cycling' : 'driving';

            if (volPos.lat === null || volPos.lng === null || destination.lat === null || destination.lng === null) {
                $scope.$apply(function() {
                    $scope.error = "Route cannot be generated due to missing coordinates.";
                });
                return;
            }

            // Draw the route
            MapService.drawRoute(map, volPos, destination, [], color, { profile: routeProfile }).then(function(res) {
                currentPolyline = res.polyline;
                $scope.$apply(function() {
                    $scope.activeRoute = { distance: res.distanceText, duration: res.durationText };
                    $scope.error = null;
                });
                map.fitBounds(res.bounds);
            }).catch(function(err) {
                console.error('[Volunteer] Route draw failed:', err);
                $scope.$apply(function() {
                    $scope.activeRoute = { distance: '--', duration: 'Route unavailable' };
                });
            });
        }, function(err) {
            console.error('[Volunteer] GPS error:', err);
            $scope.$apply(function() {
                $scope.error = "Unable to get your location. Please enable GPS.";
            });
        });
    };

    // Override updateLocation to also move the map marker and redraw route
    var originalUpdate = $scope.updateLocation;
    var lastDonationId = null;
    var lastStatus = null;
    $scope.updateLocation = function(donationId) {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(function(pos) {
                var lat = pos.coords.latitude;
                var lng = pos.coords.longitude;
                console.log('[Volunteer] Location update - lat:', lat, 'lng:', lng, 'donationId:', donationId);
                VolunteerService.updateLocation(lat, lng, donationId);
                if(volunteerMarker) {
                    MapService.moveMarkerSmoothly(volunteerMarker, {lat: lat, lng: lng});
                }
                // Redraw route dynamically if we have an active delivery
                if (donationId && map && currentPolyline) {
                    var activeDelivery = $scope.inTransitDeliveries.length > 0 ? $scope.inTransitDeliveries[0] : 
                                         $scope.assignedDeliveries.length > 0 ? $scope.assignedDeliveries[0] : null;
                    if (activeDelivery) {
                        var status = String(activeDelivery.status || '').toLowerCase();
                        var hasDonation = !!activeDelivery.donation_received;
                        var headingToNgo = hasDonation && (status === 'in_progress' || status === 'in_transit' || status === 'picked_up');
                        var isDist = !!activeDelivery.is_distribution;
                        var dest = headingToNgo ? 
                            (isDist ? { lat: parseFloat(activeDelivery.dropoff_latitude), lng: parseFloat(activeDelivery.dropoff_longitude) } : 
                                      { lat: parseFloat(activeDelivery.ngo_latitude), lng: parseFloat(activeDelivery.ngo_longitude) }) :
                            (isDist ? { lat: parseFloat(activeDelivery.ngo_latitude), lng: parseFloat(activeDelivery.ngo_longitude) } : 
                                      { lat: parseFloat(activeDelivery.pickup_latitude || activeDelivery.latitude), lng: parseFloat(activeDelivery.pickup_longitude || activeDelivery.longitude) });
                        if (dest.lat && dest.lng) {
                            MapService.clearRoute(currentPolyline);
                            MapService.drawRoute(map, {lat: lat, lng: lng}, dest, [], headingToNgo ? '#4CAF50' : '#f44336', { profile: headingToNgo ? 'cycling' : 'driving' }).then(function(res) {
                                currentPolyline = res.polyline;
                                console.log('[Volunteer] Route redrawn dynamically');
                            }).catch(function(err) {
                                console.warn('[Volunteer] Route redraw failed:', err);
                            });
                        }
                    }
                }
            }, function(err) {
                console.error('[Volunteer] GPS error in updateLocation:', err);
            }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 });
        }
    };

    $scope.markDelivered = function(donation) {
        if (donation.is_distribution) {
            if (!confirm("Are you sure you want to confirm delivery to beneficiary?")) return;
            $scope.verifyDistributionOtp(donation, "0000"); // Dummy OTP, backend ignores it now
            return;
        }
        
        if (!confirm("Are you sure you want to confirm this delivery? This will complete the delivery process.")) {
            return;
        }
        
        var donationId = donation.donation_id || donation.id;
        
        // First update donation status
        DonationService.updateStatus(donationId, "completed")
            .then(function(res) {
                donation.status = 'completed';
                donation.delivery_status = 'completed';
                if ($scope.deliveries) {
                    $scope.deliveries = $scope.deliveries.filter(function(d) { return (d.donation_id || d.id) !== donationId; });
                }
                
                // Reload dashboard to get updated stats
                if ($scope.loadVolunteerDashboard) {
                    $scope.loadVolunteerDashboard();
                }
                
                // Show success message
                $scope.showToast("Delivery completed successfully!", "success");
                $scope.error = null;
                
                // Reload deliveries to refresh the list
                loadDeliveries();
            })
            .catch(function(err) {
                $scope.error = (err.data && err.data.detail) ? err.data.detail : "Failed to mark as delivered.";
                $scope.showToast("Failed to complete delivery", "error");
            });
    };
    
    $scope.verifyDistributionOtp = function(donation, otp) {
        // Bypass check if otp is '0000' (our internal dummy code)
        if (otp !== "0000" && (!otp || otp.length !== 4)) {
            $scope.showToast("Please enter a valid 4-digit OTP", "error");
            return;
        }
        var donationId = donation.donation_id || donation.id;
        
        VolunteerService.completeDistribution(donationId, otp)
            .then(function(res) {
                donation.status = 'completed';
                donation.delivery_status = 'completed';
                donation.show_otp_input = false;
                
                if ($scope.deliveries) {
                    $scope.deliveries = $scope.deliveries.filter(function(d) { return (d.donation_id || d.id) !== donationId; });
                }
                
                if ($scope.loadVolunteerDashboard) {
                    $scope.loadVolunteerDashboard();
                }
                
                $scope.showToast("Distribution completed successfully!", "success");
                $scope.error = null;
                
                loadDeliveries();
            })
            .catch(function(err) {
                $scope.error = (err.data && err.data.detail) ? err.data.detail : "Failed to verify Beneficiary OTP.";
                $scope.showToast($scope.error, "error");
            });
    };
    
    // Show toast notification
    $scope.showToast = function(message, type) {
        var toast = document.createElement('div');
        toast.className = 'toast-notification toast-' + type;
        toast.style.cssText = 'position:fixed;top:20px;right:20px;z-index:9999;padding:15px 25px;border-radius:8px;background:' + 
            (type === 'success' ? '#28a745' : '#dc3545') + ';color:white;box-shadow:0 4px 12px rgba(0,0,0,0.15);';
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(function() {
            toast.style.opacity = '0';
            setTimeout(function() { document.body.removeChild(toast); }, 300);
        }, 3000);
    };
  }
]);

// ─────────────────────────────────────────────────────────────────────────────
//  AdminController
// ─────────────────────────────────────────────────────────────────────────────
app.controller("AdminController", ["$scope", "AdminService", "AIService", "$interval", "MapService", "$timeout",
  function ($scope, AdminService, AIService, $interval, MapService, $timeout) {

    // Tab state management
    $scope.activeTab = 'overview';
    $scope.tabTitles = {
        overview: 'System Overview',
        users: 'User Management',
        ngos: 'NGO Verification',
        donations: 'Donation Monitoring',
        volunteers: 'Delivery Partner Performance',
        insights: 'AI Insights'
    };
    
    $scope.tabLoading = { overview: false, users: false, ngos: false, donations: false, volunteers: false, insights: false };
    $scope.tabError = {};

    // Data models
    $scope.stats = { 
        totalUsers: "—", ngoCount: "—", donorCount: "—", volunteerCount: "—",
        activeDonations: "—", completedDonations: "—", pendingApprovals: "—"
    };
    $scope.pendingNgos = [];
    $scope.fraudAlerts = [];
    $scope.impactAnalytics = null;
    $scope.aiInsights = [];
    $scope.systemUsers = [];
    $scope.systemDonations = [];
    $scope.activityTimeline = [];
    $scope.volunteerPerformance = [];

    // Toast notification state
    $scope.toast = { visible: false, message: '', type: 'success' };
    var toastTimeoutPromise = null;

    $scope.showToast = function(msg, type) {
        $scope.toast.message = msg;
        $scope.toast.type = type || 'success';
        $scope.toast.visible = true;
        
        if(toastTimeoutPromise) clearTimeout(toastTimeoutPromise);
        toastTimeoutPromise = setTimeout(function() {
            $scope.toast.visible = false;
        }, 4000);
    };

    // Charts instances
    var monthlyChartInst = null;
    var ngoChartInst = null;
    var volChartInst = null;

    // Heatmap setup
    var map;
    var heatmapLayer;

    function initHeatmap(dataPoints, elementId) {
        var elId = elementId || 'hunger-heatmap';
        var mapElement = document.getElementById(elId);
        if (!mapElement) return;

        if (!map) {
            map = MapService.initMap(elId, { lat: 28.6139, lng: 77.2090 }, 11);
        } else if (map && elId === 'insights-heatmap') {
            // Need to invalidate size when tab changes
            setTimeout(function(){ map.invalidateSize(); }, 200);
        }

        var heatPoints = dataPoints.map(function(pt) {
            return [pt.lat, pt.lng, pt.weight || 0.5];
        });

        if (heatmapLayer) {
            try { map.removeLayer(heatmapLayer); } catch(e){}
        }

        if (typeof L !== 'undefined' && typeof L.heatLayer === 'function') {
            heatmapLayer = L.heatLayer(heatPoints, {
                radius: 30, blur: 20, maxZoom: 17, max: 1.0,
                gradient: { 0.3: 'blue', 0.6: 'yellow', 1.0: 'red' }
            }).addTo(map);
        }
    }

    function initMonthlyChart(chartData) {
        if (typeof Chart === 'undefined') return;
        var ctx1 = document.getElementById('monthlyTrendsChart');
        if (ctx1) {
            if (monthlyChartInst) monthlyChartInst.destroy();
            monthlyChartInst = new Chart(ctx1, {
                type: 'line',
                data: {
                    labels: chartData.labels,
                    datasets: [{
                        label: chartData.datasets[0].label,
                        data: chartData.datasets[0].data,
                        borderColor: '#0d6efd', backgroundColor: 'rgba(13, 110, 253, 0.1)',
                        borderWidth: 2, fill: true, tension: 0.4
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }
    }

    function initNgoChart(chartData) {
        if (typeof Chart === 'undefined') return;
        var ctx2 = document.getElementById('ngoPerformanceChart');
        if (ctx2) {
            if (ngoChartInst) ngoChartInst.destroy();
            ngoChartInst = new Chart(ctx2, {
                type: 'bar',
                data: {
                    labels: chartData.labels,
                    datasets: [{
                        label: chartData.datasets[0].label,
                        data: chartData.datasets[0].data,
                        backgroundColor: '#198754', borderRadius: 4
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }
    }

    function initVolunteerChart(chartData) {
        if (typeof Chart === 'undefined') return;
        var ctx3 = document.getElementById('volunteerStatsChart');
        if (ctx3) {
            if (volChartInst) volChartInst.destroy();
            
            var distinctColors = [
                '#0d6efd', '#6610f2', '#6f42c1', '#d63384', '#dc3545',
                '#fd7e14', '#ffc107', '#198754', '#20c997', '#0dcaf0',
                '#6c757d', '#343a40', '#198754', '#0dcaf0', '#d63384'
            ];
            var bgColors = chartData.datasets[0].data.map(function(val, idx) {
                return distinctColors[idx % distinctColors.length];
            });
            
            volChartInst = new Chart(ctx3, {
                type: 'doughnut',
                data: {
                    labels: chartData.labels,
                    datasets: [{
                        data: chartData.datasets[0].data,
                        backgroundColor: bgColors,
                        borderWidth: 1
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }
    }

    // ── Tab Loaders ────────────────────────────────────────────────────────
    
    function loadOverviewData() {
        if ($scope.stats.totalUsers === "—") $scope.tabLoading.overview = true;
        
        AdminService.getStats()
            .then(function(res) {
                $scope.stats = {
                    totalUsers: res.data.total_users,
                    ngoCount: res.data.ngo_count,
                    donorCount: res.data.donor_count,
                    volunteerCount: res.data.volunteer_count,
                    approved_volunteers: res.data.approved_volunteers,
                    pending_volunteers: res.data.pending_volunteers,
                    rejected_volunteers: res.data.rejected_volunteers,
                    activeDonations: res.data.active_donations,
                    completedDonations: res.data.completed_donations,
                    pendingApprovals: res.data.pending_approvals
                };
                $scope.lastUpdated = new Date();
            }).catch(function() { $scope.tabError.overview = 'Failed to load stats'; });

        AdminService.getPendingNgos().then(function(res) { $scope.pendingNgos = res.data; });
        AdminService.getActivityTimeline().then(function(res) { $scope.activityTimeline = res.data; });
        AdminService.getImpactAnalytics().then(function(res) { 
            if (res && res.data) $scope.impactAnalytics = res.data; 
        });
        AIService.getImpactInsights().then(function(res) { 
            if (res && res.data && res.data.insights) $scope.aiInsights = res.data.insights; 
        });

        AdminService.getMonthlyDonations().then(function(res) {
            if (res && res.data && res.data.monthly_donations) {
                setTimeout(function() { initMonthlyChart(res.data.monthly_donations);       }, 100);
            }
        });
        AdminService.getNgoPerformance().then(function(res) {
            if (res && res.data && res.data.ngo_performance) {
                setTimeout(function() { initNgoChart(res.data.ngo_performance);       }, 100);
            }
        });
        AdminService.getVolunteerReliability().then(function(res) {
            if (res && res.data && res.data.volunteer_stats) {
                setTimeout(function() { initVolunteerChart(res.data.volunteer_stats);       }, 100);
            }
        });

        AdminService.getAnalyticsHeatmap().then(function(res) {
            if (res && res.data) {
                setTimeout(function() { initHeatmap(res.data, 'hunger-heatmap');       }, 100);
            }
        }).finally(function() { $scope.tabLoading.overview = false; });
    }

    function loadUsers() {
        $scope.tabLoading.users = true;
        AdminService.getSystemUsers()
            .then(function(res) { $scope.systemUsers = res.data; $scope.tabError.users = null; })
            .catch(function(err) { $scope.tabError.users = 'Failed to load users'; })
            .finally(function() { $scope.tabLoading.users = false; });
    }

    function loadNgos() {
        $scope.tabLoading.ngos = true;
        AdminService.getPendingNgos()
            .then(function(res) { $scope.pendingNgos = res.data; $scope.tabError.ngos = null; })
            .catch(function(err) { $scope.tabError.ngos = 'Failed to load NGOs'; })
            .finally(function() { $scope.tabLoading.ngos = false; });
    }

    function loadDonations() {
        $scope.tabLoading.donations = true;
        AdminService.getSystemDonations()
            .then(function(res) { $scope.systemDonations = res.data; $scope.tabError.donations = null; })
            .catch(function(err) { $scope.tabError.donations = 'Failed to load donations'; })
            .finally(function() { $scope.tabLoading.donations = false; });
    }

    function loadVolunteers() {
        $scope.tabLoading.volunteers = true;
        AdminService.getVolunteerPerformance()
            .then(function(res) { $scope.volunteerPerformance = res.data; $scope.tabError.volunteers = null; })
            .catch(function(err) { $scope.tabError.volunteers = 'Failed to load volunteer performance'; })
            .finally(function() { $scope.tabLoading.volunteers = false; });
    }

    function loadInsights() {
        $scope.tabLoading.insights = true;
        
        var req1 = AdminService.getImpactAnalytics().then(function(res) { $scope.impactAnalytics = res.data; });
        var req2 = AIService.getImpactInsights().then(function(res) { $scope.aiInsights = res.data.insights; });
        var req3 = AdminService.getSuspiciousUsers().then(function(res) { $scope.fraudAlerts = res.data; });
        var req4 = AdminService.getAnalyticsHeatmap().then(function(res) { 
            setTimeout(function() { initHeatmap(res.data, 'insights-heatmap');       }, 100);
        });

        Promise.all([req1, req2, req3, req4]).finally(function() {
            setTimeout(function() { $scope.tabLoading.insights = false; });
        });
    }

    // ── Actions ─────────────────────────────────────────────────────────────

    $scope.setTab = function(tabName) {
        if ($scope.activeTab === tabName) return;
        $scope.activeTab = tabName;
        
        switch(tabName) {
            case 'overview': loadOverviewData(); break;
            case 'users': loadUsers(); break;
            case 'ngos': loadNgos(); break;
            case 'donations': loadDonations(); break;
            case 'volunteers': loadVolunteers(); break;
            case 'insights': loadInsights(); break;
        }
    };

    $scope.manualRefresh = function() {
        $scope.setTab($scope.activeTab); // Reloads active tab
    };

    $scope.approveNgo = function (ngo) {
        ngo._processing = true;
        AdminService.approveNgo(ngo.id)
            .then(function () {
                $scope.showToast("NGO " + (ngo.profile?ngo.profile.name:ngo.email) + " approved successfully.", "success");
                loadNgos();
                // Optionally refresh overview pending badge
                AdminService.getPendingNgos().then(function(res) { $scope.pendingNgos = res.data; });
            })
            .catch(function() {
                $scope.showToast("Failed to approve NGO.", "danger");
                ngo._processing = false;
            });
    };

    $scope.rejectNgo = function (ngo) {
        if (!confirm("Are you sure you want to reject this NGO request? They will be permanently blocked from logging in.")) return;
        
        ngo._processing = true;
        AdminService.rejectNgo(ngo.id)
            .then(function () {
                $scope.showToast("NGO " + (ngo.profile?ngo.profile.name:ngo.email) + " successfully removed.", "success");
                loadNgos();
                AdminService.getPendingNgos().then(function(res) { $scope.pendingNgos = res.data; });
            })
            .catch(function(err) {
                $scope.showToast(err.data && err.data.detail ? err.data.detail : "Failed to reject NGO.", "danger");
                ngo._processing = false;
            });
    };

    $scope.removeUser = function(userId) {
        if (confirm("Are you sure you want to permanently remove this user and ALL their associated data? THIS ACTION CANNOT BE UNDONE.")) {
            AdminService.removeUser(userId)
                .then(function(res){
                    $scope.showToast("User successfully removed.", "success");
                    loadUsers();
                })
                .catch(function(error){
                    var msg = error.data && error.data.detail ? error.data.detail : "Error removing user.";
                    $scope.showToast(msg, "danger");
                });
        }
    };

    // Initial load
    loadOverviewData();

    // ── Real-Time Data Synchronization ──────────────────────────────────────
    // The user requested polling EVERY 15 seconds ONLY when System Overview is active
    var overviewRefreshInterval = null;

    $scope.$watch('activeTab', function(newVal) {
        if (newVal === 'overview') {
            if (!overviewRefreshInterval) {
                overviewRefreshInterval = $interval(function() {
                    loadOverviewData();
                }, 15000); // 15 seconds real-time polling
            }
        } else {
            if (overviewRefreshInterval) {
                $interval.cancel(overviewRefreshInterval);
                overviewRefreshInterval = null;
            }
        }
    });

    $scope.$on('$destroy', function() {
        if (overviewRefreshInterval) $interval.cancel(overviewRefreshInterval);
    });

    // Listen to WebSocket for real time updates
    $scope.$on('ws_update', function() {
        $scope.manualRefresh();
    });

  }
]);


