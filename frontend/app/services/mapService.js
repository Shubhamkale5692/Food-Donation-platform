/**
 * FoodBridge - MapService (Leaflet.js Edition + Mapbox upgrade)
 * Keeps Leaflet UI, adds production-grade Mapbox Directions/Geocoding support.
 * All method signatures are identical to the previous Google Maps version.
 *
 * Priority order:
 *  - Routing   : Mapbox Directions API (if token present), else OSRM fallback
 *  - Geocoding : Mapbox Geocoding API (if token present), else Nominatim fallback
 *  - Map tiles : Mapbox style tiles (if token present), else OpenStreetMap tiles
 *
 * Token sources:
 *  - window.FOODBRIDGE_MAPBOX_TOKEN
 *  - localStorage["FOODBRIDGE_MAPBOX_TOKEN"]
 */
var app = angular.module("foodBridgeApp");

app.factory('MapService', ['$http', function($http) {
    var MAPBOX_TOKEN = '';
    if (typeof window !== 'undefined') {
        MAPBOX_TOKEN =
            window.FOODBRIDGE_MAPBOX_TOKEN ||
            (window.localStorage && window.localStorage.getItem('FOODBRIDGE_MAPBOX_TOKEN')) ||
            '';
    }
    var HAS_MAPBOX = !!MAPBOX_TOKEN;
    var MAPBOX_DIRECTIONS_URL = 'https://api.mapbox.com/directions/v5/';
    var MAPBOX_GEOCODING_URL = 'https://api.mapbox.com/geocoding/v5/mapbox.places/';

    // ── Custom role-based marker icons ─────────────────────────────────────
    // Colours follow the spec: Donor=Green, Volunteer=Blue, NGO=Orange
    var MARKER_COLORS = {
        'donor'   : { bg: '#198754', border: '#146c43', emoji: '📦' },  // Green
        'vehicle' : { bg: '#0d6efd', border: '#0a58ca', emoji: '🚗' },  // Blue (volunteer)
        'ngo'     : { bg: '#fd7e14', border: '#dc6b0a', emoji: '🏢' },  // Orange
        'user'    : { bg: '#6f42c1', border: '#5a379c', emoji: '📍' },  // Purple – live location
        'pin'     : { bg: '#dc3545', border: '#b02a37', emoji: '📌' },  // Red – dblclick pin
        'default' : { bg: '#dc3545', border: '#b02a37', emoji: '📍' }
    };

    function makeIcon(iconType, size) {
        var c = MARKER_COLORS[iconType] || MARKER_COLORS['default'];
        size = size || 34;
        var half = size / 2;
        var html = '<div style="'
            + 'background:' + c.bg + ';'
            + 'border:3px solid ' + c.border + ';'
            + 'border-radius:50% 50% 50% 0;'
            + 'transform:rotate(-45deg);'
            + 'width:' + size + 'px;height:' + size + 'px;'
            + 'box-shadow:0 4px 12px rgba(0,0,0,0.35);'
            + 'display:flex;align-items:center;justify-content:center;'
            + 'transition:transform 0.2s;'
            + '"><span style="transform:rotate(45deg);font-size:' + (size * 0.42) + 'px;">' + c.emoji + '</span></div>';
        return L.divIcon({
            html: html,
            iconSize: [size, size],
            iconAnchor: [half, size],
            popupAnchor: [0, -size],
            className: ''
        });
    }

    // ── initMap ────────────────────────────────────────────────────────────
    /**
     * Creates and returns a Leaflet map instance.
     * @param {string} elementId
     * @param {{lat, lng}} center
     * @param {number}  zoom
     * @param {object}  options  Extra Leaflet options (e.g. {doubleClickZoom: false})
     * @returns {L.Map|null}
     */
    function initMap(elementId, center, zoom, options) {
        zoom = zoom || 14;
        var mapEl = document.getElementById(elementId);
        if (!mapEl) return null;

        // Destroy previous instance if element was re-used
        if (mapEl._leaflet_id) {
            var existing = mapEl._leafletMap;
            if (existing) { try { existing.remove(); } catch(e){} }
        }

        var mapOptions = angular.extend({
            center: [center.lat, center.lng],
            zoom: zoom,
            zoomControl: true,
            doubleClickZoom: false   // Prevent accidental zoom on double-click (default off)
        }, options || {});

        var map = L.map(elementId, mapOptions);
        mapEl._leafletMap = map;

        if (HAS_MAPBOX) {
            L.tileLayer(
                'https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token=' + MAPBOX_TOKEN,
                {
                    id: 'mapbox/streets-v12',
                    tileSize: 512,
                    zoomOffset: -1,
                    maxZoom: 20,
                    attribution: '&copy; <a href="https://www.mapbox.com/about/maps/">Mapbox</a> &copy; OpenStreetMap contributors'
                }
            ).addTo(map);
        } else {
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                maxZoom: 19
            }).addTo(map);
        }

        return map;
    }

    // ── createMarker ───────────────────────────────────────────────────────
    /**
     * Adds a styled marker to the map.
     * @param {L.Map}    map
     * @param {{lat,lng}} position
     * @param {string}   iconType  'donor'|'vehicle'|'ngo'|'user'|'pin'|'default'
     * @param {string}   title
     * @param {boolean}  isDraggable
     * @returns {L.Marker|null}
     */
    function createMarker(map, position, iconType, title, isDraggable) {
        if (!map || !position) return null;
        isDraggable = isDraggable || false;

        var marker = L.marker([position.lat, position.lng], {
            icon: makeIcon(iconType),
            title: title || '',
            draggable: isDraggable
        });

        marker.addTo(map);
        if (title) {
            marker.bindPopup('<strong>' + title + '</strong>');
        }
        return marker;
    }

    // ── removeMarker ───────────────────────────────────────────────────────
    /**
     * Safely removes a marker from its map.
     * @param {L.Map}    map
     * @param {L.Marker} marker
     */
    function removeMarker(map, marker) {
        if (marker && map) {
            try { map.removeLayer(marker); } catch(e){}
        }
    }

    // ── drawRoute ──────────────────────────────────────────────────────────
    /**
     * Draws a route polyline via OSRM and returns route metadata.
     * Falls back to distance-only metadata when route providers are unreachable.
     */
    function drawRoute(map, origin, destination, waypoints, polylineColor, routeOptions) {
        polylineColor = polylineColor || '#4a25e1';
        waypoints = waypoints || [];
        routeOptions = routeOptions || {};

        var requestedProfile = String(routeOptions.profile || 'driving').toLowerCase();
        var profile = (requestedProfile === 'cycling' || requestedProfile === 'walking')
            ? requestedProfile
            : 'driving';

        return new Promise(function(resolve, reject) {
            if (!map) return reject('Map not initialized');
            if (!origin || !destination) return reject('Missing route coordinates');
            if (
                !isFinite(origin.lat) || !isFinite(origin.lng) ||
                !isFinite(destination.lat) || !isFinite(destination.lng)
            ) {
                return reject('Invalid route coordinates');
            }

            var coords = [origin].concat(waypoints).concat([destination])
                .map(function(pt) { return pt.lng + ',' + pt.lat; })
                .join(';');

            function renderRoute(routeData, fromProvider) {
                var latLngs = routeData.geometry.coordinates.map(function(c) { return [c[1], c[0]]; });
                var polyline = L.polyline(latLngs, {
                    color: polylineColor,
                    weight: 5,
                    opacity: 0.9,
                    lineJoin: 'round'
                }).addTo(map);

                resolve({
                    polyline     : polyline,
                    distanceRaw  : routeData.distance,
                    timeRaw      : routeData.duration,
                    distanceText : (routeData.distance / 1000).toFixed(1) + ' km',
                    durationText : Math.ceil(routeData.duration / 60) + ' min',
                    path         : latLngs,
                    bounds       : polyline.getBounds(),
                    provider     : fromProvider
                });
            }

            function fallbackNoLine(errLabel) {
                var distM = haversineDistance(origin, destination);
                var speedKmh = 35;
                if (profile === 'cycling') {
                    speedKmh = 15;
                } else if (profile === 'walking') {
                    speedKmh = 5;
                }
                var estimatedMinutes = Math.max(1, Math.ceil((distM / 1000) / speedKmh * 60));
                var bounds = L.latLngBounds(
                    [origin.lat, origin.lng],
                    [destination.lat, destination.lng]
                );
                console.warn('[FoodBridge Map] route unavailable:', errLabel);
                resolve({
                    polyline     : null,
                    distanceRaw  : distM,
                    timeRaw      : estimatedMinutes * 60,
                    distanceText : (distM / 1000).toFixed(1) + ' km',
                    durationText : estimatedMinutes + ' min (est.)',
                    path         : [],
                    bounds       : bounds,
                    provider     : 'distance_estimate'
                });
            }

            function requestOsrmCandidates() {
                var query = '?overview=full&geometries=geojson';
                var candidates = [];

                if (profile === 'cycling') {
                    candidates = [
                        'https://router.project-osrm.org/route/v1/cycling/' + coords + query,
                        'https://routing.openstreetmap.de/routed-bike/route/v1/driving/' + coords + query
                    ];
                } else if (profile === 'walking') {
                    candidates = [
                        'https://router.project-osrm.org/route/v1/walking/' + coords + query,
                        'https://routing.openstreetmap.de/routed-foot/route/v1/driving/' + coords + query
                    ];
                } else {
                    candidates = [
                        'https://router.project-osrm.org/route/v1/driving/' + coords + query,
                        'https://routing.openstreetmap.de/routed-car/route/v1/driving/' + coords + query
                    ];
                }

                function requestCandidate(idx) {
                    if (idx >= candidates.length) {
                        return fallbackNoLine('OSRM_ALL_PROVIDERS_FAILED');
                    }

                    $http.get(candidates[idx], { timeout: 12000 })
                        .then(function(response) {
                            console.log('[MapService] OSRM API response:', response.data);
                            var route = response.data && response.data.routes && response.data.routes[0];
                            if (!route || !route.geometry || !route.geometry.coordinates || !route.geometry.coordinates.length) {
                                return requestCandidate(idx + 1);
                            }
                            renderRoute(route, idx === 0 ? 'osrm_primary' : 'osrm_fallback');
                        })
                        .catch(function(err) {
                            console.log('[MapService] OSRM request failed:', err);
                            requestCandidate(idx + 1);
                        });
                }

                requestCandidate(0);
            }

            if (HAS_MAPBOX) {
                var mapboxProfile = 'mapbox/driving-traffic';
                if (profile === 'cycling') mapboxProfile = 'mapbox/cycling';
                if (profile === 'walking') mapboxProfile = 'mapbox/walking';
                var mapboxUrl = MAPBOX_DIRECTIONS_URL + mapboxProfile + '/' + coords;
                $http.get(mapboxUrl, {
                    timeout: 12000,
                    params: {
                        access_token: MAPBOX_TOKEN,
                        alternatives: false,
                        geometries: 'geojson',
                        overview: 'full',
                        steps: false
                    }
                }).then(function(response) {
                    var route = response.data && response.data.routes && response.data.routes[0];
                    if (!route || !route.geometry || !route.geometry.coordinates || !route.geometry.coordinates.length) {
                        return requestOsrmCandidates();
                    }
                    renderRoute(route, 'mapbox');
                }).catch(function() {
                    requestOsrmCandidates();
                });
            } else {
                requestOsrmCandidates();
            }
        });
    }

    function haversineDistance(a, b) {
        var R = 6371000;
        var dLat = (b.lat - a.lat) * Math.PI / 180;
        var dLng = (b.lng - a.lng) * Math.PI / 180;
        var x = Math.sin(dLat/2) * Math.sin(dLat/2)
              + Math.cos(a.lat * Math.PI/180) * Math.cos(b.lat * Math.PI/180)
              * Math.sin(dLng/2) * Math.sin(dLng/2);
        return R * 2 * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x));
    }

    // ── clearRoute ─────────────────────────────────────────────────────────
    function clearRoute(polyline) {
        if (polyline && polyline.remove) {
            try { polyline.remove(); } catch(e){}
        }
    }

    // ── moveMarkerSmoothly ─────────────────────────────────────────────────
    function moveMarkerSmoothly(marker, newPos) {
        if (!marker || !newPos) return;
        marker.setLatLng([newPos.lat, newPos.lng]);
    }

    // ── reverseGeocode ─────────────────────────────────────────────────────
    function reverseGeocode(lat, lng) {
        return new Promise(function(resolve, reject) {
            function fallbackNominatim() {
                $http.get('https://nominatim.openstreetmap.org/reverse', {
                    params: { format: 'json', lat: lat, lon: lng, zoom: 17, addressdetails: 0 },
                    headers: { 'Accept-Language': 'en' }
                }).then(function(res) {
                    if (res.data && res.data.display_name) resolve(res.data.display_name);
                    else reject('No address');
                }).catch(function(err) { reject(err); });
            }

            if (HAS_MAPBOX) {
                var revUrl = MAPBOX_GEOCODING_URL + lng + ',' + lat + '.json';
                $http.get(revUrl, {
                    timeout: 10000,
                    params: {
                        access_token: MAPBOX_TOKEN,
                        limit: 1
                    }
                }).then(function(res) {
                    var features = res.data && res.data.features ? res.data.features : [];
                    if (features.length && features[0].place_name) {
                        resolve(features[0].place_name);
                    } else {
                        fallbackNominatim();
                    }
                }).catch(function() {
                    fallbackNominatim();
                });
            } else {
                fallbackNominatim();
            }
        });
    }

    // ── searchAddress ──────────────────────────────────────────────────────
    function searchAddress(query) {
        return new Promise(function(resolve, reject) {
            function fallbackNominatim() {
                $http.get('https://nominatim.openstreetmap.org/search', {
                    params: { format: 'json', q: query, limit: 5, addressdetails: 0 },
                    headers: { 'Accept-Language': 'en' }
                }).then(function(res) {
                    resolve(res.data || []);
                }).catch(function(err) { reject(err); });
            }

            if (HAS_MAPBOX) {
                var searchUrl = MAPBOX_GEOCODING_URL + encodeURIComponent(query) + '.json';
                $http.get(searchUrl, {
                    timeout: 10000,
                    params: {
                        access_token: MAPBOX_TOKEN,
                        limit: 5,
                        autocomplete: true
                    }
                }).then(function(res) {
                    var features = res.data && res.data.features ? res.data.features : [];
                    var normalized = features.map(function(f) {
                        return {
                            lat: String(f.center[1]),
                            lon: String(f.center[0]),
                            display_name: f.place_name
                        };
                    });
                    resolve(normalized);
                }).catch(function() {
                    fallbackNominatim();
                });
            } else {
                fallbackNominatim();
            }
        });
    }

    return {
        initMap           : initMap,
        createMarker      : createMarker,
        removeMarker      : removeMarker,
        drawRoute         : drawRoute,
        clearRoute        : clearRoute,
        moveMarkerSmoothly: moveMarkerSmoothly,
        reverseGeocode    : reverseGeocode,
        searchAddress     : searchAddress
    };
}]);
