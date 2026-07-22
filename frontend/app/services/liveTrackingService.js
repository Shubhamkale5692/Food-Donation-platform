/**
 * FoodBridge - LiveTrackingService
 * Real-time location tracking integrated with existing Leaflet map system
 */
var app = angular.module("foodBridgeApp");

console.log('[LiveTrackingService] Loading service...');

app.factory('LiveTrackingService', ['$http', '$q', '$timeout', '$interval', 'API_BASE_URL', 'WS_BASE_URL', 'AuthService',
    function($http, $q, $timeout, $interval, API_BASE_URL, WS_BASE_URL, AuthService) {
        
        console.log('[LiveTrackingService] Initialized with API_BASE_URL:', API_BASE_URL);
        console.log('[LiveTrackingService] WS_BASE_URL:', WS_BASE_URL);
        
        var service = {};
        var ws = null;
        var currentDonationId = null;
        var locationCallback = null;
        var statusCallback = null;
        var reconnectAttempts = 0;
        var maxReconnectAttempts = 5;
        var gpsInterval = null;
        
        function getWsUrl(donationId) {
            var token = AuthService.getToken();
            var baseWs = WS_BASE_URL.replace('/ws', '/ws/location');
            return baseWs + '/' + donationId + '?token=' + token;
        }
        
        service.connect = function(donationId, onLocationUpdate, onStatusChange) {
            if (ws && currentDonationId === donationId) {
                return true;
            }
            
            service.disconnect();
            
            currentDonationId = donationId;
            locationCallback = onLocationUpdate;
            statusCallback = onStatusChange;
            reconnectAttempts = 0;
            
            var wsUrl = getWsUrl(donationId);
            console.log('[LiveTracking] Connecting to:', wsUrl);
            
            var wsConnected = false;
            
            try {
                ws = new WebSocket(wsUrl);
                
                ws.onopen = function() {
                    console.log('[LiveTracking] WebSocket connected');
                    reconnectAttempts = 0;
                    wsConnected = true;
                    // Stop polling when WebSocket is active
                    service.stopPolling();
                };
                
                ws.onmessage = function(event) {
                    try {
                        var data = JSON.parse(event.data);
                        console.log('[LiveTracking] WebSocket received:', data);
                        
                        if (data.type === 'LOCATION_UPDATE' && locationCallback) {
                            locationCallback({
                                latitude: data.latitude,
                                longitude: data.longitude,
                                timestamp: data.timestamp,
                                volunteerId: data.volunteer_id,
                                status: data.status
                            });
                        } else if (data.type === 'STATUS_CHANGED' && statusCallback) {
                            statusCallback(data.new_status);
                        }
                    } catch(e) {
                        console.error('[LiveTracking] Parse error:', e);
                    }
                };
                
                ws.onerror = function(err) {
                    console.error('[LiveTracking] WebSocket error:', err);
                    // Fall back to polling on WebSocket error
                    service.startPolling(donationId);
                };
                
                ws.onclose = function(evt) {
                    console.log('[LiveTracking] WebSocket closed:', evt.code, evt.reason);
                    ws = null;
                    
                    if (currentDonationId && reconnectAttempts < maxReconnectAttempts) {
                        reconnectAttempts++;
                        console.log('[LiveTracking] Reconnecting in 3s (attempt ' + reconnectAttempts + ')');
                        $timeout(function() {
                            service.connect(currentDonationId, locationCallback, statusCallback);
                        }, 3000);
                    } else {
                        // Fall back to polling after max reconnect attempts
                        service.startPolling(donationId);
                    }
                };
                
                return true;
            } catch(e) {
                console.error('[LiveTracking] Connection failed:', e);
                // Fall back to polling
                service.startPolling(donationId);
                return false;
            }
        };
        
        service.disconnect = function() {
            service.stopGpsTracking();
            if (ws) {
                ws.onclose = null;
                ws.close();
                ws = null;
            }
            currentDonationId = null;
            locationCallback = null;
            statusCallback = null;
        };
        
        service.sendLocation = function(donationId, latitude, longitude) {
            console.log('[LiveTracking] Location update - donation:', donationId, 'lat:', latitude, 'lng:', longitude);
            return $http.post(API_BASE_URL + '/tracking/update-location', {
                donation_id: donationId,
                latitude: latitude,
                longitude: longitude
            });
        };
        
        service.markPickedUp = function(donationId, latitude, longitude) {
            console.log('[LiveTracking] Marking picked up for donation:', donationId);
            return $http.post(API_BASE_URL + '/tracking/mark-picked-up', {
                donation_id: donationId,
                latitude: latitude,
                longitude: longitude
            });
        };
        
        service.getLocation = function(donationId) {
            console.log('[LiveTracking] Fetching location for donation:', donationId);
            return $http.get(API_BASE_URL + '/tracking/track/' + donationId);
        };
        
        // Fallback polling endpoint (no auth required)
        service.pollLocation = function(donationId) {
            console.log('[LiveTracking] Polling location for donation:', donationId);
            return $http.get(API_BASE_URL + '/tracking/latest/' + donationId);
        };
        
        // Test connection to backend
        service.testConnection = function() {
            console.log('[LiveTracking] Testing connection...');
            console.log('[LiveTracking] API_BASE_URL:', API_BASE_URL);
            console.log('[LiveTracking] WS_BASE_URL:', WS_BASE_URL);
            return {
                apiUrl: API_BASE_URL,
                wsUrl: WS_BASE_URL
            };
        };
        
        service.startGpsTracking = function(donationId, intervalMs) {
            if (gpsInterval) {
                service.stopGpsTracking();
            }
            
            intervalMs = intervalMs || 5000;
            console.log('[LiveTracking] Starting GPS tracking every', intervalMs, 'ms');
            
            gpsInterval = $interval(function() {
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(
                        function(position) {
                            console.log('[LiveTracking] GPS position:', position.coords.latitude, position.coords.longitude);
                            service.sendLocation(
                                donationId, 
                                position.coords.latitude, 
                                position.coords.longitude
                            ).then(function(res) {
                                console.log('[LiveTracking] Location sent successfully');
                            }).catch(function(err) {
                                console.error('[LiveTracking] Failed to send location:', err);
                            });
                        },
                        function(error) {
                            console.error('[LiveTracking] GPS error:', error);
                        },
                        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
                    );
                }
            }, intervalMs);
            
            return gpsInterval;
        };
        
        service.stopGpsTracking = function() {
            if (gpsInterval) {
                $interval.cancel(gpsInterval);
                gpsInterval = null;
                console.log('[LiveTracking] Stopped GPS tracking');
            }
        };
        
        service.getConnectionStatus = function() {
            return ws !== null && ws.readyState === WebSocket.OPEN;
        };
        
        // Polling fallback for when WebSocket fails
        var pollingInterval = null;
        
        service.startPolling = function(donationId) {
            if (pollingInterval) {
                service.stopPolling();
            }
            console.log('[LiveTracking] Starting polling fallback for donation:', donationId);
            pollingInterval = setInterval(function() {
                service.pollLocation(donationId).then(function(res) {
                    if (res.data && res.data.has_location) {
                        console.log('[LiveTracking] Polled location:', res.data.latitude, res.data.longitude);
                        if (locationCallback) {
                            locationCallback({
                                latitude: res.data.latitude,
                                longitude: res.data.longitude,
                                timestamp: res.data.timestamp,
                                status: res.data.donation_status
                            });
                        }
                    }
                }).catch(function(err) {
                    console.warn('[LiveTracking] Poll error:', err);
                });
            }, 5000);
        };
        
        service.stopPolling = function() {
            if (pollingInterval) {
                clearInterval(pollingInterval);
                pollingInterval = null;
                console.log('[LiveTracking] Stopped polling');
            }
        };
        
        return service;
    }
]);

/**
 * FoodBridge - LiveMapHelper
 * Helper to integrate live tracking with existing Leaflet map
 */
app.factory('LiveMapHelper', ['$http', 'API_BASE_URL', 'LiveTrackingService',
    function($http, API_BASE_URL, LiveTrackingService) {
        
        var helper = {};
        
        /**
         * Initialize live tracking on an existing Leaflet map
         * @param {L.Map} map - Leaflet map instance
         * @param {Object} options - Configuration options
         */
        helper.initLiveTracking = function(map, options) {
            options = options || {};
            var donationId = options.donationId;
            var onLocationUpdate = options.onLocationUpdate || function() {};
            var onStatusChange = options.onStatusChange || function() {};
            var volunteerMarker = null;
            var routePolyline = null;
            var donorLat = options.donorLat;
            var donorLng = options.donorLng;
            var ngoLat = options.ngoLat;
            var ngoLng = options.ngoLng;
            var pollingInterval = null;
            
            // Create volunteer marker
            function createVolunteerMarker(lat, lng) {
                if (volunteerMarker) {
                    volunteerMarker.setLatLng([lat, lng]);
                } else {
                    var icon = L.divIcon({
                        html: '<div style="background:#198754;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:0 3px 10px rgba(0,0,0,0.4);border:3px solid white;"><span style="font-size:18px;">🚗</span></div>',
                        className: '',
                        iconSize: [36, 36],
                        iconAnchor: [18, 18]
                    });
                    volunteerMarker = L.marker([lat, lng], { icon: icon })
                        .addTo(map)
                        .bindPopup('<strong>Delivery Partner</strong><br/>Live location');
                }
                return volunteerMarker;
            }
            
            // Draw route using OSRM
            function drawRoute(volLat, volLng, status) {
                var isPickedUp = status === 'picked_up' || status === 'in_progress' || status === 'completed';
                var destLat = isPickedUp ? ngoLat : donorLat;
                var destLng = isPickedUp ? ngoLng : donorLng;
                
                if (!destLat || !destLng) {
                    console.warn('[LiveMap] No destination coordinates');
                    return;
                }
                
                console.log('[LiveMap] Drawing route:', isPickedUp ? 'volunteer → NGO' : 'volunteer → donor');
                
                var coords = volLng + ',' + volLat + ';' + destLng + ',' + destLat;
                var url = 'https://router.project-osrm.org/route/v1/driving/' + coords + '?overview=full&geometries=geojson';
                
                fetch(url)
                    .then(function(res) { return res.json(); })
                    .then(function(data) {
                        if (data.routes && data.routes[0]) {
                            var route = data.routes[0];
                            var latLngs = route.geometry.coordinates.map(function(c) { return [c[1], c[0]]; });
                            
                            if (routePolyline) {
                                routePolyline.setLatLngs(latLngs);
                            } else {
                                routePolyline = L.polyline(latLngs, {
                                    color: '#4a25e1',
                                    weight: 5,
                                    opacity: 0.85
                                }).addTo(map);
                            }
                            
                            var bounds = L.latLngBounds(latLngs);
                            map.fitBounds(bounds, { padding: [50, 50] });
                            
                            console.log('[LiveMap] Route drawn, distance:', (route.distance/1000).toFixed(1), 'km');
                        }
                    })
                    .catch(function(err) {
                        console.error('[LiveMap] Route error:', err);
                    });
            }
            
            // Clear route
            function clearRoute() {
                if (routePolyline) {
                    map.removeLayer(routePolyline);
                    routePolyline = null;
                }
            }
            
            // Location update handler
            function handleLocationUpdate(location) {
                console.log('[LiveMap] Location update:', location);
                createVolunteerMarker(location.latitude, location.longitude);
                drawRoute(location.latitude, location.longitude, location.status);
                onLocationUpdate(location);
            }
            
            // Status change handler
            function handleStatusChange(newStatus) {
                console.log('[LiveMap] Status changed:', newStatus);
                onStatusChange(newStatus);
                // Redraw route with new status
                if (volunteerMarker) {
                    var pos = volunteerMarker.getLatLng();
                    drawRoute(pos.lat, pos.lng, newStatus);
                }
            }
            
            // Connect to WebSocket
            if (donationId) {
                LiveTrackingService.connect(donationId, handleLocationUpdate, handleStatusChange);
                
                // Also start polling as backup
                pollingInterval = setInterval(function() {
                    LiveTrackingService.getLocation(donationId).then(function(res) {
                        if (res.data && res.data.has_location) {
                            handleLocationUpdate({
                                latitude: res.data.latitude,
                                longitude: res.data.longitude,
                                timestamp: res.data.timestamp,
                                status: res.data.donation_status
                            });
                        }
                    }).catch(function(err) {
                        console.warn('[LiveMap] Poll error:', err);
                    });
                }, 5000);
            }
            
            // Return control object
            return {
                updateLocation: handleLocationUpdate,
                updateStatus: handleStatusChange,
                setDestination: function(dLat, dLng, isNgo) {
                    if (isNgo) { ngoLat = dLat; ngoLng = dLng; }
                    else { donorLat = dLat; donorLng = dLng; }
                    if (volunteerMarker) {
                        var pos = volunteerMarker.getLatLng();
                        drawRoute(pos.lat, pos.lng, 'assigned');
                    }
                },
                destroy: function() {
                    if (pollingInterval) clearInterval(pollingInterval);
                    if (volunteerMarker) map.removeLayer(volunteerMarker);
                    clearRoute();
                    LiveTrackingService.disconnect();
                }
            };
        };
        
        return helper;
    }
]);