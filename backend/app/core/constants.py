"""
FoodBridge – Business Constants

Centralizes magic numbers with descriptive names for maintainability.
"""

# Trust Score Adjustments
TRUST_SCORE_INCREMENT = 10
TRUST_SCORE_DECREMENT = 10
TRUST_SCORE_MAX = 100
TRUST_SCORE_MIN = 0

# Volunteer Settings
VOLUNTEER_MAX_ACTIVE_DELIVERIES = 3

# Donation Recommendation
RECOMMENDATION_DISTANCE_KM = 5.0

# Certificate Eligibility
CERTIFICATE_MIN_DONATIONS = 10

# Reward Multipliers
WASTE_REDUCTION_KG_PER_UNIT = 0.5
MEALS_PER_UNIT = 1

# Volunteer Reliability Calculation
RELIABILITY_POINTS_PER_DELIVERY = 10

# Distance Thresholds
NEARBY_DONATION_KM = 5.0

# OTP Settings
OTP_MIN = 100000
OTP_MAX = 999999
OTP_VALIDITY_MINUTES = 10
OTP_RESEND_COOLDOWN_SECONDS = 45
