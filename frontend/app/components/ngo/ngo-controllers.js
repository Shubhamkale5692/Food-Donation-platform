var app = angular.module("foodBridgeApp");

app.controller("NgoSignupController", ["$scope", "AuthService", "$window", "$timeout",
  function($scope, AuthService, $window, $timeout) {
      $scope.user = {
          role: "NGO",
          name: "",
          email: "",
          phone: "",
          password: "",
          confirmPassword: "",
          city: "",
          terms: false
      };

      $scope.loading = false;
      $scope.error = null;
      $scope.success = null;
      $scope.otpVerified = false;

      $scope.verifyOtp = function() {
          if (!$scope.user.phone) {
              $scope.error = "Please enter a mobile number first.";
              return;
          }
          $scope.error = null;
          $timeout(function() {
              $scope.otpVerified = true;
          }, 800);
      };

      function extractErrorMessage(err, fallback) {
          var detail = err && err.data ? err.data.detail : null;
          if (Array.isArray(detail) && detail.length) {
              return detail[0].msg || fallback;
          }
          if (typeof detail === "string" && detail.trim()) {
              return detail;
          }
          return fallback;
      }

      $scope.ngoSignup = function() {
          if ($scope.user.password !== $scope.user.confirmPassword) {
              $scope.error = "Passwords do not match.";
              return;
          }
          if (!$scope.user.terms) {
              $scope.error = "Please agree to the terms to continue.";
              return;
          }

          $scope.loading = true;
          $scope.error = null;
          $scope.success = null;

          var signupPayload = {
              role: "NGO",
              name: ($scope.user.name || "").trim(),
              email: ($scope.user.email || "").trim(),
              password: $scope.user.password
          };

          AuthService.register(signupPayload)
              .then(function() {
                  $scope.success = "Registration submitted. Your NGO account will be enabled after admin verification.";
                  $scope.user.password = "";
                  $scope.user.confirmPassword = "";
                  $timeout(function() {
                      $window.location.href = "#!/login";
                  }, 1800);
              })
              .catch(function(err) {
                  $scope.error = extractErrorMessage(err, "Registration failed. Please try again.");
              })
              .finally(function() {
                  $scope.loading = false;
              });
      };
  }
]);

app.controller("NgoProfileSetupController", ["$scope", "NgoService", "MapService", "$window", "$timeout",
  function($scope, NgoService, MapService, $window, $timeout) {
      var DEFAULT_MAP_CENTER = { lat: 28.6139, lng: 77.2090 };
      var NGO_PROFILE_DRAFT_KEY = "fb_ngo_profile_draft";
      var map = null;
      var locationMarker = null;

      $scope.profile = {
          logo: null, cover: null,
          tagline: "", about: "", yearEstablished: "", regNumber: "",
          foodTypes: { cooked: false, packed: false, raw: false, bakery: false },
          conditionRules: "",
          minMeals: null, maxMeals: null,
          availableDays: { m: false, t: false, w: false, th: false, f: false, s: false, su: false },
          pickupStartTime: "", pickupEndTime: "",
          storage: { fridge: false, freezer: false, heated: false },
          address: "", city: "", zipCode: "",
          lat: null, lng: null,
          ngoName: "",
          contactPerson: "", phone: "", email: "",
          deliveryMethod: "self_pickup"
      };

      $scope.loading = false;
      $scope.error = null;
      $scope.draftMessage = null;
      $scope.locationStatus = null;
      $scope.locationSearchQuery = "";
      $scope.locationSuggestions = [];
      $scope.locationLookupBusy = false;

      function toFiniteCoordinate(value) {
          var parsed = parseFloat(value);
          return isFinite(parsed) ? parsed : null;
      }

      function updateLocationStatus(message) {
          $scope.locationStatus = message;
          $timeout(function() {
              $scope.locationStatus = null;
          }, 2500);
      }

      function clearLocationSuggestions() {
          $scope.locationSuggestions = [];
      }

      function updateMapMarker(lat, lng) {
          if (!map) {
              return;
          }
          if (locationMarker) {
              MapService.removeMarker(map, locationMarker);
          }
          locationMarker = MapService.createMarker(
              map,
              { lat: lat, lng: lng },
              "ngo",
              "NGO Base Location",
              true
          );
          if (locationMarker && locationMarker.on) {
              locationMarker.on("dragend", function(evt) {
                  var p = evt.target.getLatLng();
                  $scope.$applyAsync(function() {
                      setLocation(p.lat, p.lng, { reverseGeocode: true, silentStatus: true });
                      updateLocationStatus("Location updated from map.");
                  });
              });
          }
          if (map.setView) {
              map.setView([lat, lng], 15);
          }
      }

      function ensureLocationMap() {
          if (map) {
              return map;
          }
          var lat = toFiniteCoordinate($scope.profile.lat);
          var lng = toFiniteCoordinate($scope.profile.lng);
          var center = (lat !== null && lng !== null) ? { lat: lat, lng: lng } : DEFAULT_MAP_CENTER;
          var zoom = (lat !== null && lng !== null) ? 15 : 11;

          map = MapService.initMap("ngo-profile-location-map", center, zoom);
          if (!map) {
              return null;
          }

          map.on("click", function(evt) {
              $scope.$applyAsync(function() {
                  setLocation(evt.latlng.lat, evt.latlng.lng, { reverseGeocode: true, silentStatus: true });
                  updateLocationStatus("Location selected from map.");
              });
          });

          if (lat !== null && lng !== null) {
              updateMapMarker(lat, lng);
          }

          $timeout(function() {
              if (map && map.invalidateSize) {
                  map.invalidateSize();
              }
          }, 120);

          return map;
      }

      function setLocation(lat, lng, options) {
          options = options || {};
          var parsedLat = toFiniteCoordinate(lat);
          var parsedLng = toFiniteCoordinate(lng);
          if (parsedLat === null || parsedLng === null) {
              return false;
          }

          $scope.profile.lat = Number(parsedLat.toFixed(6));
          $scope.profile.lng = Number(parsedLng.toFixed(6));

          ensureLocationMap();
          updateMapMarker($scope.profile.lat, $scope.profile.lng);

          if (options.reverseGeocode) {
              MapService.reverseGeocode($scope.profile.lat, $scope.profile.lng)
                  .then(function(fullAddress) {
                      if (!fullAddress) {
                          return;
                      }
                      $scope.$applyAsync(function() {
                          if (options.overwriteAddress || !$scope.profile.address) {
                              $scope.profile.address = fullAddress;
                          }
                      });
                  })
                  .catch(function() {
                      // Geocoding is optional; keep selected coordinates.
                  });
          }

          return true;
      }

      function restoreDraft() {
          var raw = localStorage.getItem(NGO_PROFILE_DRAFT_KEY);
          if (!raw) {
              return;
          }
          try {
              var saved = JSON.parse(raw);
              if (!saved || !saved.profile || typeof saved.profile !== "object") {
                  return;
              }
              $scope.profile = angular.extend({}, $scope.profile, saved.profile);
              $scope.draftMessage = "Draft restored.";
              $timeout(function() {
                  $scope.draftMessage = null;
              }, 2500);
          } catch (e) {
              // Ignore invalid draft payloads.
          }
      }

      function hydrateProfileFromServer() {
          NgoService.getNgoProfile()
              .then(function(res) {
                  var data = (res && res.data) ? res.data : {};
                  if (!data || !data.id) {
                      return;
                  }

                  if (!$scope.profile.ngoName) {
                      $scope.profile.ngoName = data.name || "";
                  }
                  if (!$scope.profile.contactPerson) {
                      $scope.profile.contactPerson = data.name || "";
                  }
                  if (!$scope.profile.email) {
                      $scope.profile.email = data.email || "";
                  }
                  if (!$scope.profile.phone) {
                      $scope.profile.phone = data.phone || "";
                  }
                  if (!$scope.profile.address) {
                      $scope.profile.address = data.address || "";
                  }

                  var lat = toFiniteCoordinate(data.latitude);
                  var lng = toFiniteCoordinate(data.longitude);
                  if (toFiniteCoordinate($scope.profile.lat) === null && lat !== null) {
                      $scope.profile.lat = lat;
                  }
                  if (toFiniteCoordinate($scope.profile.lng) === null && lng !== null) {
                      $scope.profile.lng = lng;
                  }

                  $timeout(function() {
                      ensureLocationMap();
                      var mergedLat = toFiniteCoordinate($scope.profile.lat);
                      var mergedLng = toFiniteCoordinate($scope.profile.lng);
                      if (mergedLat !== null && mergedLng !== null) {
                          updateMapMarker(mergedLat, mergedLng);
                      }
                  }, 0);
              })
              .catch(function() {
                  // Existing profile data is optional for first-time setup.
              });
      }

      // Pre-fill from user session
      var fbUser = localStorage.getItem("user");
      if (fbUser) {
          try {
              var u = JSON.parse(fbUser);
              $scope.profile.contactPerson = u.name || "";
              $scope.profile.email = u.email || "";
              $scope.profile.ngoName = u.name || "";
          } catch (e) {
              // Ignore malformed stored user payload.
          }
      }

      restoreDraft();
      hydrateProfileFromServer();

      $scope.goBack = function() {
          $window.history.back();
      };

      $scope.handleLogoUpload = function(files) {
          if (files && files[0]) {
              var reader = new FileReader();
              reader.onload = function(e) {
                  $scope.$apply(function() { $scope.profile.logo = e.target.result; });
              };
              reader.readAsDataURL(files[0]);
          }
      };

      $scope.handleCoverUpload = function() {
          // Handled via CSS/UI for now.
      };

      $scope.searchAddress = function() {
          var query = ($scope.locationSearchQuery || "").trim();
          if (query.length < 3) {
              clearLocationSuggestions();
              return;
          }

          $scope.locationLookupBusy = true;
          MapService.searchAddress(query)
              .then(function(results) {
                  $scope.locationSuggestions = (results || []).slice(0, 5);
              })
              .catch(function() {
                  $scope.error = "Could not search that location right now. Please use map pin or manual coordinates.";
                  clearLocationSuggestions();
              })
              .finally(function() {
                  $scope.locationLookupBusy = false;
              });
      };

      $scope.selectLocationSuggestion = function(suggestion) {
          if (!suggestion) {
              return;
          }
          var lat = toFiniteCoordinate(suggestion.lat);
          var lng = toFiniteCoordinate(suggestion.lon);
          if (lat === null || lng === null) {
              $scope.error = "Selected location does not contain valid coordinates.";
              return;
          }

          setLocation(lat, lng, { silentStatus: true });
          $scope.profile.address = suggestion.display_name || $scope.profile.address;
          $scope.locationSearchQuery = suggestion.display_name || "";
          clearLocationSuggestions();
          updateLocationStatus("Location set from search result.");
      };

      $scope.useCurrentLocation = function() {
          if (!navigator.geolocation) {
              $scope.error = "Location access is not supported in this browser.";
              return;
          }

          $scope.locationLookupBusy = true;
          navigator.geolocation.getCurrentPosition(
              function(position) {
                  $scope.$applyAsync(function() {
                      setLocation(position.coords.latitude, position.coords.longitude, { reverseGeocode: true, overwriteAddress: false, silentStatus: true });
                      updateLocationStatus("Current device location captured.");
                      $scope.locationLookupBusy = false;
                      $scope.error = null;
                  });
              },
              function() {
                  $scope.$applyAsync(function() {
                      $scope.locationLookupBusy = false;
                      $scope.error = "Could not read device location. Please allow location access or pin manually on map.";
                  });
              },
              { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
          );
      };

      $scope.syncCoordinatesFromInput = function() {
          var lat = toFiniteCoordinate($scope.profile.lat);
          var lng = toFiniteCoordinate($scope.profile.lng);
          if (lat === null || lng === null) {
              return;
          }
          ensureLocationMap();
          updateMapMarker(lat, lng);
      };

      $scope.saveDraft = function() {
          try {
              localStorage.setItem(
                  NGO_PROFILE_DRAFT_KEY,
                  JSON.stringify({
                      savedAt: new Date().toISOString(),
                      profile: angular.copy($scope.profile)
                  })
              );
              $scope.error = null;
              $scope.draftMessage = "Draft saved locally.";
              $timeout(function() {
                  $scope.draftMessage = null;
              }, 2500);
          } catch (e) {
              $scope.error = "Could not save draft in local storage.";
          }
      };

      $scope.isReadyToPublish = function() {
          var lat = toFiniteCoordinate($scope.profile.lat);
          var lng = toFiniteCoordinate($scope.profile.lng);
          return !!(
              $scope.profile.contactPerson &&
              $scope.profile.email &&
              $scope.profile.phone &&
              $scope.profile.address &&
              $scope.profile.city &&
              $scope.profile.minMeals !== null &&
              $scope.profile.maxMeals !== null &&
              $scope.profile.pickupStartTime &&
              $scope.profile.pickupEndTime &&
              lat !== null &&
              lng !== null
          );
      };

      $scope.publishProfile = function() {
          if (!$scope.isReadyToPublish()) {
              $scope.error = "Please complete required fields and choose a valid map location.";
              return;
          }

          $scope.loading = true;
          $scope.error = null;

          var lat = toFiniteCoordinate($scope.profile.lat);
          var lng = toFiniteCoordinate($scope.profile.lng);
          var street = ($scope.profile.address || "").trim();
          var city = ($scope.profile.city || "").trim();
          var fullAddress = street;
          if (city && street.toLowerCase().indexOf(city.toLowerCase()) === -1) {
              fullAddress = street ? (street + ", " + city) : city;
          }

          var payload = {
              name: (($scope.profile.ngoName || $scope.profile.contactPerson || "").trim() || "NGO"),
              phone: ($scope.profile.phone || "").trim(),
              address: fullAddress,
              latitude: lat,
              longitude: lng
          };

          NgoService.updateNgoProfile(payload)
              .then(function() {
                  localStorage.removeItem(NGO_PROFILE_DRAFT_KEY);
                  $window.location.href = "#!/ngo-dashboard";
              })
              .catch(function(err) {
                  var detail = (err && err.data && err.data.detail) ? err.data.detail : err.statusText;
                  if (Array.isArray(detail)) {
                      detail = detail.map(function(d) {
                          return d.msg || JSON.stringify(d);
                      }).join(", ");
                  }
                  $scope.error = "Failed to update profile: " + (detail || "Unknown error");
              })
              .finally(function() {
                  $scope.loading = false;
              });
      };

      $timeout(function() {
          ensureLocationMap();
      }, 300);

      $scope.$on("$destroy", function() {
          if (map) {
              try { map.remove(); } catch (e) {}
              map = null;
          }
          locationMarker = null;
      });
  }
]);
