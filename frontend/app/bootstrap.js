/**
 * FoodBridge bootstrap controllers and routing.
 * This file restores app-level routing/controllers and provides the canonical
 * DonorController implementation.
 */
var app = angular.module("foodBridgeApp");

(function () {
  function normalizeRole(roleValue) {
    return String(roleValue || "").trim().toLowerCase();
  }

  function dashboardPathForRole(roleValue) {
    var role = normalizeRole(roleValue);
    if (role === "admin") return "/admin-dashboard";
    if (role === "ngo") return "/ngo-dashboard";
    if (role === "volunteer") return "/volunteer-dashboard";
    if (role === "donor") return "/donor-dashboard";
    return "/";
  }

  function parseErrorMessage(err, fallback) {
    fallback = fallback || "Something went wrong.";
    if (!err) return fallback;
    if (err.data) {
      if (typeof err.data.message === "string" && err.data.message.trim()) {
        return err.data.message;
      }
      if (typeof err.data.detail === "string" && err.data.detail.trim()) {
        return err.data.detail;
      }
      if (Array.isArray(err.data.detail) && err.data.detail.length > 0) {
        return err.data.detail
          .map(function (item) {
            if (item && item.msg) return item.msg;
            return String(item);
          })
          .join(", ");
      }
    }
    return fallback;
  }

  app.config([
    "$routeProvider",
    function ($routeProvider) {
      $routeProvider
        .when("/", {
          templateUrl: "app/components/home/home.html",
        })
        .when("/login", {
          templateUrl: "app/components/home/home.html",
        })
        .when("/donor-dashboard", {
          templateUrl: "app/components/donor/donor.html",
        })
        .when("/ngo-dashboard", {
          templateUrl: "app/components/ngo/ngo.html",
          controller: "NgoController",
        })
        .when("/volunteer-dashboard", {
          templateUrl: "app/components/volunteer/volunteer.html",
          controller: "VolunteerController",
        })
        .when("/admin-dashboard", {
          templateUrl: "app/components/admin/admin.html",
          controller: "AdminController",
        })
        .when("/ngo/signup", {
          templateUrl: "app/components/ngo/ngo-signup.html",
          controller: "NgoSignupController",
        })
        .when("/ngo/profile-setup", {
          templateUrl: "app/components/ngo/ngo-profile.html",
          controller: "NgoProfileSetupController",
        })
        .when("/impact-report", {
          templateUrl: "app/components/home/impact-report.html",
          controller: "ImpactReportController",
        })
        .when("/safety-guidelines", {
          templateUrl: "app/components/home/safety-guidelines.html",
          controller: "SafetyGuidelinesController",
        })
        .when("/terms", {
          templateUrl: "app/components/home/terms.html",
          controller: "TermsController",
        })
        .when("/privacy", {
          templateUrl: "app/components/home/privacy.html",
          controller: "PrivacyController",
        })
        .when("/our-story", {
          templateUrl: "app/components/home/our-story.html",
          controller: "OurStoryController",
        })
        .when("/ngo-directory", {
          templateUrl: "app/components/home/ngo-directory.html",
          controller: "NgoDirectoryController",
        })
        .when("/help-center", {
          templateUrl: "app/components/home/help-center.html",
          controller: "HelpCenterController",
        })
        .when("/achievements", {
          templateUrl: "app/components/achievements/achievements.html",
          controller: "AchievementsController",
        })
        .otherwise({
          redirectTo: "/",
        });
    },
  ]);

  app.run([
    "$rootScope",
    "$location",
    "AuthService",
    function ($rootScope, $location, AuthService) {
      var roleRequiredByPath = {
        "/donor-dashboard": "donor",
        "/ngo-dashboard": "ngo",
        "/volunteer-dashboard": "volunteer",
        "/admin-dashboard": "admin",
        "/ngo/profile-setup": "ngo",
      };

      $rootScope.$on("$routeChangeStart", function (evt, next) {
        var targetPath = next && next.$$route ? next.$$route.originalPath : "";
        if (!targetPath || !roleRequiredByPath[targetPath]) return;

        // Toggle body class for NGO dashboard to remove top padding
        if (targetPath === "/ngo-dashboard") {
          document.body.classList.add("ngo-fullscreen");
        } else {
          document.body.classList.remove("ngo-fullscreen");
        }

        if (!AuthService.isLoggedIn()) {
          evt.preventDefault();
          $location.path("/");
          $rootScope.authMode = "login";
          return;
        }

        var expectedRole = roleRequiredByPath[targetPath];
        var actualRole = normalizeRole(AuthService.getUserRole());
        if (expectedRole !== actualRole) {
          evt.preventDefault();
          $location.path(dashboardPathForRole(actualRole));
        }
      });
    },
  ]);

  app.controller("RootController", [
    "$scope",
    "$rootScope",
    "$location",
    "$interval",
    "AuthService",
    "NotificationService",
    "DonationService",
    function ($scope, $rootScope, $location, $interval, AuthService, NotificationService, DonationService) {
      $scope.isLoggedIn = false;
      // ... existing RootController code ...
      $scope.userRole = "";
      $scope.currentUserEmail = "";
      $scope.currentPath = $location.path();
      $scope.logoutInProgress = false;
      $scope.showNotifications = false;
      $scope.notifications = [];
      $scope.notificationCount = 0;
      $scope.authMode = "login";

      // ── Lifecycle Tracking Helpers ─────────────────────────────────────
$rootScope.getTimelineSteps = function(donation) {
           if (!donation) return [];
           
           var cacheKey = donation.id + '|' + (donation.lifecycle_status || donation.status || 'CREATED');
           if (donation._timelineCacheKey === cacheKey && donation._timelineSteps) {
               return donation._timelineSteps;
           }
           
           var status = (donation.lifecycle_status || donation.status || 'CREATED').toUpperCase();
           var ts = donation.lifecycle_timestamps || {};
           
           var steps = [
               { key: 'CREATED', label: 'Posted', icon: 'bi-box-seam', time: ts.donation_posted_at },
               { key: 'ACCEPTED', label: 'Accepted', icon: 'bi-check2-circle', time: ts.pickup_accepted_at },
               { key: 'PICKED_UP', label: 'Picked Up', icon: 'bi-truck', time: ts.picked_up_at },
               { key: 'DELIVERED', label: 'Delivered', icon: 'bi-house-heart', time: ts.delivered_at },
               { key: 'RECEIVED', label: 'Received', icon: 'bi-bag-check-fill', time: ts.received_at }
           ];

           donation._timelineSteps = steps.map(function(s) {
               return {
                   key: s.key,
                   label: s.label,
                   icon: s.icon,
                   time: s.time ? String(s.time) : null,
                   isCompleted: !!s.time,
                   isActive: (s.key === status)
               };
           });
           donation._timelineCacheKey = cacheKey;
           return donation._timelineSteps;
       };

      $rootScope.loadLifecycle = function(donation) {
          if (!donation || !donation.id) return;
          donation._loadingLifecycle = true;
          DonationService.getDonationLifecycle(donation.id)
              .then(function(res) {
                  var data = res.data;
                  angular.extend(donation, data);
                  donation.timelineSteps = $rootScope.getTimelineSteps(donation);
              })
              .finally(function() {
                  donation._loadingLifecycle = false;
              });
      };

      var notificationInterval = null;

      function refreshAuthState() {
        $scope.isLoggedIn = AuthService.isLoggedIn();
        $scope.userRole = normalizeRole(AuthService.getUserRole());

        var userEmail = "";
        try {
          var raw = localStorage.getItem("user");
          if (raw) {
            var parsed = JSON.parse(raw);
            if (parsed && parsed.email) userEmail = parsed.email;
          }
        } catch (e) {
          userEmail = "";
        }
        $scope.currentUserEmail = userEmail;

        if ($scope.isLoggedIn) {
          startNotificationPolling();
        } else {
          stopNotificationPolling();
          $scope.notifications = [];
          $scope.notificationCount = 0;
        }
      }

      function loadNotifications() {
        if (!$scope.isLoggedIn) return;
        NotificationService.getNotifications(true)
          .then(function (res) {
            var list = Array.isArray(res.data) ? res.data : [];
            $scope.notifications = list;
            $scope.notificationCount = list.length;
          })
          .catch(function () {
            $scope.notifications = [];
            $scope.notificationCount = 0;
          });
      }

      function startNotificationPolling() {
        if (notificationInterval) return;
        loadNotifications();
        notificationInterval = $interval(loadNotifications, 15000);
      }

      function stopNotificationPolling() {
        if (notificationInterval) {
          $interval.cancel(notificationInterval);
          notificationInterval = null;
        }
      }

      $scope.openHowItWorks = function () {
        var modalEl = document.getElementById("howItWorksModal");
        if (modalEl && typeof bootstrap !== "undefined") {
          var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
          modal.show();
        }
      };

      $scope.openPartnershipModal = function () {
        var modalEl = document.getElementById("partnershipModal");
        if (modalEl && typeof bootstrap !== "undefined") {
          var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
          modal.show();
        }
      };

      $scope.handleCtaPrimary = function () {
        if ($scope.isLoggedIn) {
          $location.path(dashboardPathForRole($scope.userRole));
          return;
        }
        $scope.authMode = "register";
        var modalEl = document.getElementById("authModal");
        if (modalEl && typeof bootstrap !== "undefined") {
          var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
          modal.show();
        }
      };

      $scope.logout = function () {
        if ($scope.logoutInProgress) return;
        $scope.logoutInProgress = true;
        AuthService.logout()
          .finally(function () {
            $scope.logoutInProgress = false;
            $scope.showNotifications = false;
            $rootScope.$emit("fb:authChanged");
            $location.path("/");
          });
      };

      $scope.$on("$routeChangeSuccess", function () {
        $scope.currentPath = $location.path();
      });

      $scope.$on("fb:authChanged", function () {
        refreshAuthState();
      });

      $scope.$on("$destroy", function () {
        stopNotificationPolling();
      });

      refreshAuthState();
    },
  ]);

  app.controller("AuthController", [
    "$scope",
    "$rootScope",
    "$location",
    "$timeout",
    "AuthService",
    function ($scope, $rootScope, $location, $timeout, AuthService) {
      $scope.authMode = $rootScope.authMode || "login";
      $scope.authLoading = false;
      $scope.authError = null;
      $scope.authSuccess = null;

      $scope.user = {
        name: "",
        email: "",
        password: "",
        role: "",
        ngo_id: "",
      };
      $scope.loginData = {
        email: "",
        password: "",
      };
      $scope.ngos = [];

      function syncAuthModeFromRoot() {
        $scope.authMode = $rootScope.authMode || $scope.authMode || "login";
      }

      function loadNgos() {
        AuthService.getNgos()
          .then(function (res) {
            $scope.ngos = Array.isArray(res.data) ? res.data : [];
          })
          .catch(function () {
            $scope.ngos = [];
          });
      }

      function closeAuthModal() {
        var el = document.getElementById("authModal");
        if (el && typeof bootstrap !== "undefined") {
          var modal = bootstrap.Modal.getOrCreateInstance(el);
          modal.hide();
        }
      }

      $scope.login = function () {
        $scope.authError = null;
        $scope.authSuccess = null;
        $scope.authLoading = true;

        var email = ($scope.user.email || "").trim();
        var password = $scope.user.password || "";
        if (!email || !password) {
          $scope.authLoading = false;
          $scope.authError = "Please enter email and password.";
          return;
        }

        AuthService.login(email, password)
          .then(function (res) {
            var role = normalizeRole((res.data && res.data.role) || AuthService.getUserRole());
            $scope.authSuccess = "Login successful.";
            $rootScope.$emit("fb:authChanged");
            closeAuthModal();
            $location.path(dashboardPathForRole(role));
          })
          .catch(function (err) {
            $scope.authError = parseErrorMessage(err, "Invalid email or password.");
          })
          .finally(function () {
            $scope.authLoading = false;
          });
      };

      $scope.signup = function () {
        $scope.authError = null;
        $scope.authSuccess = null;
        $scope.authLoading = true;

        var payload = {
          name: ($scope.user.name || "").trim(),
          email: ($scope.user.email || "").trim(),
          password: $scope.user.password || "",
          role: $scope.user.role || "",
          ngo_id: $scope.user.ngo_id || null,
        };

        if (!payload.name || !payload.email || !payload.password || !payload.role) {
          $scope.authLoading = false;
          $scope.authError = "Please fill all required fields.";
          return;
        }

        if (payload.role !== "Volunteer") {
          payload.ngo_id = null;
        } else if (!payload.ngo_id) {
          $scope.authLoading = false;
          $scope.authError = "Please select an NGO for volunteer registration.";
          return;
        }

        AuthService.register(payload)
          .then(function () {
            $scope.authSuccess = "Registration successful. Please log in.";
            $scope.authMode = "login";
            $rootScope.authMode = "login";
            $scope.user.password = "";
            $scope.user.ngo_id = "";
          })
          .catch(function (err) {
            $scope.authError = parseErrorMessage(err, "Registration failed. Please try again.");
          })
          .finally(function () {
            $scope.authLoading = false;
          });
      };

      $scope.$watch(function () {
        return $rootScope.authMode;
      }, function () {
        syncAuthModeFromRoot();
      });

      loadNgos();
      syncAuthModeFromRoot();
      $timeout(function () {
        if ($scope.authMode === "register") loadNgos();
      }, 0);
    },
  ]);

  app.controller("HomeController", [
    "$scope",
    "$interval",
    "AuthService",
    function ($scope, $interval, AuthService) {
      $scope.animatedStats = {
        mealsDelivered: 0,
        activeDonors: 0,
        partnerNGOs: 0,
        volunteers: 0,
      };

      function animateStat(key, target) {
        var current = Number($scope.animatedStats[key] || 0);
        target = Number(target || 0);
        if (target <= current) {
          $scope.animatedStats[key] = target;
          return;
        }

        var steps = 25;
        var step = Math.max(1, Math.round((target - current) / steps));
        var ticks = 0;
        var timer = $interval(function () {
          ticks += 1;
          current += step;
          if (current >= target || ticks >= steps) {
            $scope.animatedStats[key] = target;
            $interval.cancel(timer);
            return;
          }
          $scope.animatedStats[key] = current;
        }, 24);
      }

      function loadDashboardSummary() {
        AuthService.getDashboardStats()
          .then(function (res) {
            var data = res && res.data && res.data.data ? res.data.data : {};
            animateStat("mealsDelivered", data.mealsDelivered || 0);
            animateStat("activeDonors", data.activeDonors || 0);
            animateStat("partnerNGOs", data.partnerNGOs || 0);
            animateStat("volunteers", data.volunteers || 0);
          })
          .catch(function () {
            // Keep defaults if public stats are unavailable.
          });
      }

      loadDashboardSummary();
    },
  ]);

  app.controller("HowItWorksController", [
    "$scope",
    function ($scope) {
      $scope.currentStep = 0;
      $scope.steps = [
        {
          title: "Donor Lists Surplus",
          description: "Donors post food details, quantity, and pickup location in under a minute.",
          icon: "bi-box-seam",
          details: [
            "Add food type and quantity",
            "Set expiry and pickup location",
            "AI checks freshness cues",
          ],
        },
        {
          title: "NGO Accepts Donation",
          description: "Nearby NGOs are notified and can instantly claim matching donations.",
          icon: "bi-building",
          details: [
            "Live pending donations feed",
            "Smart prioritization support",
            "Volunteer assignment controls",
          ],
        },
        {
          title: "Volunteer Delivers",
          description: "Assigned volunteers complete pickup and delivery with OTP verification.",
          icon: "bi-bicycle",
          details: [
            "Secure OTP handoff",
            "Route and status tracking",
            "Delivery completion proof",
          ],
        },
        {
          title: "Impact Tracked",
          description: "The platform records meals served and community impact in real time.",
          icon: "bi-graph-up-arrow",
          details: [
            "Donation and delivery analytics",
            "Impact dashboards and trends",
            "Transparent activity timeline",
          ],
        },
      ];

      $scope.prevStep = function () {
        if ($scope.currentStep > 0) $scope.currentStep -= 1;
      };

      $scope.nextStep = function () {
        if ($scope.currentStep < $scope.steps.length - 1) $scope.currentStep += 1;
      };

      $scope.closeModal = function () {
        var modalEl = document.getElementById("howItWorksModal");
        if (modalEl && typeof bootstrap !== "undefined") {
          bootstrap.Modal.getOrCreateInstance(modalEl).hide();
        }
      };
    },
  ]);

  app.controller("PartnershipController", [
    "$scope",
    "$timeout",
    function ($scope, $timeout) {
      $scope.formData = { name: "", organization: "", email: "", message: "" };
      $scope.submitting = false;
      $scope.formSubmitted = false;

      $scope.submitPartnershipForm = function () {
        if ($scope.submitting) return;
        $scope.submitting = true;
        $timeout(function () {
          $scope.submitting = false;
          $scope.formSubmitted = true;
        }, 900);
      };
    },
  ]);

  app.controller("ImpactReportController", [
    "$scope",
    "$timeout",
    "AuthService",
    function ($scope, $timeout, AuthService) {
      $scope.loading = true;
      $scope.currentDate = new Date();
      $scope.trendFilter = "monthly";
      $scope.maxDeliveries = 100;
      $scope.overviewStats = {
        totalDonations: 0,
        mealsServed: 0,
        ngosConnected: 0,
        deliveriesCompleted: 0,
      };
      $scope.topNgos = [];
      $scope.volunteerStats = { totalDeliveries: 0, reliabilityScore: 0 };
      $scope.recentActivity = [];

      var trendChart = null;

      function renderTrendChart() {
        if (typeof Chart === "undefined") return;
        var canvas = document.getElementById("donationTrendChart");
        if (!canvas) return;
        if (trendChart) {
          trendChart.destroy();
          trendChart = null;
        }

        var labels;
        var data;
        if ($scope.trendFilter === "today") {
          labels = ["6AM", "9AM", "12PM", "3PM", "6PM", "9PM"];
          data = [2, 4, 6, 8, 5, 3];
        } else if ($scope.trendFilter === "weekly") {
          labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
          data = [8, 10, 7, 12, 11, 9, 13];
        } else {
          labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"];
          data = [32, 41, 38, 55, 49, 62];
        }

        trendChart = new Chart(canvas, {
          type: "line",
          data: {
            labels: labels,
            datasets: [{
              label: "Donations",
              data: data,
              borderColor: "#198754",
              backgroundColor: "rgba(25,135,84,0.15)",
              borderWidth: 3,
              fill: true,
              tension: 0.35,
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
          },
        });
      }

      $scope.setTrendFilter = function (filter) {
        $scope.trendFilter = filter;
        $timeout(renderTrendChart, 0);
      };

      $scope.getReliabilityClass = function (score) {
        if (score >= 70) return "text-success";
        if (score >= 40) return "text-warning";
        return "text-danger";
      };

      $scope.getReliabilityBarClass = function (score) {
        if (score >= 70) return "bg-success";
        if (score >= 40) return "bg-warning";
        return "bg-danger";
      };

      $scope.getActivityIconClass = function (type) {
        if (type === "donation") return "bg-success-subtle text-success";
        if (type === "delivery") return "bg-primary-subtle text-primary";
        if (type === "ngo") return "bg-warning-subtle text-warning";
        return "bg-secondary-subtle text-secondary";
      };

      $scope.getActivityIcon = function (type) {
        if (type === "donation") return "bi-basket";
        if (type === "delivery") return "bi-truck";
        if (type === "ngo") return "bi-building";
        return "bi-info-circle";
      };

      function loadImpactData() {
        var now = new Date();
        AuthService.getDashboardStats()
          .then(function (res) {
            var data = res && res.data && res.data.data ? res.data.data : {};
            $scope.overviewStats.totalDonations = Number(data.mealsDelivered || 0);
            $scope.overviewStats.mealsServed = Number(data.mealsDelivered || 0);
            $scope.overviewStats.ngosConnected = Number(data.partnerNGOs || 0);
            $scope.overviewStats.deliveriesCompleted = Number(data.mealsDelivered || 0);
            $scope.volunteerStats.totalDeliveries = Number(data.volunteers || 0) * 3;
            $scope.volunteerStats.reliabilityScore = 84;
          })
          .catch(function () {
            $scope.overviewStats.totalDonations = 0;
            $scope.overviewStats.mealsServed = 0;
            $scope.overviewStats.ngosConnected = 0;
            $scope.overviewStats.deliveriesCompleted = 0;
            $scope.volunteerStats.totalDeliveries = 0;
            $scope.volunteerStats.reliabilityScore = 0;
          })
          .finally(function () {
            $scope.topNgos = [
              { name: "Hope Kitchen", donationCount: 42 },
              { name: "Care Meals Network", donationCount: 35 },
              { name: "Urban Relief Trust", donationCount: 27 },
            ];
            $scope.recentActivity = [
              { type: "donation", description: "New donation posted in your city.", time: now },
              { type: "delivery", description: "Volunteer completed a delivery run.", time: new Date(now.getTime() - 3600000) },
              { type: "ngo", description: "A new NGO partner joined the platform.", time: new Date(now.getTime() - 7200000) },
            ];
            $scope.loading = false;
            $timeout(renderTrendChart, 0);
          });
      }

      $scope.$on("$destroy", function () {
        if (trendChart) trendChart.destroy();
      });

      loadImpactData();
    },
  ]);

  app.controller("SafetyGuidelinesController", [
    "$scope",
    function ($scope) {
      $scope.activeTab = "donor";
      $scope.agreedToAll = false;

      $scope.donorRules = [
        { title: "Donate Fresh Food", description: "Share only food that is safe and within expiry." },
        { title: "Provide Accurate Labels", description: "Mention food type, quantity, and preparation details." },
        { title: "Use Clean Packaging", description: "Pack donations hygienically to avoid contamination." },
      ];
      $scope.ngoRules = [
        { title: "Verify At Pickup", description: "Inspect quality and quantity before dispatch." },
        { title: "Maintain Storage Hygiene", description: "Store food using safe temperature practices." },
        { title: "Distribute Promptly", description: "Deliver food quickly to reduce spoilage risk." },
      ];
      $scope.volunteerRules = [
        { title: "Handle Carefully", description: "Transport food safely and avoid unnecessary delays." },
        { title: "Follow Route Safety", description: "Use safe routes and maintain communication." },
        { title: "Complete Handoff Proof", description: "Confirm delivery status accurately in-app." },
      ];

      $scope.setActiveTab = function (tab) {
        $scope.activeTab = tab;
      };
    },
  ]);

  function registerScrollablePolicyController(controllerName, defaultSection) {
    app.controller(controllerName, [
      "$scope",
      "$window",
      function ($scope, $window) {
        $scope.activeSection = defaultSection;
        $scope.showBackToTop = false;

        $scope.setActiveSection = function (section) {
          $scope.activeSection = section;
        };

        $scope.scrollToTop = function () {
          $window.scrollTo({ top: 0, behavior: "smooth" });
        };

        function onScroll() {
          $scope.$applyAsync(function () {
            $scope.showBackToTop = ($window.scrollY || 0) > 300;
          });
        }

        angular.element($window).on("scroll", onScroll);
        $scope.$on("$destroy", function () {
          angular.element($window).off("scroll", onScroll);
        });
      },
    ]);
  }

  registerScrollablePolicyController("TermsController", "intro");
  registerScrollablePolicyController("PrivacyController", "intro");

  app.controller("OurStoryController", [
    "$scope",
    function ($scope) {
      // Template uses root auth state; this controller is intentionally light.
    },
  ]);

  app.controller("NgoDirectoryController", [
    "$scope",
    "AuthService",
    function ($scope, AuthService) {
      $scope.loading = true;
      $scope.searchQuery = "";
      $scope.locationFilter = "";
      $scope.allNgos = [];
      $scope.filteredNgos = [];
      $scope.selectedNgo = {};

      function normalizeNgo(raw) {
        return {
          id: raw.id,
          name: raw.name || "",
          email: raw.email || "",
          location: raw.location || "",
          description: raw.description || "",
          donationCount: raw.donationCount || 0,
          is_verified: !!raw.is_verified,
          created_at: raw.created_at || null,
          phone: raw.phone || "",
        };
      }

      function applyFilters() {
        var q = String($scope.searchQuery || "").trim().toLowerCase();
        var location = String($scope.locationFilter || "").trim().toLowerCase();
        $scope.filteredNgos = $scope.allNgos.filter(function (ngo) {
          var hay = (ngo.name + " " + ngo.location + " " + ngo.email).toLowerCase();
          var queryOk = !q || hay.indexOf(q) !== -1;
          var locationOk = !location || String(ngo.location || "").toLowerCase().indexOf(location) !== -1;
          return queryOk && locationOk;
        });
      }

      $scope.filterNgos = applyFilters;

      $scope.clearFilters = function () {
        $scope.searchQuery = "";
        $scope.locationFilter = "";
        applyFilters();
      };

      $scope.viewNgoDetails = function (ngo) {
        $scope.selectedNgo = ngo || {};
        var modalEl = document.getElementById("ngoDetailModal");
        if (modalEl && typeof bootstrap !== "undefined") {
          bootstrap.Modal.getOrCreateInstance(modalEl).show();
        }
      };

      $scope.donateToNgo = function (ngo) {
        $scope.selectedNgo = ngo || {};
      };

      AuthService.getNgos()
        .then(function (res) {
          var data = Array.isArray(res.data) ? res.data : [];
          $scope.allNgos = data.map(normalizeNgo);
          applyFilters();
        })
        .catch(function () {
          $scope.allNgos = [];
          $scope.filteredNgos = [];
        })
        .finally(function () {
          $scope.loading = false;
        });
    },
  ]);

  app.controller("HelpCenterController", [
    "$scope",
    "$timeout",
    function ($scope, $timeout) {
      $scope.searchQuery = "";
      $scope.selectedCategory = "";
      $scope.activeFaqIndex = -1;
      $scope.submitting = false;
      $scope.formSubmitted = false;
      $scope.supportForm = { name: "", email: "", subject: "", message: "" };

      $scope.faqs = [
        { category: "donor", question: "How do I create a donation?", answer: "Open Donor Dashboard, fill donation details, and submit." },
        { category: "donor", question: "Why is my donation still pending?", answer: "Pending means an NGO has not accepted it yet. It updates live." },
        { category: "ngo", question: "How do I assign Delivery Partners?", answer: "Accepted donations can be assigned from NGO dashboard volunteer tools." },
        { category: "ngo", question: "Can I reject volunteers?", answer: "Yes. NGO admins can approve/reject volunteer requests in the volunteers tab." },
        { category: "volunteer", question: "How do I verify pickup OTP?", answer: "Use the OTP verification step before marking pickup complete." },
        { category: "volunteer", question: "Why can I not see deliveries?", answer: "Ensure your volunteer account is approved and assigned by an NGO." },
      ];
      $scope.filteredFaqs = $scope.faqs.slice();

      $scope.setCategory = function (category) {
        $scope.selectedCategory = category || "";
        $scope.filterFAQs();
      };

      $scope.filterFAQs = function () {
        var q = String($scope.searchQuery || "").trim().toLowerCase();
        var cat = String($scope.selectedCategory || "").trim().toLowerCase();
        $scope.filteredFaqs = $scope.faqs.filter(function (faq) {
          var categoryOk = !cat || faq.category === cat;
          var queryOk = !q || faq.question.toLowerCase().indexOf(q) !== -1 || faq.answer.toLowerCase().indexOf(q) !== -1;
          return categoryOk && queryOk;
        });
      };

      $scope.toggleFaq = function (idx) {
        $scope.activeFaqIndex = ($scope.activeFaqIndex === idx) ? -1 : idx;
      };

      $scope.submitSupportForm = function () {
        if ($scope.submitting) return;
        $scope.submitting = true;
        $timeout(function () {
          $scope.submitting = false;
          $scope.formSubmitted = true;
        }, 900);
      };
    },
  ]);

  app.controller("DonorController", [
    "$scope",
    "$rootScope",
    "$location",
    "$timeout",
    "$interval",
    "DonationService",
    "MapService",
    "LiveTrackingService",
    "AIService",
    "AuthService",
    "ChatService",
    function (
      $scope,
      $rootScope,
      $location,
      $timeout,
      $interval,
      DonationService,
      MapService,
      LiveTrackingService,
      AIService,
      AuthService,
      ChatService
    ) {
      var DEFAULT_CENTER = { lat: 28.6139, lng: 77.2090 };
      var DONATIONS_REFRESH_INTERVAL_MS = 20000;
      var TRACKING_REFRESH_INTERVAL_MS = 10000;
      var donationMap = null;
      var donationMarker = null;
      var trackingMap = null;
      var trackingVolunteerMarker = null;
      var trackingPickupMarker = null;
      var trackingNgoMarker = null;
      var trackingRoute = null;
      var donationsPollPromise = null;
      var trackingPollPromise = null;
      var addressSearchTimer = null;
      var toastTimer = null;

      function toNumber(value) {
        var n = parseFloat(value);
        return isFinite(n) ? n : null;
      }

      function normalizeStatus(value) {
        if (value && typeof value === "object" && value.value) {
          return String(value.value).toLowerCase();
        }
        return String(value || "").toLowerCase();
      }

      function toISOStringOrNull(value) {
        if (!value) return null;
        var dateValue = new Date(value);
        if (isNaN(dateValue.getTime())) return null;
        return dateValue.toISOString();
      }

      function mapFreshnessStatus(aiStatus) {
        var normalized = String(aiStatus || "").toLowerCase();
        if (normalized === "fresh") return "Fresh";
        if (normalized === "medium") return "Medium";
        if (normalized === "spoiled") return "Spoiled";
        return null;
      }

      function createdAtTime(value) {
        var ts = Date.parse(value);
        return isFinite(ts) ? ts : 0;
      }

      function getCurrentUserEmail() {
        try {
          var raw = localStorage.getItem("user");
          if (!raw) return "";
          var parsed = JSON.parse(raw);
          return parsed && parsed.email ? parsed.email : "";
        } catch (e) {
          return "";
        }
      }

      function showToast(type, message) {
        if (toastTimer) {
          $timeout.cancel(toastTimer);
          toastTimer = null;
        }
        $scope.toast.type = type || "info";
        $scope.toast.message = message || "";
        $scope.toast.visible = true;
        toastTimer = $timeout(function () {
          $scope.toast.visible = false;
        }, 3200);
      }

      function resetDonationForm() {
        $scope.newDonation = {
          food_type: "",
          quantity: null,
          food_category: "",
          expiry_time: "",
          pickup_address: "",
          pickup_latitude: null,
          pickup_longitude: null,
          latitude: null,
          longitude: null,
          image_url: null,
          freshness_status: null,
          ai_confidence_score: null,
          image_hash: null,
          image_source: null,
          image_timestamp: null,
        };
        $scope.imageSourceTab = "camera";
        $scope.aiAnalysis = null;
        $scope.aiAnalyzing = false;
        $scope.donationSubmitted = false;
        $scope.submitLoading = false;
      }

      function clearDonationMarker() {
        if (donationMap && donationMarker) {
          try {
            donationMap.removeLayer(donationMarker);
          } catch (e) {}
        }
        donationMarker = null;
      }

      function setDonationCoordinates(lat, lng, mode, addressText) {
        var parsedLat = toNumber(lat);
        var parsedLng = toNumber(lng);
        if (parsedLat === null || parsedLng === null) return;

        $scope.selectedLatitude = parsedLat;
        $scope.selectedLongitude = parsedLng;
        $scope.newDonation.pickup_latitude = parsedLat;
        $scope.newDonation.pickup_longitude = parsedLng;
        $scope.newDonation.latitude = parsedLat;
        $scope.newDonation.longitude = parsedLng;
        if (mode) $scope.locationMode = mode;
        if (addressText) {
          $scope.selectedAddress = addressText;
          $scope.newDonation.pickup_address = addressText;
        }

        if (donationMap) {
          if (donationMarker) {
            donationMarker.setLatLng([parsedLat, parsedLng]);
          } else {
            donationMarker = MapService.createMarker(
              donationMap,
              { lat: parsedLat, lng: parsedLng },
              "pin",
              "Pickup location",
              true
            );
            if (donationMarker) {
              donationMarker.on("dragend", function (evt) {
                var dragPos = evt.target.getLatLng();
                $scope.$applyAsync(function () {
                  setDonationCoordinates(dragPos.lat, dragPos.lng, "drag");
                  reverseGeocodeSelected(dragPos.lat, dragPos.lng);
                });
              });
            }
          }
          donationMap.setView([parsedLat, parsedLng], 15);
        }
      }

      function reverseGeocodeSelected(lat, lng) {
        MapService.reverseGeocode(lat, lng)
          .then(function (addressText) {
            $scope.$applyAsync(function () {
              if (!addressText) return;
              $scope.selectedAddress = addressText;
              $scope.newDonation.pickup_address = addressText;
            });
          })
          .catch(function () {});
      }

      function initDonationMap() {
        if ($scope.activeSection !== "new-donation") return;
        var mapEl = document.getElementById("donor-interactive-map");
        if (!mapEl) return;

        var center = {
          lat: $scope.selectedLatitude || DEFAULT_CENTER.lat,
          lng: $scope.selectedLongitude || DEFAULT_CENTER.lng,
        };

        if (!donationMap) {
          donationMap = MapService.initMap(
            "donor-interactive-map",
            center,
            $scope.selectedLatitude ? 14 : 12,
            { doubleClickZoom: false }
          );
          if (!donationMap) return;

          donationMap.on("dblclick", function (evt) {
            $scope.$applyAsync(function () {
              setDonationCoordinates(
                evt.latlng.lat,
                evt.latlng.lng,
                "dblclick"
              );
              reverseGeocodeSelected(evt.latlng.lat, evt.latlng.lng);
            });
          });
        } else {
          donationMap.setView(
            [center.lat, center.lng],
            $scope.selectedLatitude ? 14 : 12
          );
        }

        if ($scope.selectedLatitude && $scope.selectedLongitude) {
          setDonationCoordinates(
            $scope.selectedLatitude,
            $scope.selectedLongitude,
            $scope.locationMode || "search",
            $scope.selectedAddress
          );
        }

        $timeout(function () {
          if (donationMap) {
            try {
              donationMap.invalidateSize();
            } catch (e) {}
          }
        }, 120);
      }

      function normalizeDonation(raw) {
        var donation = angular.copy(raw || {});
        donation.status = normalizeStatus(donation.status || donation.delivery_status);
        donation.delivery_status = normalizeStatus(
          donation.delivery_status || donation.status
        );
        donation.quantity = Number(donation.quantity || 0);
        return donation;
      }

      $scope.getElapsedTime = function(startTime) {
        if (!startTime) return "0m 0s";
        var now = new Date();
        var start = new Date(startTime);
        var diff = Math.floor((now - start) / 1000);
        if (diff < 0) return "0m 0s";
        var minutes = Math.floor(diff / 60);
        var seconds = diff % 60;
        return minutes + "m " + seconds + "s";
      };

      $scope.getDeliveryStage = function(donation) {
        if (!donation) return "";
        var status = normalizeStatus(donation.status);
        if (status === "assigned") return "Heading to Donor";
        if (status === "in_progress" || status === "in_transit" || status === "picked_up") return "Delivering to NGO";
        if (status === "completed" || status === "delivered") return "Delivered";
        return "Waiting for NGO";
      };

      function recalculateDonationCollections() {
        $scope.activeDonations = $scope.myDonations.filter(function (d) {
          var status = normalizeStatus(d.status);
          return (
            status !== "completed" &&
            status !== "delivered" &&
            status !== "cancelled"
          );
        });

        $scope.historyDonations = $scope.myDonations.filter(function (d) {
          var status = normalizeStatus(d.status);
          return status === "completed" || status === "delivered";
        });

        $scope.cancelledDonations = $scope.myDonations.filter(function (d) {
          return normalizeStatus(d.status) === "cancelled";
        });

        $scope.pendingCount = $scope.myDonations.filter(function (d) {
          var status = normalizeStatus(d.status);
          return (
            status === "pending" ||
            status === "accepted" ||
            status === "assigned" ||
            status === "picked_up" ||
            status === "in_progress"
          );
        }).length;

        var completedMeals = $scope.historyDonations.reduce(function (sum, d) {
          return sum + (Number(d.quantity) || 0);
        }, 0);

        $scope.donationStats = {
          total: $scope.myDonations.length,
          pending: $scope.myDonations.filter(function (d) {
            return normalizeStatus(d.status) === "pending";
          }).length,
          completed: $scope.historyDonations.length,
          mealsSaved: completedMeals,
          carbonSaved: Number((completedMeals * 0.5).toFixed(1)),
        };

        $scope.updateFilteredDonations();
      }

      $scope.updateFilteredDonations = function () {
        var tab = String($scope.donationTab || "all").toLowerCase();
        if (tab === "active") {
          $scope.filteredDonations = $scope.activeDonations.slice();
          return;
        }
        if (tab === "completed") {
          $scope.filteredDonations = $scope.historyDonations.slice();
          return;
        }
        if (tab === "cancelled") {
          $scope.filteredDonations = $scope.cancelledDonations.slice();
          return;
        }
        $scope.filteredDonations = $scope.myDonations.slice();
      };

      function loadDonations(options) {
        options = options || {};
        var silent = !!options.silent;
        if (!silent) {
          $scope.loading = true;
          $scope.error = null;
        }

        return DonationService.getDonations(0, 200)
          .then(function (res) {
            var donations = Array.isArray(res.data) ? res.data : [];
            $scope.myDonations = donations
              .map(normalizeDonation)
              .sort(function (a, b) {
                return createdAtTime(b.created_at) - createdAtTime(a.created_at);
              });
            recalculateDonationCollections();

            if ($scope.trackedDonation && $scope.trackedDonation.id) {
              var updated = $scope.myDonations.find(function (item) {
                return item.id === $scope.trackedDonation.id;
              });
              if (updated) {
                $scope.trackedDonation = updated;
              }
            }
          })
          .catch(function (err) {
            if (!silent) {
              $scope.error = parseErrorMessage(
                err,
                "Unable to load your donations."
              );
            }
          })
          .finally(function () {
            if (!silent) {
              $scope.loading = false;
            }
          });
      }

      function loadCertificate() {
        DonationService.getCertificate()
          .then(function (res) {
            $scope.certificate = !!(res && res.data && res.data.eligible);
          })
          .catch(function () {
            $scope.certificate = false;
          });
      }

      function normalizeProfile(data) {
        data = data || {};
        return {
          id: data.id || null,
          email: data.email || getCurrentUserEmail(),
          name: data.name || "",
          phone: data.phone || "",
          address: data.address || "",
          latitude: data.latitude,
          longitude: data.longitude,
          role: normalizeRole(data.role || AuthService.getUserRole()),
          is_verified: !!data.is_verified,
          created_at: data.created_at || "",
        };
      }

      $scope.loadDonorProfile = function () {
        $scope.profileLoading = true;
        return AuthService.getUserProfile()
          .then(function (res) {
            $scope.donorProfile = normalizeProfile(res.data);
            $scope.profileForm = angular.copy($scope.donorProfile);
          })
          .catch(function (err) {
            $scope.donorProfile = null;
            $scope.profileForm = {};
            showToast(
              "danger",
              parseErrorMessage(err, "Unable to load profile.")
            );
          })
          .finally(function () {
            $scope.profileLoading = false;
          });
      };

      $scope.saveDonorProfile = function () {
        if ($scope.profileLoading) return;
        $scope.profileLoading = true;
        var payload = {
          name: String($scope.profileForm.name || "").trim(),
          phone: String($scope.profileForm.phone || "").trim(),
          address: String($scope.profileForm.address || "").trim(),
          latitude:
            $scope.profileForm.latitude === "" ||
            $scope.profileForm.latitude == null
              ? null
              : Number($scope.profileForm.latitude),
          longitude:
            $scope.profileForm.longitude === "" ||
            $scope.profileForm.longitude == null
              ? null
              : Number($scope.profileForm.longitude),
        };

        AuthService.updateUserProfile(payload)
          .then(function () {
            $scope.editingProfile = false;
            return $scope.loadDonorProfile();
          })
          .then(function () {
            showToast("success", "Profile updated successfully.");
          })
          .catch(function (err) {
            showToast(
              "danger",
              parseErrorMessage(err, "Failed to save profile.")
            );
          })
          .finally(function () {
            $scope.profileLoading = false;
          });
      };

      $scope.cancelProfileEdit = function () {
        $scope.editingProfile = false;
        $scope.profileForm = angular.copy($scope.donorProfile || {});
      };

      $scope.saveNotificationSettings = function () {
        var payload = {
          email_notifications: $scope.notificationSettings.email,
          sms_notifications: $scope.notificationSettings.sms
        };
        AuthService.updateUserProfile(payload)
          .then(function () {
            $scope.notificationSaved = true;
            $timeout(function () {
              $scope.notificationSaved = false;
            }, 2000);
          })
          .catch(function (err) {
            showToast("danger", "Failed to save notification settings.");
          });
      };

      $scope.setDonorSection = function (section) {
        $scope.activeSection = section;
        if (section === "new-donation") {
          $timeout(initDonationMap, 120);
        } else if (section === "profile") {
          $scope.loadDonorProfile();
        } else if (section === "my-donations") {
          // Always land on "Active" tab when opening My Donations
          $scope.donationTab = "active";
          $scope.updateFilteredDonations();
        }
      };

      $scope.openDonorProfile = function () {
        $scope.setDonorSection("profile");
      };

      $scope.manualRefresh = function () {
        loadDonations({ silent: false });
        loadCertificate();
        if ($scope.activeSection === "profile") {
          $scope.loadDonorProfile();
        }
      };

      $scope.useMyLocation = function () {
        if (!navigator.geolocation) {
          $scope.geoError = "Geolocation is not supported by this browser.";
          return;
        }
        $scope.geoError = null;
        $scope.mapLoading = true;

        navigator.geolocation.getCurrentPosition(
          function (position) {
            $scope.$applyAsync(function () {
              setDonationCoordinates(
                position.coords.latitude,
                position.coords.longitude,
                "gps"
              );
              reverseGeocodeSelected(
                position.coords.latitude,
                position.coords.longitude
              );
              $scope.mapLoading = false;
            });
          },
          function (error) {
            $scope.$applyAsync(function () {
              var message = "Unable to fetch your location.";
              if (error && error.code === 1) {
                message = "Location permission denied. Please enable it and retry.";
              } else if (error && error.code === 3) {
                message = "Location request timed out. Please try again.";
              }
              $scope.geoError = message;
              $scope.mapLoading = false;
            });
          },
          {
            enableHighAccuracy: true,
            timeout: 12000,
            maximumAge: 0,
          }
        );
      };

      $scope.clearLocation = function () {
        clearDonationMarker();
        $scope.locationMode = null;
        $scope.selectedLatitude = null;
        $scope.selectedLongitude = null;
        $scope.selectedAddress = "";
        $scope.newDonation.pickup_latitude = null;
        $scope.newDonation.pickup_longitude = null;
        $scope.newDonation.latitude = null;
        $scope.newDonation.longitude = null;
        $scope.newDonation.pickup_address = "";
      };

      $scope.onAddressInput = function () {
        var query = String($scope.newDonation.pickup_address || "").trim();
        $scope.selectedAddress = query;

        if (addressSearchTimer) {
          $timeout.cancel(addressSearchTimer);
          addressSearchTimer = null;
        }

        if (query.length < 3) {
          $scope.showSuggestions = false;
          $scope.addressSuggestions = [];
          return;
        }

        addressSearchTimer = $timeout(function () {
          MapService.searchAddress(query)
            .then(function (results) {
              $scope.addressSuggestions = Array.isArray(results) ? results : [];
              $scope.showSuggestions = $scope.addressSuggestions.length > 0;
            })
            .catch(function () {
              $scope.addressSuggestions = [];
              $scope.showSuggestions = false;
            });
        }, 320);
      };

      $scope.selectSuggestion = function (suggestion) {
        if (!suggestion) return;
        var lat = toNumber(suggestion.lat);
        var lng = toNumber(suggestion.lon);
        if (lat === null || lng === null) return;

        $scope.showSuggestions = false;
        $scope.addressSuggestions = [];
        setDonationCoordinates(lat, lng, "search", suggestion.display_name || "");
      };

      $scope.confirmLocation = function () {
        if (!$scope.selectedLatitude || !$scope.selectedLongitude) {
          showToast("warning", "Select a location before confirming.");
          return;
        }
        showToast("success", "Pickup location confirmed.");
      };

      $scope.setImageSourceTab = function (tab) {
        $scope.imageSourceTab = tab === "upload" ? "upload" : "camera";
      };

      $scope.handleImageUpload = function (files, source) {
        var file = files && files[0];
        if (!file) return;

        $scope.$applyAsync(function () {
          if ($scope.imagePreviewUrl && window.URL && window.URL.revokeObjectURL) {
            try {
              window.URL.revokeObjectURL($scope.imagePreviewUrl);
            } catch (e) {}
          }

          $scope.imageSourceTab = source === "upload" ? "upload" : "camera";
          $scope.imagePreviewUrl = window.URL.createObjectURL(file);
          $scope.selectedImageFile = file;
          $scope.aiAnalysis = null;
          $scope.aiAnalyzing = true;
          $scope.newDonation.image_source = $scope.imageSourceTab;

          AIService.analyzeImage(file, $scope.imageSourceTab)
            .then(function (res) {
              var analysis = res && res.data ? res.data : null;
              $scope.aiAnalysis = analysis;
              if (!analysis) return;

              var freshnessStatus = mapFreshnessStatus(analysis.freshness_status);
              if (freshnessStatus) {
                $scope.newDonation.freshness_status = freshnessStatus;
              }
              if (analysis.confidence_score != null) {
                $scope.newDonation.ai_confidence_score = Number(
                  analysis.confidence_score
                );
              }
              if (analysis.image_hash) {
                $scope.newDonation.image_hash = analysis.image_hash;
              }
              if (analysis.image_source) {
                $scope.newDonation.image_source = analysis.image_source;
              }
              if (analysis.image_timestamp) {
                $scope.newDonation.image_timestamp = analysis.image_timestamp;
              }
            })
            .catch(function (err) {
              $scope.aiAnalysis = null;
              showToast(
                "warning",
                parseErrorMessage(err, "AI analysis could not be completed.")
              );
            })
            .finally(function () {
              $scope.aiAnalyzing = false;
            });
        });
      };

      $scope.clearImage = function () {
        if ($scope.imagePreviewUrl && window.URL && window.URL.revokeObjectURL) {
          try {
            window.URL.revokeObjectURL($scope.imagePreviewUrl);
          } catch (e) {}
        }
        $scope.imagePreviewUrl = null;
        $scope.selectedImageFile = null;
        $scope.aiAnalysis = null;
        $scope.aiAnalyzing = false;
        $scope.newDonation.freshness_status = null;
        $scope.newDonation.ai_confidence_score = null;
        $scope.newDonation.image_hash = null;
        $scope.newDonation.image_source = null;
        $scope.newDonation.image_timestamp = null;
      };

      $scope.submitDonation = function () {
        if ($scope.submitLoading) return;
        $scope.error = null;

        var payload = angular.copy($scope.newDonation);
        payload.food_type = String(payload.food_type || "").trim();
        payload.quantity = Number(payload.quantity || 0);
        payload.expiry_time = toISOStringOrNull(payload.expiry_time);
        payload.pickup_latitude = toNumber(
          payload.pickup_latitude || $scope.selectedLatitude
        );
        payload.pickup_longitude = toNumber(
          payload.pickup_longitude || $scope.selectedLongitude
        );
        payload.latitude = payload.pickup_latitude;
        payload.longitude = payload.pickup_longitude;
        payload.pickup_address = String(
          payload.pickup_address || $scope.selectedAddress || ""
        ).trim();

        if (!payload.food_type || payload.quantity <= 0 || !payload.expiry_time) {
          $scope.error = "Food name, quantity, and expiry time are required.";
          return;
        }
        if (payload.pickup_latitude === null || payload.pickup_longitude === null) {
          $scope.error = "Select a valid pickup location on the map.";
          return;
        }
        if (!payload.pickup_address) {
          $scope.error = "Pickup address is required.";
          return;
        }

        $scope.submitLoading = true;
        DonationService.createDonation(payload)
          .then(function () {
            $scope.donationSubmitted = true;
            showToast("success", "Donation submitted successfully.");
            loadDonations({ silent: true });
            loadCertificate();
            $timeout(function () {
              $scope.donationSubmitted = false;
              resetDonationForm();
              $scope.clearLocation();
            }, 1800);
          })
          .catch(function (err) {
            $scope.error = parseErrorMessage(
              err,
              "Failed to submit donation. Please check your details."
            );
          })
          .finally(function () {
            $scope.submitLoading = false;
          });
      };

      function clearTrackingVisuals() {
        if (!trackingMap) return;
        if (trackingVolunteerMarker) {
          try {
            trackingMap.removeLayer(trackingVolunteerMarker);
          } catch (e) {}
        }
        if (trackingPickupMarker) {
          try {
            trackingMap.removeLayer(trackingPickupMarker);
          } catch (e) {}
        }
        if (trackingNgoMarker) {
          try {
            trackingMap.removeLayer(trackingNgoMarker);
          } catch (e) {}
        }
        if (trackingRoute) {
          MapService.clearRoute(trackingRoute);
        }
        trackingVolunteerMarker = null;
        trackingPickupMarker = null;
        trackingNgoMarker = null;
        trackingRoute = null;
      }

      function stopTrackingPoll() {
        if (trackingPollPromise) {
          $interval.cancel(trackingPollPromise);
          trackingPollPromise = null;
        }
      }

      function ensureTrackingMap(center) {
        var mapEl = document.getElementById("tracking-map");
        if (!mapEl) return null;

        var mapCenter = center || DEFAULT_CENTER;
        if (!trackingMap) {
          trackingMap = MapService.initMap("tracking-map", mapCenter, 13, {
            doubleClickZoom: true,
          });
        } else {
          trackingMap.setView([mapCenter.lat, mapCenter.lng], 13);
        }
        $timeout(function () {
          if (trackingMap) {
            try {
              trackingMap.invalidateSize();
            } catch (e) {}
          }
        }, 120);
        return trackingMap;
      }

      function renderTrackingMap(donation, trackingData) {
        if (!trackingData) return;

        var volunteerPos = {
          lat: toNumber(trackingData.latitude),
          lng: toNumber(trackingData.longitude),
        };
        var pickupPos = {
          lat: toNumber(
            donation.pickup_latitude ||
              donation.latitude ||
              trackingData.pickup_latitude
          ),
          lng: toNumber(
            donation.pickup_longitude ||
              donation.longitude ||
              trackingData.pickup_longitude
          ),
        };
        var ngoPos = {
          lat: toNumber(trackingData.ngo_latitude || donation.ngo_latitude),
          lng: toNumber(trackingData.ngo_longitude || donation.ngo_longitude),
        };
        var status = normalizeStatus(trackingData.status || donation.status);
        var headingToNgo =
          status === "picked_up" ||
          status === "in_progress" ||
          status === "in_transit" ||
          status === "completed" ||
          status === "delivered";
        var destination =
          headingToNgo && ngoPos.lat != null && ngoPos.lng != null
            ? ngoPos
            : pickupPos;

        if (volunteerPos.lat == null || volunteerPos.lng == null) {
          $scope.trackingError =
            "Volunteer location is not available yet. Please try again shortly.";
          return;
        }
        if (destination.lat == null || destination.lng == null) {
          $scope.trackingError = "Route cannot be drawn due to missing coordinates.";
          return;
        }

        var mapCenter = volunteerPos;
        var mapInstance = ensureTrackingMap(mapCenter);
        if (!mapInstance) return;

        clearTrackingVisuals();
        trackingVolunteerMarker = MapService.createMarker(
          mapInstance,
          volunteerPos,
          "vehicle",
          "Volunteer"
        );
        if (pickupPos.lat != null && pickupPos.lng != null) {
          trackingPickupMarker = MapService.createMarker(
            mapInstance,
            pickupPos,
            "donor",
            "Pickup Point"
          );
        }
        if (ngoPos.lat != null && ngoPos.lng != null) {
          trackingNgoMarker = MapService.createMarker(
            mapInstance,
            ngoPos,
            "ngo",
            trackingData.ngo_name || donation.ngo_name || "NGO Destination"
          );
        }

        MapService.drawRoute(
          mapInstance,
          volunteerPos,
          destination,
          [],
          headingToNgo ? "#198754" : "#0d6efd",
          { profile: headingToNgo ? "cycling" : "driving" }
        )
          .then(function (routeRes) {
            trackingRoute = routeRes ? routeRes.polyline : null;
            if (routeRes && routeRes.bounds) {
              mapInstance.fitBounds(routeRes.bounds);
            }
            $scope.trackingSuccess =
              "Route: " +
              (routeRes && routeRes.distanceText ? routeRes.distanceText : "--") +
              ", " +
              (routeRes && routeRes.durationText ? routeRes.durationText : "--");
            $scope.trackingError = null;
          })
          .catch(function () {
            $scope.trackingSuccess = null;
            $scope.trackingError =
              "Route generation failed. Showing latest location only.";
          });
      }

      function fetchTracking(donation, silent) {
        if (!donation || !donation.id) return;

        DonationService.trackDelivery(donation.id)
          .then(function (res) {
            var data = res && res.data ? res.data : {};
            data.donation_id = data.donation_id || donation.id;
            data.status = normalizeStatus(data.status || donation.status);
            $scope.trackingInfo = data;
            $scope.trackedDonation = donation;
            $timeout(function () {
              renderTrackingMap(donation, data);
            }, 80);
          })
          .catch(function (err) {
            if (silent) return;
            $scope.trackingSuccess = null;
            $scope.trackingError = parseErrorMessage(
              err,
              "Tracking info not available yet."
            );
          });
      }

      function startTrackingPoll(donation) {
        stopTrackingPoll();
        trackingPollPromise = $interval(function () {
          if (!$scope.trackingInfo || !$scope.trackedDonation) {
            stopTrackingPoll();
            return;
          }
          fetchTracking(donation, true);
        }, TRACKING_REFRESH_INTERVAL_MS);
      }

      $scope.trackVolunteer = function (donation) {
        if (!donation || !donation.id) return;
        $scope.trackingError = null;
        $scope.trackingSuccess = null;
        fetchTracking(donation, false);
        startTrackingPoll(donation);
      };

      $scope.cancelDonation = function (donation) {
        if (!donation || donation.cancelling) return;
        var status = normalizeStatus(donation.status);
        if (
          status !== "pending" &&
          status !== "accepted" &&
          status !== "assigned"
        ) {
          showToast(
            "warning",
            "Only pending, accepted, or assigned donations can be cancelled."
          );
          return;
        }

        var reason = window.prompt(
          "Cancellation reason (optional):",
          donation.cancel_reason || ""
        );
        if (reason === null) return;

        donation.cancelling = true;
        DonationService.cancelDonation(donation.id, reason)
          .then(function () {
            donation.status = "cancelled";
            donation.cancel_reason = reason || donation.cancel_reason || "";
            donation.cancelling = false;
            if (
              $scope.trackingInfo &&
              String($scope.trackingInfo.donation_id) === String(donation.id)
            ) {
              $scope.trackingInfo = null;
            }
            showToast("success", "Donation cancelled successfully.");
            loadDonations({ silent: true });
          })
          .catch(function (err) {
            donation.cancelling = false;
            showToast(
              "danger",
              parseErrorMessage(err, "Unable to cancel donation.")
            );
          });
      };

      $scope.undoCancel = function () {
        showToast(
          "info",
          "Undo cancellation is not available yet. Please create a new donation."
        );
      };

      $scope.fetchParticipantPhone = function (donation) {
        return donation && donation.volunteer_phone ? donation.volunteer_phone : "";
      };

      $scope.onChatInputChange = function () {
        var receiverId = $scope.chatSelectedReceiver || $rootScope.chatSelectedReceiver;
        var donationId = $scope.currentDonationId || $rootScope.currentDonationId;
        if (receiverId && donationId && ChatService && ChatService.onTyping) {
          ChatService.onTyping(receiverId, donationId);
        }
      };

      $scope.goBack = function () {
        $location.path("/");
      };

      $scope.getStatusClass = function (status) {
        return "status-" + status;
      };

      $scope.openChat = function (donation, targetRole) {
        var donationId = donation.id || donation;
        console.log("=== OPEN CHAT CALLED ===");
        console.log("Donation ID:", donationId);
        console.log("Target role:", targetRole);
        console.log("Donation object:", donation);
        
        $scope.chatPanelOpen = true;
        $scope.currentDonationId = donationId;
        $scope.chatMessageText = "";
        $scope.chatLoading = true;
        $scope.selectedReceiverName = "";
        $scope.chatError = "";
        $scope.chatMessages = [];
        $scope.chatParticipants = [];
        $scope.chatSelectedReceiver = null;
        
        console.log("chatPanelOpen set to:", $scope.chatPanelOpen);

        var token = AuthService.getToken();
        
        // Force disconnect first to ensure clean state
        ChatService.disconnect();
        
        // Small delay to ensure clean state
        $timeout(function() {
            console.log("Connecting to chat for donation:", donationId);
            ChatService.connect(donationId, token);
        }, 100);

        console.log("Fetching participants for donation:", donationId);
        ChatService.getParticipants(donationId)
          .then(function (res) {
            $scope.chatParticipants = res.data.participants || [];
            console.log("=== PARTICIPANTS FETCHED ===");
            console.log("Count:", $scope.chatParticipants.length);
            $scope.chatParticipants.forEach(function(p, idx) {
                console.log("  [" + idx + "] role:", p.role, ", user_id:", p.user_id, ", name:", p.name);
            });
            
            if (targetRole) {
              console.log("Looking for target role:", targetRole);
              var target = $scope.chatParticipants.find(function (p) {
                var match = p.role && p.role.toLowerCase() === targetRole.toLowerCase();
                console.log("  Checking:", p.role, "==", targetRole, "?", match);
                return match;
              });
              if (target) {
                $scope.chatSelectedReceiver = target.user_id;
                $scope.selectedReceiverName = target.name;
                console.log("=== SELECTED RECEIVER ===");
                console.log("User ID:", target.user_id, "Name:", target.name);
              } else {
                console.warn("=== NO PARTICIPANT FOUND FOR ROLE ===", targetRole);
                // Fallback: select first non-self participant
                var others = $scope.chatParticipants.filter(function (p) {
                    return p.user_id !== $scope.currentUserId;
                });
                if (others.length > 0) {
                    $scope.chatSelectedReceiver = others[0].user_id;
                    $scope.selectedReceiverName = others[0].name;
                    console.log("=== FALLBACK SELECTED ===", others[0].name);
                }
              }
            } else if ($scope.chatParticipants.length > 0) {
              var others = $scope.chatParticipants.filter(function (p) {
                return p.user_id !== $scope.currentUserId;
              });
              if (others.length > 0) {
                $scope.chatSelectedReceiver = others[0].user_id;
                $scope.selectedReceiverName = others[0].name;
              }
            }
            
            console.log("Final chatSelectedReceiver:", $scope.chatSelectedReceiver);
          })
          .catch(function (err) {
            console.error("=== PARTICIPANTS ERROR ===", err);
            $scope.chatError = "Failed to load participants: " + (err.data && err.data.detail || err.message);
          });

        console.log("Fetching messages for donation:", donationId);
        ChatService.getMessages(donationId)
          .then(function (res) {
            $scope.chatMessages = res.data || [];
            console.log("=== MESSAGES FETCHED ===");
            console.log("Count:", $scope.chatMessages.length);
            $scope.chatLoading = false;
          })
          .catch(function (err) {
            console.error("=== MESSAGES ERROR ===", err);
            $scope.chatError = "Failed to load messages: " + (err.data && err.data.detail || err.message);
            $scope.chatLoading = false;
          });
      };

      $scope.closeChat = function () {
        $scope.chatPanelOpen = false;
        if ($scope.currentDonationId) {
          ChatService.disconnect();
        }
      };

      $scope.sendChatMessage = function () {
        if (!$scope.chatMessageText || !$scope.chatSelectedReceiver || !$scope.currentDonationId) {
          return;
        }

        ChatService.sendMessage($scope.chatSelectedReceiver, $scope.currentDonationId, $scope.chatMessageText)
          .then(function (res) {
            $scope.chatMessageText = "";
            if (res.data && res.data.data) {
              var msgs = res.data.data;
              if (msgs.id) {
                $scope.chatMessages.push(msgs);
              }
            }
            setTimeout(function () {
              var container = document.getElementById("chatMessagesContainer");
              if (container) {
                container.scrollTop = container.scrollHeight;
              }
            }, 100);
          })
          .catch(function (err) {
            console.error("Send message error:", err);
          });
      };

      $scope.logout = function () {
        if ($scope.logoutInProgress) return;
        $scope.logoutInProgress = true;
        AuthService.logout().finally(function () {
          $scope.logoutInProgress = false;
          $rootScope.$emit("fb:authChanged");
          $location.path("/");
        });
      };

      $scope.$watch("trackingInfo", function (value) {
        if (!value) {
          stopTrackingPoll();
          clearTrackingVisuals();
        }
      });

      $scope.$on("$destroy", function () {
        if (donationsPollPromise) {
          $interval.cancel(donationsPollPromise);
          donationsPollPromise = null;
        }
        stopTrackingPoll();
        if (addressSearchTimer) {
          $timeout.cancel(addressSearchTimer);
          addressSearchTimer = null;
        }
        if (toastTimer) {
          $timeout.cancel(toastTimer);
          toastTimer = null;
        }
        if ($scope.imagePreviewUrl && window.URL && window.URL.revokeObjectURL) {
          try {
            window.URL.revokeObjectURL($scope.imagePreviewUrl);
          } catch (e) {}
        }
        clearTrackingVisuals();
      });

      $scope.sidebarOpen = false;
      $scope.activeSection = $scope.activeSection || "new-donation";
      $scope.donationTab = "active";
      $scope.toast = { visible: false, type: "info", message: "" };
      $scope.loading = false;
      $scope.submitLoading = false;
      $scope.donationSubmitted = false;
      $scope.error = null;
      $scope.geoError = null;
      $scope.mapLoading = false;
      $scope.showSuggestions = false;
      $scope.addressSuggestions = [];
      $scope.selectedLatitude = null;
      $scope.selectedLongitude = null;
      $scope.selectedAddress = "";
      $scope.locationMode = null;
      $scope.myDonations = [];
      $scope.filteredDonations = [];
      $scope.activeDonations = [];
      $scope.historyDonations = [];
      $scope.cancelledDonations = [];
      $scope.pendingCount = 0;
      $scope.trackingInfo = null;
      $scope.trackingSuccess = null;
      $scope.trackingError = null;
      $scope.trackedDonation = null;
      $scope.certificate = false;
      $scope.logoutInProgress = false;
      $scope.profileLoading = false;
      $scope.donorProfile = null;
      $scope.profileForm = {};
      $scope.editingProfile = false;
      $scope.notificationSettings = {
        email: true,
        sms: true
      };
      $scope.notificationSaved = false;
      $scope.currentUserId = AuthService.getUserId();
      $scope.currentUserEmail = getCurrentUserEmail();
      $scope.donationStats = {
        total: 0,
        pending: 0,
        completed: 0,
        mealsSaved: 0,
        carbonSaved: 0,
      };
      resetDonationForm();

      loadDonations({ silent: false });
      loadCertificate();
      if ($scope.activeSection === "profile") {
        $scope.loadDonorProfile();
      }
      $timeout(initDonationMap, 180);
      donationsPollPromise = $interval(function () {
        loadDonations({ silent: true });
      }, DONATIONS_REFRESH_INTERVAL_MS);
    },
  ]);
})();
