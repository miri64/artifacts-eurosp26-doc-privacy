CREATE TABLE cbor_paper.processed_table
PARTITION BY RANGE_BUCKET(export_id, GENERATE_ARRAY(0, 50, 1))
CLUSTER BY export_id
AS (
  SELECT
  url, req_user_agent, resp_content_length, CAST(FLOOR(50*RAND()) AS INT64) AS export_id
FROM `httparchive.summary_requests.2024_09_01_desktop`
WHERE 
  LOWER(resp_content_type) LIKE "%json%"
);
SELECT * EXCEPT(export_id)
FROM cbor_paper.processed_table
WHERE export_id IN (1, 2, 3);
SELECT * EXCEPT(export_id)
FROM cbor_paper.processed_table
WHERE export_id IN (4, 5, 6);
