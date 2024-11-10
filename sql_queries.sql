-- This query retrieves metadata about the columns in the 'products' table.
-- It selects the column name, data type, nullability, default value, and whether the column is a primary key.
-- The primary key status is determined by checking if the column name exists in the list of primary key columns for the 'products' table.
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default,
    CASE 
        WHEN column_name IN (
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attnum = ANY(i.indkey)
            WHERE i.indrelid = 'products'::regclass
            AND i.indisprimary
        ) THEN 'YES'
        ELSE 'NO'
    END AS is_primary_key
FROM information_schema.columns
WHERE table_name = 'products';


