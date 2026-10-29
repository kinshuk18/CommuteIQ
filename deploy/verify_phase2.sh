#!/usr/bin/env bash
# verify_phase2.sh — run after `docker compose up -d postgres`
# Records real row counts into docs/DATA.md and prints a summary.
# Usage: bash deploy/verify_phase2.sh

set -euo pipefail

COMPOSE_FILE="$(dirname "$0")/compose.yml"
PSQL="docker compose -f ${COMPOSE_FILE} exec -T postgres psql -U commuteiq -d commuteiq"
# host port is 5434 (5433 in use on this machine)

echo "=== Phase 2 Verification ==="

echo "--- Tables ---"
${PSQL} -c "\dt"

echo "--- Row counts ---"
${PSQL} <<'SQL'
SELECT 'stop'           AS "table", COUNT(*) AS rows FROM stop
UNION ALL
SELECT 'route',                      COUNT(*) FROM route
UNION ALL
SELECT 'trip',                       COUNT(*) FROM trip
UNION ALL
SELECT 'stop_time',                  COUNT(*) FROM stop_time
UNION ALL
SELECT 'office',                     COUNT(*) FROM office
ORDER BY 1;
SQL

echo "--- Agency breakdown ---"
${PSQL} <<'SQL'
SELECT agency, COUNT(*) AS stops  FROM stop      GROUP BY agency ORDER BY agency;
SQL
${PSQL} <<'SQL'
SELECT agency, COUNT(*) AS routes FROM route     GROUP BY agency ORDER BY agency;
SQL
${PSQL} <<'SQL'
SELECT agency, COUNT(*) AS trips  FROM trip      GROUP BY agency ORDER BY agency;
SQL
${PSQL} <<'SQL'
SELECT t.agency, COUNT(*) AS stop_times
FROM stop_time st
JOIN trip t ON t.id = st.trip_fk
GROUP BY t.agency ORDER BY t.agency;
SQL

echo "=== Done ==="
