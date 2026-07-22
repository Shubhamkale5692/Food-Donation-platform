-- Seed script to add more test data for dashboard display
-- Run this with: docker exec -i fooddonationplatform-db-1 psql -U postgres -d foodbridge < seed_extra.sql

-- First check existing data
-- We'll add more donations with varying statuses

-- Add more pending donations for variety
INSERT INTO donations (id, donor_id, food_type, quantity, expiry_time, status, freshness_status, latitude, longitude, created_at)
SELECT 
    gen_random_uuid(),
    id,
    (ARRAY['Fresh Bread', 'Cooked Rice', 'Vegetables', 'Fruits', 'Milk', 'Yogurt', 'Canned Soup'])[floor(random()*7)+1],
    (floor(random()*30)+5)::integer,
    NOW() + (random()*48 || ' hours')::interval,
    'pending',
    'Fresh'::donation_freshness_status,
    40.7128 + random()*0.1 - 0.05,
    -74.0060 + random()*0.1 - 0.05,
    NOW() - (random()*24 || ' hours')::interval
FROM users WHERE role = 'DONOR' LIMIT 5;

-- Add completed donations for history (these will show in completed/historical tabs)
INSERT INTO donations (id, donor_id, food_type, quantity, expiry_time, status, freshness_status, latitude, longitude, ngo_id, volunteer_id, created_at, delivery_time, delivery_status)
SELECT 
    gen_random_uuid(),
    d.id,
    (ARRAY['Rice Bags', 'Bread Loaves', 'Veggie Boxes', 'Fruit Baskets', 'Canned Food', 'Pasta Packs', 'Cereal'])[floor(random()*7)+1],
    (floor(random()*50)+10)::integer,
    NOW() - (random()*48 || ' hours')::interval,
    'completed',
    'Fresh'::donation_freshness_status,
    40.7128 + random()*0.1 - 0.05,
    -74.0060 + random()*0.1 - 0.05,
    (SELECT id FROM users WHERE role = 'NGO' LIMIT 1),
    (SELECT id FROM users WHERE role = 'VOLUNTEER' LIMIT 1),
    NOW() - (random()*10 || ' days')::interval,
    NOW() - (random()*8 || ' days')::interval,
    'delivered'
FROM (SELECT id FROM users WHERE role = 'DONOR' LIMIT 5) d;

-- Ensure we have profile data for all users
INSERT INTO profiles (user_id, name, phone, address, latitude, longitude)
SELECT id, COALESCE(name, split_part(email, '@', 1)), 
    '+1-555-' || floor(random()*9000+1000),
    (ARRAY['100 Main St', '200 Oak Ave', '300 Pine Rd', '400 Elm Blvd', '500 Maple Dr'])[floor(random()*5)+1],
    40.7128 + random()*0.1 - 0.05,
    -74.0060 + random()*0.1 - 0.05
FROM users 
WHERE id NOT IN (SELECT user_id FROM profiles);

-- Make sure all volunteers have delivery records for assigned donations
-- First check existing delivery counts
-- This will ensure that when volunteers log in, they see their assigned work