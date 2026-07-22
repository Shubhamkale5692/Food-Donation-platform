/**
 * Achievements Controller - Certificate & Achievement Display
 */
var app = angular.module("foodBridgeApp");

app.controller("AchievementsController", [
    "$scope",
    "$rootScope",
    "$http",
    "$timeout",
    function ($scope, $rootScope, $http, $timeout) {
        $scope.loading = true;
        $scope.certificates = [];
        $scope.achievements = [];
        $scope.error = null;

        var apiBase = "/api/v1";

        function loadCertificates() {
            return $http.get(apiBase + "/user/certificates")
                .then(function (res) {
                    $scope.certificates = Array.isArray(res.data) ? res.data : [];
                })
                .catch(function (err) {
                    console.warn("[Achievements] Failed to load certificates:", err);
                    $scope.certificates = [];
                });
        }

        function loadAchievements() {
            return $http.get(apiBase + "/user/achievements")
                .then(function (res) {
                    $scope.achievements = Array.isArray(res.data) ? res.data : [];
                })
                .catch(function (err) {
                    console.warn("[Achievements] Failed to load achievements:", err);
                    $scope.achievements = [];
                });
        }

        $scope.formatDate = function (dateStr) {
            if (!dateStr) return "N/A";
            try {
                var date = new Date(dateStr);
                return date.toLocaleDateString("en-US", {
                    year: "numeric",
                    month: "long",
                    day: "numeric"
                });
            } catch (e) {
                return dateStr;
            }
        };

        $scope.getCertDownloadUrl = function (url) {
            if (!url) return "#";
            if (url.startsWith("http")) return url;
            return "/" + url;
        };

        function loadAll() {
            $scope.loading = true;
            $scope.error = null;

            $timeout(function () {
                loadCertificates()
                    .then(loadAchievements)
                    .finally(function () {
                        $scope.loading = false;
                    });
            }, 100);
        }

        $rootScope.$on("fb:authChanged", function () {
            loadAll();
        });

        loadAll();
    }
]);
