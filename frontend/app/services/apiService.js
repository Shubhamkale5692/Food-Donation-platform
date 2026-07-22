/**
 * FoodBridge â€“ API Service Layer
 *
 * LOAD ORDER: This file must load BEFORE app.js in index.html because it
 * contains the app.config([$httpProvider]) block that registers the
 * AuthInterceptor. AngularJS config blocks must run during the module
 * configuration phase (before controllers / services are instantiated).
 *
 * URL Strategy:
 *   Docker  â†’ browser hits http://localhost:8080 (Nginx on port 8080)
 *             Nginx proxies /api/* â†’ backend:8000/api/v1/*
 *             API calls MUST use relative path "/api" so Nginx adds /api/v1
 *
 *   Local   â†’ browser hits http://localhost:5500 (or another non-8080 port)
 *             Backend runs separately at http://localhost:8000
 *             API calls use "http://localhost:8000/api/v1" directly
 *
 *   Override â†’ set window.FOODBRIDGE_API_URL before this script loads
 */

var app = angular.module("foodBridgeApp");

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// API base URL constant
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Detect Docker mode vs local-dev mode by checking the port:
//  - Port 8080 or 80 or empty (default) = served through Nginx Docker proxy
//    → use relative "/api" so Nginx routes the call to backend /api/v1/*
//  - Any other port (5500, 3000, etc.)   = local dev server
//    → call the backend directly at http://localhost:8000
// NOTE: Check window.FOODBRIDGE_API_URL first to allow override for any environment
var _port  = window.location.port;           // "8080", "5500", "" …
var _isDockerNginx = (_port === "80" || _port === "");
var apiBaseUrl = (typeof window !== "undefined" && window.FOODBRIDGE_API_URL)
    ? window.FOODBRIDGE_API_URL
    : _isDockerNginx
        ? "/api"                             // Docker / Nginx proxy
        : "http://localhost:8000/api/v1";    // Local dev: direct to FastAPI

// Allow manual override via query parameter for testing
var urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('api')) {
    apiBaseUrl = urlParams.get('api');
}

console.log("API_BASE_URL initialized as:", apiBaseUrl);

app.constant("API_BASE_URL", apiBaseUrl);

// WebSocket URL must always be absolute (ws:// or wss://, never a relative path).
// When in Docker mode, apiBaseUrl is "/api" (relative), so we build the WS URL
// from the page origin so the connection still goes through Nginx.
var wsBaseUrl = _isDockerNginx
    ? (window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host + "/ws"
    : apiBaseUrl.replace("http://", "ws://").replace("https://", "wss://").replace("/api/v1", "/ws");
app.constant("WS_BASE_URL", wsBaseUrl);

// NOTE: VolunteerService is defined AFTER AuthService to avoid circular dependency
// See below after AuthService definition

app.factory("AuthInterceptor", ["$injector", function ($injector) {
  return {
    request: function (config) {
      // Lazy-get AuthService to avoid circular injection during bootstrap
      var AuthService = $injector.get("AuthService");
      var token = AuthService.getToken();
      console.log("[AuthInterceptor] request:", config.url, "token:", token ? "present" : "none");
      
      // Skip auth header for OSRM routing API (CORS issue - OSRM doesn't accept auth headers)
      if (token && config.url && !config.url.includes('router.project-osrm.org') && !config.url.includes('routing.openstreetmap.de')) {
        config.headers = config.headers || {};
        config.headers["Authorization"] = "Bearer " + token;
      }
      return config;
    },
    responseError: function (rejection) {
      // Always log the real error so developers can see it in DevTools
      console.error(
        "[FoodBridge API Error] " + rejection.status + " | URL: " + (rejection.config && rejection.config.url),
        "\nData:", rejection.data,
        "\nHeaders:", rejection.config && rejection.config.headers
      );
      
      // Show toast notification for user-friendly errors (except 401 which redirects to login)
      if (rejection.status !== 401 && rejection.status !== 0) {
        var errorMsg = rejection.data && rejection.data.detail ? rejection.data.detail : "An error occurred";
        
        // Try to show toast via Angular
        var $rootScope;
        try {
          $rootScope = $injector.get("$rootScope");
          $rootScope.$broadcast("show:error-toast", errorMsg);
        } catch(e) {
          // Fallback: show alert for critical errors
          if (rejection.status >= 500) {
            console.warn("Server error - showing user notification");
          }
        }
      }
      
      // 401 â†’ clear stale token and redirect to login page
      if (rejection.status === 401) {
        var auth = $injector.get("AuthService");
        auth.clearSession();
        // Bug 7 Fix: Navigate to login so user isn't stranded on a protected view
        var $window = $injector.get("$window");
        $window.location.href = "#!/login";
      }
      return $injector.get("$q").reject(rejection);
    }
  };
}]);

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Auth Service
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app.service("AuthService", ["$http", "$window", "$q", "API_BASE_URL",
  function ($http, $window, $q, API_BASE_URL) {

    var TOKEN_KEY = "fb_access_token";
    var LEGACY_TOKEN_KEY = "token";
    var USER_KEY  = "fb_user";
    var LEGACY_USER_KEY = "user";
    var LOGIN_KEYS = [TOKEN_KEY, LEGACY_TOKEN_KEY, USER_KEY, LEGACY_USER_KEY, "fb_user_id", "fb_volunteer_status", "fb_ngo_id"];

    this.register = function (userData) {
      return $http.post(API_BASE_URL + "/auth/register", userData)
        .catch(function(error){
            console.log("Full Error:", error);
            var detail = error.data ? error.data.detail : null;
            var msg = "Registration Failed";
            if (detail) {
                if (Array.isArray(detail)) {
                    msg = detail.map(function(d) { return (d.loc && d.loc.length > 0 ? d.loc[d.loc.length - 1] + ": " : "") + d.msg; }).join('\n');
                } else if (typeof detail === 'string') {
                    msg = detail;
                } else {
                    msg = JSON.stringify(detail);
                }
            }
            alert(msg);
            throw error;
        });
    };

this.login = function (email, password) {
      var payload = {
        email: email,
        password: password
      };
      
      var loginUrl = API_BASE_URL + "/login";
      this.clearSession();
      console.log("[FoodBridge Auth] Login request", { email: email, url: loginUrl, apiBaseUrl: API_BASE_URL });

      return $http.post(loginUrl, payload, {
        headers: { "Content-Type": "application/json" }
      }).then(function (res) {
          console.log("[FoodBridge Auth] Login response:", res.status, res.data);
          var data = res.data || {};
          var token = data.access_token;
          
          if (!token) {
            console.log("[FoodBridge Auth] No token - checking if success:", data.success);
            if (data.success === false) {
              throw { data: { message: data.message || "Invalid email or password" } };
            }
            throw { data: { message: "Login failed - no token received" } };
          }

          var user = data.user || {};
          $window.localStorage.setItem(TOKEN_KEY, token);
          $window.localStorage.setItem(LEGACY_TOKEN_KEY, token);

          if (data.role) {
            $window.localStorage.setItem(USER_KEY, data.role);
          }
          if (user.id) {
            $window.localStorage.setItem("fb_user_id", user.id);
          }
          
          return res;
        }).catch(function(error) {
          var status = error.status;
          var data = error.data || {};
          console.log("[FoodBridge Auth] Login failed:", status, data);
          
          var message = data.detail || data.message || "Login failed";
          if (status === 401 || status === 400 || status === 403) {
            throw { data: { message: message } };
          }
          throw { data: { message: "Unable to connect to server. Please try again." } };
        });
    };

    this.logout = function () {
      var token = this.getToken();
      this.clearSession();
      
      // If we have a token, try to call logout endpoint
      if (token) {
        // BUG-9 Fix: pass captured token explicitly - clearSession() already ran,
        // so the interceptor has no token. Send it explicitly in headers.
        return $http.post(API_BASE_URL + "/logout", {}, {
          headers: { "Authorization": "Bearer " + token }
        }).catch(function() {
          // Ignore server logout errors - local session is already cleared
        });
      }
      
      // Return resolved promise when no token exists
      return $q.when({ success: true, message: "Logged out locally" });
    };

    this.clearSession = function () {
      // Only clear FoodBridge-specific keys, not all localStorage
      LOGIN_KEYS.forEach(function(key) {
        $window.localStorage.removeItem(key);
      });
      // Also clear sessionStorage for FoodBridge keys
      var sessionKeys = ["fb_pending_donation", "fb_draft_donation"];
      sessionKeys.forEach(function(key) {
        $window.sessionStorage.removeItem(key);
      });
    };

    this.getToken = function () {
      return $window.localStorage.getItem(TOKEN_KEY) || $window.localStorage.getItem(LEGACY_TOKEN_KEY);
    };

    this.getUserRole = function () {
      var role = $window.localStorage.getItem(USER_KEY);
      if (role) return role;
      try {
        var user = JSON.parse($window.localStorage.getItem(LEGACY_USER_KEY) || "{}");
        return user.role || "";
      } catch (e) {
        return "";
      }
    };

    this.getUserId = function () {
      return $window.localStorage.getItem("fb_user_id");
    };

    this.isLoggedIn = function () {
      return !!this.getToken();
    };
    
    this.getNgos = function () {
      return $http.get(API_BASE_URL + "/auth/ngos");
    };

    this.getDashboardStats = function () {
      return $http.get(API_BASE_URL + "/stats/dashboard-summary");
    };

    // User Profile
    this.getUserProfile = function () {
      console.log("[FoodBridge AuthService] getUserProfile called, fetching:", API_BASE_URL + "/auth/profile");
      return $http.get(API_BASE_URL + "/auth/profile");
    };

    this.updateUserProfile = function (profileData) {
      return $http.put(API_BASE_URL + "/auth/profile", profileData);
    };
  }
]);

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Donation Service
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app.service("DonationService", ["$http", "API_BASE_URL",
  function ($http, API_BASE_URL) {

    this.createDonation = function (donationData) {
      console.log("[FoodBridge] Submitting donation payload:", donationData);
      return $http.post(API_BASE_URL + "/donations/", donationData);
    };

    this.getDonations = function (skip, limit) {
      skip  = skip  || 0;
      limit = limit || 100;
      return $http.get(
        API_BASE_URL + "/donations/?skip=" + skip + "&limit=" + limit
      );
    };

    this.getPendingDonations = function (skip, limit) {
      skip  = skip  || 0;
      limit = limit || 100;
      return $http.get(
        API_BASE_URL + "/donations/pending?skip=" + skip + "&limit=" + limit
      );
    };

    /**
     * Update donation status.
     * Sends { "status": "Accepted" } as a JSON body so FastAPI's
     * DonationStatusUpdate pydantic model can parse it.
     */
    this.updateStatus = function (donationId, newStatus) {
      return $http.put(
        API_BASE_URL + "/donations/" + donationId + "/status",
        { status: newStatus }
      );
    };

    this.claimDonation = function (donationId) {
      var url = API_BASE_URL + "/donations/" + donationId + "/claim";
      console.log("[FoodBridge DonationService] claimDonation called with ID:", donationId, "URL:", url);
      return $http.post(url);
    };

    this.cancelDonation = function (donationId, cancelReason) {
      return $http.post(
        API_BASE_URL + "/donations/cancel/" + donationId,
        { cancel_reason: cancelReason || null }
      );
    };

    this.assignVolunteer = function (donationId, volunteerId) {
      var url = API_BASE_URL + "/donations/" + donationId + "/assign-volunteer";
      if (volunteerId) {
          url += "?volunteer_id=" + volunteerId;
      }
      return $http.post(url);
    };

    this.trackDelivery = function (donationId) {
      return $http.get(API_BASE_URL + "/donations/" + donationId + "/track");
    };

    this.getCertificate = function () {
      return $http.get(API_BASE_URL + "/donations/my-donations/certificate");
    };

    this.generateOtp = function (donationId) {
      return $http.post(API_BASE_URL + "/donations/" + donationId + "/generate-otp");
    };

    this.verifyOtp = function (donationId, otpCode) {
      return $http.post(API_BASE_URL + "/donations/" + donationId + "/verify-otp", { otp: otpCode });
    };

    this.volunteerReachedLocation = function (donationId) {
      return $http.post(API_BASE_URL + "/donations/" + donationId + "/reached-location");
    };

    this.volunteerReceiveDonation = function (donationId) {
      return $http.post(API_BASE_URL + "/donations/" + donationId + "/receive-donation");
    };

    this.completeDonation = function (donationId) {
      return $http.post(API_BASE_URL + "/donations/" + donationId + "/complete");
    };

    this.getDonationLifecycle = function (donationId) {
      return $http.get(API_BASE_URL + "/donations/" + donationId + "/lifecycle");
    };

this.confirmDonationReceived = function (donationId) {
      return $http.post(API_BASE_URL + "/donations/" + donationId + "/confirm-received");
    };

    this.markPickup = function(donationId) {
      return $http.post(API_BASE_URL + "/donations/" + donationId + "/pickup");
    };
    
    this.markDelivered = function(donationId) {
      return $http.post(API_BASE_URL + "/donations/" + donationId + "/mark-delivered");
    };
    
    this.completeDelivery = function(donationId, receiverName, otpVerified) {
      var url = API_BASE_URL + "/donations/" + donationId + "/confirm-delivery-complete";
      return $http.post(url, { 
        receiver_name: receiverName || null, 
        otp_verified: otpVerified || false 
      });
    };
    
    this.assignBeneficiary = function(donationId, beneficiaryId) {
      return $http.post(API_BASE_URL + "/beneficiaries/assign-to-donation?donation_id=" + donationId + "&beneficiary_id=" + beneficiaryId);
    };

    this.ngoCancelDonation = function (donationId, cancelReason) {
      return $http.post(
        API_BASE_URL + "/donations/" + donationId + "/ngo-cancel",
        { cancel_reason: cancelReason || null }
      );
    };
  }
]);



// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Admin Service
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app.service("AdminService", ["$http", "API_BASE_URL",
  function ($http, API_BASE_URL) {
    this.getStats = function () {
      return $http.get(API_BASE_URL + "/admin/stats");
    };
    this.getPendingNgos = function () {
      return $http.get(API_BASE_URL + "/admin/pending-ngos");
    };
    this.approveNgo = function (userId) {
      return $http.post(API_BASE_URL + "/admin/approve-ngo/" + userId);
    };
    this.rejectNgo = function (userId) {
      return $http.post(API_BASE_URL + "/admin/reject-ngo/" + userId);
    };
    this.removeUser = function (userId) {
      return $http.delete(API_BASE_URL + "/admin/users/" + userId);
    };
    this.getSuspiciousUsers = function() {
      return $http.get(API_BASE_URL + "/admin/suspicious-users");
    };
    this.getDemandHeatmap = function() {
      return $http.get(API_BASE_URL + "/admin/demand-heatmap");
    };
    this.getImpactAnalytics = function() {
      return $http.get(API_BASE_URL + "/admin/impact-analytics");
    };
    this.getSystemUsers = function() {
      return $http.get(API_BASE_URL + "/admin/system-users");
    };
    this.getSystemDonations = function() {
      return $http.get(API_BASE_URL + "/admin/system-donations");
    };
    this.getActivityTimeline = function() {
      return $http.get(API_BASE_URL + "/admin/activity-timeline");
    };
    this.getMonthlyDonations = function() {
      return $http.get(API_BASE_URL + "/admin/analytics/monthly-donations");
    };
    this.getVolunteerReliability = function() {
      return $http.get(API_BASE_URL + "/admin/analytics/volunteer-reliability");
    };
    this.getNgoPerformance = function() {
      return $http.get(API_BASE_URL + "/admin/analytics/ngo-performance");
    };
    this.getAnalyticsHeatmap = function() {
      return $http.get(API_BASE_URL + "/admin/analytics/heatmap");
    };
    this.getVolunteerPerformance = function() {
      return $http.get(API_BASE_URL + "/admin/volunteers/performance");
    };
  }
]);

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// NGO Service
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app.service("NgoService", ["$http", "API_BASE_URL",
  function ($http, API_BASE_URL) {
    // â”€â”€ Volunteer approval endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    // NOTE: These live under /volunteer/ router, NOT /ngo/ router
    this.getPendingVolunteers = function () {
      return $http.get(API_BASE_URL + "/volunteer/pending");
    };
    this.approveVolunteer = function (userId) {
      // Correct endpoint: POST /volunteer/approve/{id}
      return $http.post(API_BASE_URL + "/volunteer/approve/" + userId);
    };
    this.rejectVolunteer = function (userId) {
      // Correct endpoint: POST /volunteer/reject/{id}
      return $http.post(API_BASE_URL + "/volunteer/reject/" + userId);
    };

    // â”€â”€ New NGO dashboard endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    /** Overview stat cards */
    this.getNgoStats = function () {
      return $http.get(API_BASE_URL + "/ngo/stats");
    };
    /** All volunteers for this NGO (any status) with delivery counts */
    this.getAllVolunteers = function () {
      return $http.get(API_BASE_URL + "/ngo/volunteers");
    };
    /** Available (approved) volunteers only â€” for manual assign dropdown */
    this.getAvailableVolunteers = function () {
      return $http.get(API_BASE_URL + "/ngo/available-volunteers");
    };
    /** NGO own profile */
    this.getNgoProfile = function () {
      return $http.get(API_BASE_URL + "/ngo/profile");
    };
    /** Update NGO profile fields */
    this.updateNgoProfile = function (data) {
      return $http.put(API_BASE_URL + "/ngo/profile", data);
    };
    /** Monthly analytics data for Chart.js charts */
    this.getNgoAnalytics = function () {
      return $http.get(API_BASE_URL + "/ngo/analytics");
    };
    /** Food inventory (accepted/in-transit donations) */
    this.getNgoInventory = function () {
      return $http.get(API_BASE_URL + "/ngo/inventory");
    };
    /** Delivery tracking endpoint */
    this.getDeliveryTracking = function () {
      return $http.get(API_BASE_URL + "/ngo/delivery-tracking");
    };

    /** Distribution records endpoint */
    this.getDistributionRecords = function () {
      return $http.get(API_BASE_URL + "/ngo/distribution-records");
    };

    // ── Food Testing & Decision System ────────────────────────────────────

    /** Donations received by NGO and awaiting food quality testing */
    this.getReceivedDonations = function () {
      return $http.get(API_BASE_URL + "/ngo/received-donations");
    };

    this.testFood = function (donationId, quality, remarks) {
      return $http.post(
        API_BASE_URL + "/ngo/donations/" + donationId + "/test-food",
        { quality: quality, remarks: remarks || "" }
      );
    };

    /** Donations cleared for distribution (fresh / urgent) */
    this.getDistributionQueue = function () {
      return $http.get(API_BASE_URL + "/ngo/distribution");
    };

    /** Rejected / spoiled donations (waste management) */
    this.getWasteList = function () {
      return $http.get(API_BASE_URL + "/ngo/waste");
    };

    /** AI-powered distribution assignment */
    this.assignDistributionPartner = function (donationId, beneficiaryId) {
      var url = API_BASE_URL + "/ngo/distribution/assign?donation_id=" + donationId;
      if (beneficiaryId) url += "&beneficiary_id=" + beneficiaryId;
      return $http.post(url);
    };

    /** Manual distribution assignment */
    this.assignDistributionPartnerManual = function (donationId, volunteerId, beneficiaryId) {
      var url = API_BASE_URL + "/ngo/distribution/assign-manual?donation_id=" + donationId + "&volunteer_id=" + volunteerId;
      if (beneficiaryId) url += "&beneficiary_id=" + beneficiaryId;
      return $http.post(url);
    };
  }
]);

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Volunteer Service - Updated with Live Tracking
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app.service("VolunteerService", ["$http", "API_BASE_URL", "$injector",
  function ($http, API_BASE_URL, $injector) {
    this.verifyOtp = function (donationId, otp) {
      var DonationService = $injector.get("DonationService");
      return DonationService.verifyOtp(donationId, otp);
    };
    
    // Updated to use new tracking endpoint with optional donation_id
    this.updateLocation = function (lat, lng, donationId) {
      console.log('[VolunteerService] updateLocation called:', lat, lng, donationId);
      var payload = {
        latitude: lat,
        longitude: lng
      };
      if (donationId) {
        payload.donation_id = donationId;
      }
      return $http.post(API_BASE_URL + "/tracking/update-location", payload);
    };
    
    this.getMyDeliveries = function () {
      return $http.get(API_BASE_URL + "/volunteer/my-deliveries");
    };

    this.getMyStatus = function () {
      return $http.get(API_BASE_URL + "/volunteer/me/status");
    };
    
    // New methods for live tracking
    this.markPickedUp = function(donationId, latitude, longitude) {
      console.log('[VolunteerService] markPickedUp called:', donationId);
      return $http.post(API_BASE_URL + "/tracking/mark-picked-up", {
        donation_id: donationId,
        latitude: latitude,
        longitude: longitude
      });
    };
    
    this.getLocation = function(donationId) {
      console.log('[VolunteerService] getLocation called:', donationId);
      return $http.get(API_BASE_URL + "/tracking/track/" + donationId);
    };
    
    // New: Dashboard Summary
    this.getDashboardSummary = function() {
      return $http.get(API_BASE_URL + "/volunteer/dashboard-summary");
    };
    
    // New: Rewards and Points
    this.getRewards = function() {
      return $http.get(API_BASE_URL + "/volunteer/rewards");
    };
    
    // New: Active Delivery
    this.getActiveDelivery = function() {
      return $http.get(API_BASE_URL + "/volunteer/active-delivery");
    };
    
    // New: Update Delivery Status
    this.updateDeliveryStatus = function(deliveryId, status) {
      return $http.post(API_BASE_URL + "/volunteer/update-delivery-status", {
        delivery_id: deliveryId,
        status: status
      });
    };
    
    // New: Complete Distribution with OTP
    this.completeDistribution = function(donationId, otp) {
      return $http.post(API_BASE_URL + "/volunteer/complete-distribution", {
        donation_id: donationId,
        otp: otp
      });
    };
  }
]);

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// AI Service
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app.service("AIService", ["$http", "API_BASE_URL",
  function ($http, API_BASE_URL) {

    /**
     * NEW: 4-Layer AI Image Analysis
     *
     * @param {File}   file        - Raw File object from <input type="file">
     * @param {string} imageSource - "camera" | "upload"
     * @returns Promise with AiImageAnalysisResponse
     */
    this.analyzeImage = function (file, imageSource) {
      var formData = new FormData();
      formData.append("file", file);
      formData.append("image_source", imageSource || "upload");

      return $http.post(API_BASE_URL + "/ai/analyze-image", formData, {
        // Content-Type must be undefined so the browser sets the correct
        // multipart/form-data boundary automatically.
        headers: { "Content-Type": undefined },
        transformRequest: angular.identity
      });
    };

    this.assignVolunteer = function (donationId) {
      return $http.post(API_BASE_URL + "/ai/assign-volunteer", { donation_id: donationId });
    };

    // Legacy: kept for backwards compatibility
    this.checkFoodFreshness = function (imageUrl) {
      return $http.post(API_BASE_URL + "/ai/check-food-freshness", { image_url: imageUrl });
    };

    this.getHungerHeatmap = function () {
      return $http.get(API_BASE_URL + "/ai/hunger-heatmap");
    };

    this.checkFraud = function (userId) {
      return $http.post(API_BASE_URL + "/ai/fraud-check", { user_id: userId });
    };

    this.getRecommendations = function () {
      return $http.get(API_BASE_URL + "/ai/recommendations");
    };

    this.getImpactInsights = function () {
      return $http.get(API_BASE_URL + "/ai/impact-insights");
    };
  }
]);


app.service("NotificationService", ["$http", "API_BASE_URL",
  function ($http, API_BASE_URL) {
    this.getNotifications = function (unreadOnly) {
      var url = API_BASE_URL + "/notifications/";
      if (unreadOnly) {
        url += "?unread_only=true";
      }
      return $http.get(url);
    };

    this.markAsRead = function (notificationId) {
      return $http.post(API_BASE_URL + "/notifications/read/" + notificationId);
    };

    this.markAllAsRead = function () {
      return $http.post(API_BASE_URL + "/notifications/read-all");
    };

    this.getUnreadCount = function () {
      return $http.get(API_BASE_URL + "/notifications/unread-count");
    };
  }
]);

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Chat Service - Real-time messaging
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app.service("ChatService", ["$http", "$q", "API_BASE_URL", "WS_BASE_URL", "$timeout", "$rootScope", "$interval",
  function ($http, $q, API_BASE_URL, WS_BASE_URL, $timeout, $rootScope, $interval) {
    var ws = null;
    var currentDonationId = null;
    var currentToken = null;
    var reconnectAttempts = 0;
    var maxReconnectAttempts = 5;
    var pollInterval = null;
    var typingTimeout = null;
    var typingDebounceTimer = null;
    var isTyping = false;
    var heartbeatInterval = null;
    var lastMessageTime = Date.now();

    var baseReconnectDelay = 1000;
    var maxReconnectDelay = 30000;

    this.connect = function (donationId, token) {
      if (ws && ws.readyState === WebSocket.OPEN && currentDonationId === donationId) {
        return $q.resolve();
      }

      this.disconnect();

      reconnectAttempts = 0;
      currentDonationId = donationId;
      currentToken = token;
      this.stopPolling();
      var wsUrl = WS_BASE_URL.replace("/ws", "/ws/chat/" + donationId + "?token=" + token + "&heartbeat=30");

      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = function () {
          console.log("[ChatService] WebSocket connected for donation:", donationId);
          reconnectAttempts = 0;
          lastMessageTime = Date.now();
          $rootScope.$broadcast("chat:connected", { donationId: donationId });
          this.stopPolling();
          startHeartbeat();
        }.bind(this);

        ws.onmessage = function (event) {
          lastMessageTime = Date.now();
          try {
            var data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
            $rootScope.$applyAsync(function () {
              if (data.type === "typing") {
                $rootScope.$broadcast("chat:typing", data);
              } else if (data.type === "chat_message" || data.type === "connected" || data.type === "heartbeat_ack") {
                $rootScope.$broadcast("chat:message", data);
              } else if (data.type === "pong" || data.type === "heartbeat") {
                console.log("[ChatService] Heartbeat response received");
              } else {
                $rootScope.$broadcast("chat:message", data);
              }
            });
          } catch (e) {
            console.error("[ChatService] Parse error:", e);
          }
        };

        ws.onerror = function (error) {
          console.error("[ChatService] WebSocket error:", error);
        };

        ws.onclose = function (event) {
          console.log("[ChatService] WebSocket disconnected, donation:", donationId, "code:", event.code);
          $rootScope.$broadcast("chat:disconnected", { donationId: donationId });
          stopHeartbeat();

          if (reconnectAttempts < maxReconnectAttempts && currentDonationId && currentToken) {
            reconnectAttempts++;
            var delay = Math.min(baseReconnectDelay * Math.pow(2, reconnectAttempts - 1), maxReconnectDelay);
            console.log("[ChatService] Reconnecting in " + (delay/1000) + "s... attempt:", reconnectAttempts);
            $timeout(function () {
              this.connect(currentDonationId, currentToken);
            }.bind(this), delay);
          } else if (currentDonationId) {
            console.log("[ChatService] Max reconnect attempts reached or no token, falling back to polling");
            this.startPolling(currentDonationId);
          }
        }.bind(this);
      } catch (e) {
        console.error("[ChatService] Connection error:", e);
        this.startPolling(donationId);
      }
    };

    function startHeartbeat() {
      stopHeartbeat();
      heartbeatInterval = $interval(function () {
        if (ws && ws.readyState === WebSocket.OPEN) {
          var timeSinceLastMsg = Date.now() - lastMessageTime;
          if (timeSinceLastMsg > 60000) {
            console.log("[ChatService] No message for 60s, sending heartbeat");
            ws.send(JSON.stringify({ type: "heartbeat" }));
          }
        }
      }, 30000);
    }

    function stopHeartbeat() {
      if (heartbeatInterval) {
        $interval.cancel(heartbeatInterval);
        heartbeatInterval = null;
      }
    };

    this.disconnect = function () {
      stopHeartbeat();
      if (ws) {
        ws.onclose = null;
        ws.close();
        ws = null;
      }
      this.stopPolling();
      this.stopTypingIndicator();
      currentDonationId = null;
      currentToken = null;
      reconnectAttempts = 0;
      lastPollTime = null;
    };

    this.sendMessage = function (receiverId, donationId, message) {
      var deferred = $q.defer();

      this.stopTypingIndicator();

      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: "chat_message",
          receiver_id: receiverId,
          message: message
        }));
        deferred.resolve({ method: "websocket" });
      } else {
        $http.post(API_BASE_URL + "/messages/send", {
          receiver_id: receiverId,
          donation_id: donationId,
          message: message
        }).then(function (res) {
          deferred.resolve({ method: "http", data: res.data });
        }).catch(function (err) {
          deferred.reject(err);
        });
      }

      return deferred.promise;
    };

    this.sendTyping = function (receiverId, donationId) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: "typing",
          receiver_id: receiverId,
          donation_id: donationId
        }));
      }
    };

    this.onTyping = function (receiverId, donationId) {
      if (typingDebounceTimer) {
        $timeout.cancel(typingDebounceTimer);
      }
      
      typingDebounceTimer = $timeout(function() {
        this.sendTyping(receiverId, donationId);
      }.bind(this), 500);
    };

    this.stopTypingIndicator = function () {
      isTyping = false;
      if (typingTimeout) {
        $timeout.cancel(typingTimeout);
        typingTimeout = null;
      }
      if (typingDebounceTimer) {
        $timeout.cancel(typingDebounceTimer);
        typingDebounceTimer = null;
      }
    };

    this.getMessages = function (donationId) {
      return $http.get(API_BASE_URL + "/messages/" + donationId);
    };

    this.getParticipants = function (donationId) {
      console.log("[ChatService] getParticipants called for donation:", donationId);
      return $http.get(API_BASE_URL + "/messages/" + donationId + "/participants")
        .then(function(res) {
          console.log("[ChatService] getParticipants response:", res.data);
          return res;
        })
        .catch(function(err) {
          console.error("[ChatService] getParticipants error:", err);
          return $q.reject(err);
        });
    };

    this.markAsRead = function (donationId) {
      return $http.post(API_BASE_URL + "/messages/read", {
        donation_id: donationId
      });
    };

    this.markAsSeen = function (donationId, messageIds) {
      return $http.post(API_BASE_URL + "/messages/mark-seen", {
        donation_id: donationId,
        message_ids: messageIds || null
      });
    };

    this.sendEmergencyAlert = function (donationId, message) {
      return $http.post(API_BASE_URL + "/messages/emergency-alert", {
        donation_id: donationId,
        message: message || "Emergency! Need help immediately!"
      });
    };

    var lastPollTime = null;

    this.startPolling = function (donationId) {
      this.stopPolling();
      console.log("[ChatService] Starting polling for donation:", donationId);
      lastPollTime = null;

      pollInterval = $interval(function () {
        if (currentDonationId) {
          var url = API_BASE_URL + "/messages/" + currentDonationId + "/poll";
          if (lastPollTime) {
            url += "?since=" + encodeURIComponent(lastPollTime);
          }
          $http.get(url).then(function (res) {
            if (res.data && res.data.polled_at) {
              lastPollTime = res.data.polled_at;
            }
            if (res.data && res.data.messages && res.data.messages.length > 0) {
              $rootScope.$applyAsync(function () {
                $rootScope.$broadcast("chat:poll-update", res.data.messages);
              });
            }
          }).catch(function (err) {
            console.log("[ChatService] Poll failed, falling back to regular messages");
            this.getMessages(currentDonationId).then(function (res) {
              $rootScope.$applyAsync(function () {
                $rootScope.$broadcast("chat:poll-update", res.data);
              });
            });
          }.bind(this));
        }
      }.bind(this), 5000);
    };

    this.stopPolling = function () {
      if (pollInterval) {
        $interval.cancel(pollInterval);
        pollInterval = null;
      }
      lastPollTime = null;
    };

    this.isConnected = function () {
      return ws && ws.readyState === WebSocket.OPEN;
    };

    this.getConnectionStatus = function (donationId) {
      return $http.get(API_BASE_URL + "/messages/" + donationId + "/status");
    };
  }
]);

// Filter to convert UTC datetime to local user's timezone
app.filter('utcToLocal', ['$filter', function($filter) {
  return function(utcDateString, format) {
    if (!utcDateString) return '';
    
    // Handle both string dates and Date objects
    var date = utcDateString instanceof Date ? utcDateString : new Date(utcDateString);
    if (isNaN(date.getTime())) return '';
    
    // Create a date in local timezone
    var localDate = new Date(date.toLocaleString());
    var dateFilter = $filter('date');
    return dateFilter(localDate, format || 'medium');
  };
}]);

// Shorter time filter for chat - shows time in local timezone
app.filter('localTime', ['$filter', function($filter) {
  return function(utcDateString) {
    if (!utcDateString) return '';
    
    var date = utcDateString instanceof Date ? utcDateString : new Date(utcDateString);
    if (isNaN(date.getTime())) return '';
    
    var localDate = new Date(date.toLocaleString());
    var dateFilter = $filter('date');
    return dateFilter(localDate, 'h:mm a');
  };
}]);


// Formats duration into human-readable format for timeline
app.filter('lifecycleDuration', [function() {
  return function(durationStr) {
    if (!durationStr || durationStr === 'In Progress') return 'Pending...';
    return durationStr;
  };
}]);

// ─────────────────────────────────────────────────────────────────────────────
// Beneficiary Service - For managing beneficiaries/recipients
// ─────────────────────────────────────────────────────────────────────────────
app.service("BeneficiaryService", ["$http", "API_BASE_URL",
  function ($http, API_BASE_URL) {
    
    this.getBeneficiaries = function(skip, limit, typeFilter) {
      var url = API_BASE_URL + "/beneficiaries/?limit=100";
      if (skip) url += "&skip=" + skip;
      if (limit) url += "&limit=" + limit;
      if (typeFilter) url += "&type_filter=" + typeFilter;
      return $http.get(url);
    };
    
    this.getBeneficiary = function(beneficiaryId) {
      return $http.get(API_BASE_URL + "/beneficiaries/" + beneficiaryId + "/");
    };
    
    this.createBeneficiary = function(beneficiaryData) {
      return $http.post(API_BASE_URL + "/beneficiaries", beneficiaryData);
    };
    
    this.updateBeneficiary = function(beneficiaryId, updateData) {
      return $http.put(API_BASE_URL + "/beneficiaries/" + beneficiaryId, updateData);
    };
    
    this.deleteBeneficiary = function(beneficiaryId) {
      return $http.delete(API_BASE_URL + "/beneficiaries/" + beneficiaryId);
    };
    
    this.assignToDonation = function(donationId, beneficiaryId) {
      return $http.post(API_BASE_URL + "/beneficiaries/assign-to-donation?donation_id=" + donationId + "&beneficiary_id=" + beneficiaryId);
    };
    
    this.getNearbyBeneficiaries = function(latitude, longitude, radiusKm) {
      var url = API_BASE_URL + "/beneficiaries/nearby/list?latitude=" + latitude + "&longitude=" + longitude;
      if (radiusKm) url += "&radius_km=" + radiusKm;
      return $http.get(url);
    };
  }
]);
