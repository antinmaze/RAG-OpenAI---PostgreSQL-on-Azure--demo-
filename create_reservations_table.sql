-- ===============================================
-- RESERVATIONS TABLE CREATION WITH EXCLUSION CONSTRAINT
-- ===============================================

-- 1. Enable required extensions
-- btree_gist: Allows using standard data types (int, text) with GiST indexes
-- Required to combine item_id (integer) with daterange in exclusion constraint
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 2. Create the Reservations table
CREATE TABLE reservations (
    -- Primary key for the reservation
    resa_id SERIAL PRIMARY KEY,
    
    -- Reference to the reserved item (foreign key to items table)
    item_id INTEGER NOT NULL,
    
    -- Reservation period as a date range
    -- Using PostgreSQL's daterange type to optimize overlap calculations
    periode_reservation DATERANGE NOT NULL,
    
    -- Individual dates for easier queries (denormalized for performance)
    date_debut DATE NOT NULL,
    date_fin DATE NOT NULL,
    
    -- Client identifier (can be NULL for maintenance reservations)
    client_id INTEGER,
    
    -- Reservation status
    -- 'confirmee' : confirmed reservation by a client
    -- 'provisoire' : temporary reservation (unvalidated cart)
    -- 'maintenance' : unavailability period for maintenance
    -- 'annulee' : cancelled reservation (kept for history)
    statut VARCHAR(20) NOT NULL DEFAULT 'confirmee' 
        CHECK (statut IN ('confirmee', 'provisoire', 'maintenance', 'annulee')),
    
    -- Traceability metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraint to ensure end date is after start date
    CONSTRAINT check_dates_coherentes CHECK (date_fin > date_debut),
    
    -- Constraint to ensure daterange matches individual dates
    CONSTRAINT check_periode_coherente CHECK (
        periode_reservation = daterange(date_debut, date_fin, '[)')
    ),
    
    -- EXCLUSION CONSTRAINT: CORE OF ANTI-OVERLAP LOGIC
    -- This constraint prevents two reservations of the same item from overlapping in time
    -- Only active reservations (not cancelled) are concerned
    CONSTRAINT exclude_overlapping_reservations 
        EXCLUDE USING gist (
            -- item_id with equality operator: same item
            item_id WITH =,
            -- periode_reservation with overlap operator: overlapping periods
            periode_reservation WITH &&
        ) 
        -- Condition: constraint only applies if status is not 'annulee'
        WHERE (statut != 'annulee'),
    
    -- Foreign key to items table
    CONSTRAINT fk_reservations_item_id 
        FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

-- 3. Indexes to optimize performance
-- Index on item_id for search queries by item
CREATE INDEX idx_reservations_item_id ON reservations(item_id);

-- Index on dates for search queries by period
CREATE INDEX idx_reservations_dates ON reservations(date_debut, date_fin);

-- Index on status to filter active reservations
CREATE INDEX idx_reservations_statut ON reservations(statut);

-- GiST index on period to optimize overlap queries
CREATE INDEX idx_reservations_periode_gist ON reservations USING gist(periode_reservation);

-- Composite index for frequent queries (item + period)
CREATE INDEX idx_reservations_item_periode ON reservations USING gist(item_id, periode_reservation);

-- 4. Trigger to maintain daterange consistency
-- Automatically updates periode_reservation when date_debut or date_fin changes
CREATE OR REPLACE FUNCTION update_periode_reservation()
RETURNS TRIGGER AS $$
BEGIN
    -- Automatically recalculates daterange from individual dates
    NEW.periode_reservation := daterange(NEW.date_debut, NEW.date_fin, '[)');
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger on INSERT and UPDATE
CREATE TRIGGER trigger_update_periode_reservation
    BEFORE INSERT OR UPDATE OF date_debut, date_fin
    ON reservations
    FOR EACH ROW
    EXECUTE FUNCTION update_periode_reservation();

-- 5. Utility function to check availability
-- This function allows checking if an item is available for a given period
CREATE OR REPLACE FUNCTION check_item_availability(
    p_item_id INTEGER,
    p_date_debut DATE,
    p_date_fin DATE
) RETURNS BOOLEAN AS $$
DECLARE
    conflict_count INTEGER;
BEGIN
    -- Count reservations that overlap with the requested period
    SELECT COUNT(*)
    INTO conflict_count
    FROM reservations
    WHERE item_id = p_item_id
      AND statut != 'annulee'  -- Ignore cancelled reservations
      AND periode_reservation && daterange(p_date_debut, p_date_fin, '[)');
    
    -- Return TRUE if no conflict, FALSE otherwise
    RETURN conflict_count = 0;
END;
$$ LANGUAGE plpgsql;

-- 6. View for active reservations with detailed information
CREATE VIEW v_reservations_actives AS
SELECT 
    r.resa_id,
    r.item_id,
    i.name AS item_name,
    i.type AS item_type,
    r.date_debut,
    r.date_fin,
    r.client_id,
    r.statut,
    r.created_at,
    -- Calculate duration in days
    (r.date_fin - r.date_debut) AS duree_jours,
    -- Estimated total price (based on daily item price)
    (r.date_fin - r.date_debut) * i.price AS prix_total_estime
FROM reservations r
JOIN items i ON r.item_id = i.id
WHERE r.statut != 'annulee'
ORDER BY r.date_debut;

-- ===============================================
-- USAGE EXAMPLES
-- ===============================================

-- Example 1: Insert a normal reservation
/*
INSERT INTO reservations (item_id, date_debut, date_fin, client_id, statut)
VALUES (1, '2025-01-15', '2025-01-20', 123, 'confirmee');
*/

-- Example 2: Insert a maintenance period (blocks the item)
/*
INSERT INTO reservations (item_id, date_debut, date_fin, statut)
VALUES (1, '2025-01-25', '2025-01-27', 'maintenance');
*/

-- Example 3: Check availability before reservation
/*
SELECT check_item_availability(1, '2025-01-18', '2025-01-22') AS disponible;
-- Will return FALSE because there's overlap with existing reservation
*/

-- Example 4: View all reservations for an item
/*
SELECT * FROM v_reservations_actives WHERE item_id = 1;
*/

-- ===============================================
-- IMPORTANT TECHNICAL COMMENTS
-- ===============================================

/*
KEY POINTS OF THE SOLUTION:

1. DATERANGE vs INDIVIDUAL DATES:
   - periode_reservation (daterange): optimized for overlap calculations
   - date_debut/date_fin (date): easier to use in standard queries
   - Trigger automatically maintains consistency between both

2. EXCLUSION CONSTRAINT:
   - EXCLUDE USING gist: more performant than triggers for this use case
   - item_id WITH =: same item concerned
   - periode_reservation WITH &&: overlapping periods
   - WHERE (statut != 'annulee'): ignores cancelled reservations
   - Database-level guarantee (no need for application logic)

3. STATUS MANAGEMENT:
   - 'confirmee': validated client reservation
   - 'provisoire': temporary reservation (cart)
   - 'maintenance': system unavailability
   - 'annulee': kept for history but excluded from conflicts

4. PERFORMANCE:
   - GiST index on periode_reservation for overlap queries
   - B-tree indexes on item_id, dates, status for standard queries
   - Pre-calculated view for frequent queries

5. SECURITY AND CONSISTENCY:
   - CHECK constraints for data validation
   - Foreign keys for referential integrity
   - Trigger to maintain consistency automatically
   - Utility function to check availability

This solution guarantees that no double booking is possible while
offering optimal performance for availability queries.
*/