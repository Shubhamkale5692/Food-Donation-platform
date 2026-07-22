/**
 * FoodBridge - NavigationService
 * Handles routing, path drawing, and live tracking integration
 * Works with Leaflet maps already initialized by MapService
 */
var app = angular.module("foodBridgeApp");

app.factory('NavigationService', ['$http', '$q', '$interval', 'API_BASE_URL',
    function($http, $q, $interval, API_BASE_URL) {
        
        console.log('[NavigationService] Initialized');
        
        var service = {};
        
        // Route configuration
        var ROUTE_COLORS = {
            'to_donor': '#f44336',      // Red - going to pickup
            'to_ngo': '#4CAF50'          // Green - going to NGO
        };
        
        var ROUTE_PROFILE = 'driving';
        
        /**
         * Fetch route from OSRM and return GeoJSON geometry
         */
        service.fetchRoute = function(startLat, startLng, endLat, endLng) {
            return $q(function(resolve, reject) {
                if (!startLat || !startLng || !endLat || !endLng) {
                    return reject('Invalid coordinates');
                }
                
                var url = 'https://router.project-osrm.org/route/v1/driving/' 
                    + startLng + ',' + startLat + ';' + endLng + ',' + endLat 
                    + '?overview=full&geometries=geojson';
                
                console.log('[NavigationService] Fetching route:', url);
                
                $http.get(url, { timeout: 15000 })
                    .then(function(response) {
                        console.log('[NavigationService] OSRM response:', response.data);
                        
                        if (response.data && response.data.routes && response.data.routes[0]) {
                            var route = response.data.routes[0];
                            resolve({
                                geometry: route.geometry,
                                distance: route.distance,
                                duration: route.duration,
                                distanceText: (route.distance / 1000).toFixed(1) + ' km',
                                durationText: Math.ceil(route.duration / 60) + ' min'
                            });
                        } else {
                            reject('No route found');
                        }
                    })
                    .catch(function(err) {
                        console.error('[NavigationService] Route fetch error:', err);
                        reject(err);
                    });
            });
        };
        
        /**
         * Draw route on Leaflet map using GeoJSON source/layer
         * Creates source if not exists, updates data otherwise
         */
        service.drawRoute = function(map, geoJsonGeometry, color, existingLayer) {
            return $q(function(resolve, reject) {
                if (!map || !geoJsonGeometry) {
                    return reject('Map or geometry missing');
                }
                
                var L = window.L;
                if (!L) {
                    return reject('Leaflet not available');
                }
                
                var latLngs = geoJsonGeometry.coordinates.map(function(c) {
                    return [c[1], c[0]];
                });
                
                var polyline = L.polyline(latLngs, {
                    color: color || ROUTE_COLORS.to_donor,
                    weight: 5,
                    opacity: 0.85,
                    lineJoin: 'round'
                }).addTo(map);
                
                resolve({
                    polyline: polyline,
                    bounds: polyline.getBounds()
                });
            });
        };
        
        /**
         * Update existing route polyline with new geometry
         */
        service.updateRoute = function(polyline, newLatLngs) {
            if (polyline && polyline.setLatLngs) {
                polyline.setLatLngs(newLatLngs);
            }
        };
        
        /**
         * Clear route from map
         */
        service.clearRoute = function(polyline) {
            if (polyline) {
                try { polyline.remove(); } catch(e) {}
            }
        };
        
        /**
         * Create volunteer marker on map
         */
        service.createVolunteerMarker = function(map, lat, lng, existingMarker) {
            var L = window.L;
            if (!L) return null;
            
            if (existingMarker) {
                existingMarker.setLatLng([lat, lng]);
                return existingMarker;
            }
            
            var icon = L.divIcon({
                html: '<div style="background:#0d6efd;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:0 3px 10px rgba(0,0,0,0.4);border:3px solid white;"><span style="font-size:18px;">🚗</span></div>',
                className: '',
                iconSize: [36, 36],
                iconAnchor: [18, 18]
            });
            
            var marker = L.marker([lat, lng], { icon: icon })
                .addTo(map)
                .bindPopup('<strong>Delivery Partner</strong><br/>Live location');
            
            return marker;
        };
        
        /**
         * Move volunteer marker smoothly
         */
        service.moveMarker = function(marker, lat, lng) {
            if (marker && marker.setLatLng) {
                marker.setLatLng([lat, lng]);
            }
        };
        
        /**
         * Get route destination based on donation status
         * Returns { lat, lng, type: 'donor' | 'ngo' }
         */
        service.getRouteDestination = function(donation) {
            var status = String(donation.status || '').toLowerCase();
            var hasDonation = !!donation.donation_received;
            
            var headingToNgo = hasDonation && 
                (status === 'in_progress' || status === 'in_transit' || status === 'picked_up');
            
            if (headingToNgo) {
                return {
                    lat: parseFloat(donation.ngo_latitude),
                    lng: parseFloat(donation.ngo_longitude),
                    type: 'ngo'
                };
            } else {
                return {
                    lat: parseFloat(donation.pickup_latitude || donation.latitude),
                    lng: parseFloat(donation.pickup_longitude || donation.longitude),
                    type: 'donor'
                };
            }
        };
        
        /**
         * Get color for route based on destination type
         */
        service.getRouteColor = function(destinationType) {
            return destinationType === 'ngo' ? ROUTE_COLORS.to_ngo : ROUTE_COLORS.to_donor;
        };
        
        return service;
    }
]);

/**
 * FoodBridge - RouteManager
 * Manages live route updates and volunteer tracking
 * Integrates with existing map and LiveTrackingService
 */
app.factory('RouteManager', ['$http', '$q', '$interval', 'NavigationService', 'LiveTrackingService', 'API_BASE_URL',
    function($http, $q, $interval, NavigationService, LiveTrackingService, API_BASE_URL) {
        
        console.log('[RouteManager] Initialized');
        
        var manager = {};
        
        // State
        var map = null;
        var volunteerMarker = null;
        var routePolyline = null;
        var currentDonationId = null;
        var currentDonation = null;
        var pollingInterval = null;
        var lastStatus = null;
        var lastLocation = null;
        manager.eta = null;
        
        /**
         * Initialize route manager with map and donation
         */
        manager.init = function(leafletMap, donation) {
            map = leafletMap;
            currentDonation = donation;
            currentDonationId = donation.donation_id || donation.id;
            
            console.log('[RouteManager] Init with donation:', currentDonationId);
        };
        
        /**
         * Start tracking and route updates
         */
        manager.startTracking = function(donationId) {
            currentDonationId = donationId;
            
            // Connect to WebSocket for real-time updates
            LiveTrackingService.connect(donationId, 
                function(location) {
                    manager.onLocationUpdate(location);
                },
                function(newStatus) {
                    manager.onStatusChange(newStatus);
                }
            );
            
            // Start polling fallback
            manager.startPolling(donationId);
        };
        
        /**
         * Stop tracking
         */
        manager.stopTracking = function() {
            if (pollingInterval) {
                $interval.cancel(pollingInterval);
                pollingInterval = null;
            }
            LiveTrackingService.disconnect();
            currentDonationId = null;
            currentDonation = null;
        };
        
        /**
         * Calculate distance manually (Haversine formula)
         */
        function getDistance(lat1, lon1, lat2, lon2) {
            var R = 6371e3; // metres
            var φ1 = lat1 * Math.PI/180;
            var φ2 = lat2 * Math.PI/180;
            var Δφ = (lat2-lat1) * Math.PI/180;
            var Δλ = (lon2-lon1) * Math.PI/180;

            var a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
                      Math.cos(φ1) * Math.cos(φ2) *
                      Math.sin(Δλ/2) * Math.sin(Δλ/2);

            var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
            return R * c;
        }

        /**
         * Handle location update from WebSocket or polling
         */
        manager.onLocationUpdate = function(location) {
            console.log('[RouteManager] Location update:', location);
            
            if (!map || !location) return;
            
            var volPos = {
                lat: location.latitude,
                lng: location.longitude
            };
            
            // Update volunteer marker
            volunteerMarker = NavigationService.createVolunteerMarker(map, volPos.lat, volPos.lng, volunteerMarker);
            
            // Get destination based on status
            if (currentDonation) {
                var dest = NavigationService.getRouteDestination(currentDonation);
                
                if (dest.lat && dest.lng) {
                    var needsRouteFetch = !lastLocation || getDistance(lastLocation.lat, lastLocation.lng, volPos.lat, volPos.lng) > 50;
                    
                    if (needsRouteFetch) {
                        lastLocation = volPos;
                        // Fetch and draw route
                        NavigationService.fetchRoute(volPos.lat, volPos.lng, dest.lat, dest.lng)
                            .then(function(routeData) {
                                // Clear existing route
                                NavigationService.clearRoute(routePolyline);
                                
                                // Draw new route
                                var color = NavigationService.getRouteColor(dest.type);
                                NavigationService.drawRoute(map, routeData.geometry, color, routePolyline)
                                    .then(function(result) {
                                        routePolyline = result.polyline;
                                        // Commenting out map fitting bounds on every update as it causes violent stutters
                                        // map.fitBounds(result.bounds, { padding: [50, 50] });
                                        console.log('[RouteManager] Route updated, distance:', routeData.distanceText);
                                        
                                        // Update ETA for delivery tracking display
                                        manager.eta = Math.floor(routeData.duration / 60);
                                    });
                            })
                            .catch(function(err) {
                                console.error('[RouteManager] Route update failed:', err);
                            });
                    }
                }
            }
        };
        
        /**
         * Handle status change
         */
        manager.onStatusChange = function(newStatus) {
            console.log('[RouteManager] Status changed:', newStatus, 'lastStatus:', lastStatus);
            
            if (lastStatus === newStatus) return;
            lastStatus = newStatus;
            
            // Stop tracking on delivery completion or cancellation
            if (newStatus === 'completed' || newStatus === 'delivered' || newStatus === 'cancelled' || newStatus === 'rejected') {
                manager.stopTracking();
                NavigationService.clearRoute(routePolyline);
                manager.eta = null;
                return;
            }
            
            // Reload donation to get fresh data
            if (currentDonationId) {
                LiveTrackingService.getLocation(currentDonationId)
                    .then(function(res) {
                        if (res.data && res.data.has_location) {
                            manager.onLocationUpdate({
                                latitude: res.data.latitude,
                                longitude: res.data.longitude,
                                timestamp: res.data.timestamp,
                                status: newStatus
                            });
                        }
                    });
            }
        };
        
        /**
         * Start polling fallback
         */
        manager.startPolling = function(donationId) {
            if (pollingInterval) {
                $interval.cancel(pollingInterval);
            }
            
            pollingInterval = $interval(function() {
                LiveTrackingService.pollLocation(donationId)
                    .then(function(res) {
                        if (res.data && res.data.has_location) {
                            manager.onLocationUpdate({
                                latitude: res.data.latitude,
                                longitude: res.data.longitude,
                                timestamp: res.data.timestamp,
                                status: res.data.donation_status
                            });
                        }
                    });
            }, 5000);
        };
        
        /**
         * Update donation reference for route switching
         */
        manager.updateDonation = function(donation) {
            currentDonation = donation;
            lastStatus = donation.status;
        };
        
        /**
         * Clean up resources
         */
        manager.destroy = function() {
            manager.stopTracking();
            if (volunteerMarker && map) {
                try { map.removeLayer(volunteerMarker); } catch(e) {}
            }
            NavigationService.clearRoute(routePolyline);
            volunteerMarker = null;
            routePolyline = null;
            map = null;
        };
        
        return manager;
    }
]);
