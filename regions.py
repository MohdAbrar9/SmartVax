"""
regions.py
----------
A single shared list of regions (areas an ASHA worker can be assigned
to, and a child can be registered under). Keeping this in ONE file
means the "Add Child" dropdown, the Admin region map, and the "Create
ASHA Worker" form can never fall out of sync with each other.

Coordinates are approximate city-center points, used to place markers
on the Admin Portal's Leaflet.js map.
"""

REGION_COORDINATES = {
    "Mumbai":      {"lat": 19.0760, "lng": 72.8777},
    "Navi Mumbai": {"lat": 19.0330, "lng": 73.0297},
    "Panvel":      {"lat": 18.9894, "lng": 73.1175},
    "Thane":       {"lat": 19.2183, "lng": 72.9781},
    "Kalyan":      {"lat": 19.2403, "lng": 73.1305},
}

REGION_NAMES = list(REGION_COORDINATES.keys())
