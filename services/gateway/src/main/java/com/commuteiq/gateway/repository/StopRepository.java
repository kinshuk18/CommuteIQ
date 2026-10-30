package com.commuteiq.gateway.repository;

import com.commuteiq.gateway.entity.Stop;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface StopRepository extends JpaRepository<Stop, String> {

    /** Full-text search on stop name (case-insensitive prefix). */
    @Query("SELECT s FROM Stop s WHERE LOWER(s.stopName) LIKE LOWER(CONCAT(:q, '%')) ORDER BY s.stopName")
    List<Stop> searchByName(@Param("q") String q);

    /**
     * Bounding-box pre-filter followed by Haversine distance sort.
     * Haversine formula keeps the maths in SQL so no round-trips.
     * 1 degree ≈ 111 km; bbox delta = radiusKm / 111.
     */
    @Query(value = """
            SELECT *,
                   (6371 * acos(
                       cos(radians(:lat)) * cos(radians(stop_lat))
                       * cos(radians(stop_lon) - radians(:lon))
                       + sin(radians(:lat)) * sin(radians(stop_lat))
                   )) AS distance_km
            FROM stops
            WHERE stop_lat BETWEEN :lat - :delta AND :lat + :delta
              AND stop_lon BETWEEN :lon - :delta AND :lon + :delta
              AND (6371 * acos(
                       cos(radians(:lat)) * cos(radians(stop_lat))
                       * cos(radians(stop_lon) - radians(:lon))
                       + sin(radians(:lat)) * sin(radians(stop_lat))
                   )) <= :radiusKm
            ORDER BY distance_km
            LIMIT :limit
            """, nativeQuery = true)
    List<Stop> findNearby(
            @Param("lat") double lat,
            @Param("lon") double lon,
            @Param("radiusKm") double radiusKm,
            @Param("delta") double delta,
            @Param("limit") int limit);

    /**
     * Aggregate: count stops per route (via stop_times join).
     * Used by /insights/popular to surface route density.
     */
    @Query(value = """
            SELECT st.route_id, COUNT(DISTINCT st.stop_id) AS stop_count
            FROM stop_times st
            GROUP BY st.route_id
            ORDER BY stop_count DESC
            LIMIT :limit
            """, nativeQuery = true)
    List<Object[]> popularRoutesByStopCount(@Param("limit") int limit);
}
