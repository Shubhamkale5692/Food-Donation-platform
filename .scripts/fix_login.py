import os

# --- Patch app.js ---
app_js_path = r'f:\Food Donation Platform\frontend\app\app.js'

with open(app_js_path, 'r', encoding='utf-8') as f:
    app_js = f.read()

# Replace AuthController declaration
old_decl = 'app.controller("AuthController", ["$scope", "$rootScope", "$location", "AuthService",\n  function ($scope, $rootScope, $location, AuthService) {'
new_decl = 'app.controller("AuthController", ["$scope", "$rootScope", "$location", "AuthService", "$http", "API_BASE_URL", "$window",\n  function ($scope, $rootScope, $location, AuthService, $http, API_BASE_URL, $window) {'
app_js = app_js.replace(old_decl, new_decl)
app_js = app_js.replace(old_decl.replace('\n', '\r\n'), new_decl)

old_login = '''    $scope.login = function () {
        $scope.loginData.email = $scope.user.email;
        $scope.loginData.password = $scope.user.password;
        $scope.authLoading = true;
        AuthService.login($scope.loginData.email, $scope.loginData.password)
        .then(function(res){
            if (res.data.success === false) {
                $scope.$applyAsync(function() {
                    $scope.authError = res.data.message || "Invalid email or password";
                    $scope.loginData = { email: "", password: "" };
                    $scope.user.email = "";
                    $scope.user.password = "";
                });
                return;
            }

            $rootScope.$emit("fb:authChanged");

            var role = (res.data.role || "").toLowerCase();
            
            // Close modal manually if needed
            var el = document.getElementById("authModal");
            if (el && typeof bootstrap !== 'undefined') {
              var modal = bootstrap.Modal.getInstance(el) || new bootstrap.Modal(el);
              modal.hide();
            }

            // Route based on role
            if(role === "donor"){
                $location.path("/donor-dashboard");
            } else if(role === "ngo"){
                $location.path("/ngo-dashboard");
            } else if(role === "volunteer"){
                $location.path("/volunteer-dashboard");
            } else if(role === "admin"){
                $location.path("/admin-dashboard");
            }
        })
        .catch(function(err){
            var msg = "Invalid email or password";
            if (err.data) {
                if (err.data.message) {
                    msg = err.data.message;
                } else if (err.data.detail) {
                    msg = typeof err.data.detail === 'string' ? err.data.detail : JSON.stringify(err.data.detail);
                } else if (err.status === -1 || err.status === 0) {
                    msg = "Unable to connect to server. Please try again.";
                }
            }
            $scope.$applyAsync(function() {
                $scope.authError = msg;
                $scope.loginData = { email: "", password: "" };
                $scope.user.email = "";
                $scope.user.password = "";
            });
            console.error("Login error:", err);
        })
        .finally(function() {
            $scope.authLoading = false;
        });
    };'''

new_login = '''    $scope.login = function() {
        localStorage.removeItem("token");
        localStorage.removeItem("fb_access_token");

        $scope.loading = true;
        $scope.authLoading = true;

        $scope.loginData.email = $scope.user.email;
        $scope.loginData.password = $scope.user.password;

        var loginUrl = (typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : "/api") + "/login";

        $http.post(loginUrl, $scope.loginData)
        .then(function(res) {
            if (res.data && res.data.success) {
                var t = res.data.token || res.data.access_token;
                localStorage.setItem("token", t);
                localStorage.setItem("fb_access_token", t);
                
                if (res.data.user) {
                   localStorage.setItem("user", JSON.stringify(res.data.user));
                   localStorage.setItem("fb_user", res.data.user.role || res.data.role);
                }

                $scope.loginData = { email: "", password: "" };
                $scope.user.password = "";

                $rootScope.$emit("fb:authChanged");

                if (typeof document !== 'undefined') {
                    var el = document.getElementById("authModal");
                    if (el && typeof bootstrap !== 'undefined') {
                        var modal = bootstrap.Modal.getInstance(el) || new bootstrap.Modal(el);
                        modal.hide();
                    }
                }

                var role = "";
                if (res.data.user && res.data.user.role) role = res.data.user.role.toLowerCase();
                else if (res.data.role) role = res.data.role.toLowerCase();

                if (role === "admin") {
                    $window.location.href = "#!/admin-dashboard";
                } else if (role === "ngo") {
                    $window.location.href = "#!/ngo-dashboard";
                } else if (role === "volunteer") {
                    $window.location.href = "#!/volunteer-dashboard";
                } else {
                    $window.location.href = "#!/donor-dashboard";
                }
            } else {
                $scope.authError = (res.data && res.data.message) ? res.data.message : "Invalid email or password";
                $scope.loginData = { email: "", password: "" };
                $scope.user.password = "";
            }
        })
        .catch(function(err) {
            $scope.authError = "Invalid email or password";
            $scope.loginData = { email: "", password: "" };
            $scope.user.password = "";
        })
        .finally(function() {
            $scope.loading = false;
            $scope.authLoading = false;
            $scope.$applyAsync();
        });
    };'''

app_js = app_js.replace(old_login, new_login)
app_js = app_js.replace(old_login.replace('\n', '\r\n'), new_login)

with open(app_js_path, 'w', encoding='utf-8') as f:
    f.write(app_js)
print("Updated app.js")

# --- Patch apiService.js ---
api_js_path = r'f:\Food Donation Platform\frontend\app\services\apiService.js'

with open(api_js_path, 'r', encoding='utf-8') as f:
    api_js = f.read()

old_logout = '''    this.logout = function () {
      var token = this.getToken();
      if (token) {
        // Best-effort backend logout. We do NOT wait for a response — if the
        // token is already expired the call will 401, which is fine since we
        // clear localStorage right after regardless.
        return $http.post(API_BASE_URL + "/logout")
             .finally(this.clearSession.bind(this));
      }
      return $http.post(API_BASE_URL + "/logout", {})
        .finally(this.clearSession.bind(this));
    };'''

new_logout = '''    this.logout = function () {
      this.clearSession();
      try {
        if ($window.localStorage.getItem("fb_access_token") || this.getToken()) {
             return $http.post(API_BASE_URL + "/logout").catch(function(){});
        }
      } catch (e) {}
      return { finally: function(cb) { if(cb) cb(); return this; } };
    };'''

api_js = api_js.replace(old_logout, new_logout)
api_js = api_js.replace(old_logout.replace('\n', '\r\n'), new_logout)

with open(api_js_path, 'w', encoding='utf-8') as f:
    f.write(api_js)
print("Updated apiService.js")

