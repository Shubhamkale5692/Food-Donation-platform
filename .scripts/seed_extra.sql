-- Add pending donations with explicit IDs
INSERT INTO donations (id, donor_id, food_type, quantity, expiry_time, status, freshness_status, latitude, longitude, created_at)
SELECT 
    gen_random_uuid(),
    id,
    (ARRAY['Fresh Bread', 'Cooked Rice', 'Vegetables', 'Fruits', 'Milk'])[floor(random()*5)+1],
    (5 + floor(random()*20))::integer,
    NOW() + (4 + floor(random()*12)) * interval '1 hour',
    'pending',
    'Fresh',
    40.7128 + random()*0.1 - 0.05,
    -74.0060 + random()*0.1 - 0.05,
    NOW() - floor(random()*24) * interval '1 hour'
FROM users WHERE role = 'DONOR' LIMIT 5;

-- Add accepted donations with explicit IDs
INSERT INTO donations (id, donor_id, food_type, quantity, expiry_time, status, freshness_status, latitude, longitude, ngo_id, created_at)
SELECT 
    gen_random_uuid(),
    id,
    (ARRAY['Rice', 'Vegetables', 'Fruits'])[floor(random()*3)+1],
    (10 + floor(random()*15))::integer,
    NOW() + (3 + floor(random()*8)) * interval '1 hour',
    'accepted',
    'Fresh',
    40.72 + random()*0.1 - 0.05,
    -73.99 + random()*0.1 - 0.05,
    (SELECT id FROM users WHERE role = 'NGO' AND is_verified = true LIMIT 1),
    NOW() - floor(random()*12) * interval '1 hour'
FROM users WHERE role = 'DONOR' LIMIT 3;

-- Add completed donations (for history) with explicit IDs
INSERT INTO donations (id, donor_id, food_type, quantity, expiry_time, status, freshness_status, latitude, longitude, ngo_id, volunteer_id, created_at, delivery_time, delivery_status)
SELECT 
    gen_random_uuid(),
    d.id,
    (ARRAY['Rice Bags', 'Bread Loaves', 'Veggie Boxes'])[floor(random()*3)+1],
    (15 + floor(random()*25))::integer,
    NOW() - floor(random()*48) * interval '1 hour',
    'completed',
    'Fresh',
    40.73 + random()*0.1 - 0.05,
    -73.98 + random()*0.1 - 0.05,
    (SELECT id FROM users WHERE role = 'NGO' AND is_verified = true LIMIT 1),
    (SELECT id FROM users WHERE role = 'VOLUNTEER' AND volunteer_status = 'approved' LIMIT 1),
    NOW() - floor(random()*10) * interval '1 day',
    NOW() - floor(random()*8) * interval '1 day',
    'delivered'
FROM (SELECT id FROM users WHERE role = 'DONOR' LIMIT 3) d;

-- Add in_progress donations with explicit IDs
INSERT INTO donations (id, donor_id, food_type, quantity, expiry_time, status, freshness_status, latitude, longitude, ngo_id, volunteer_id, donation_received, created_at)
SELECT 
    gen_random_uuid(),
    d.id,
    'Hot Meals',
    20 + floor(random()*10)::integer,
    NOW() + 2 * interval '1 hour',
    'in_progress',
    'Fresh',
    40.71 + random()*0.05,
    -74.00 + random()*0.05,
    (SELECT id FROM users WHERE role = 'NGO' AND is_verified = true LIMIT 1),
    (SELECT id FROM users WHERE role = 'VOLUNTEER' AND volunteer_status = 'approved' LIMIT 1),
    true,
    NOW() - 3 * interval '1 hour'
FROM (SELECT id FROM users WHERE role = 'DONOR' LIMIT 2) d;