package com.commuteiq.gateway.service;

import com.commuteiq.gateway.repository.StopRepository;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

import java.util.*;

/**
 * Aggregates insight data:
 *   1. Popular routes from Redis ZSET (incremented on each plan).
 *   2. Route density from Postgres aggregate query (stops-per-route).
 */
@Service
public class InsightService {

    private final StringRedisTemplate redis;
    private final StopRepository stopRepo;
    private final Optional<KafkaTemplate<String, String>> kafka;

    public InsightService(StringRedisTemplate redis,
                          StopRepository stopRepo,
                          Optional<KafkaTemplate<String, String>> kafka) {
        this.redis   = redis;
        this.stopRepo = stopRepo;
        this.kafka    = kafka;
    }

    /**
     * Returns up to `limit` popular route keys from Redis ZSET, merged with
     * aggregate stop-count data from Postgres.
     */
    public List<Map<String, Object>> popularRoutes(int limit) {
        List<Map<String, Object>> result = new ArrayList<>();

        // Redis ZSET: routes sorted by request count descending
        Set<org.springframework.data.redis.core.ZSetOperations.TypedTuple<String>> zset =
                redis.opsForZSet().reverseRangeWithScores("popular_routes", 0, limit - 1);

        if (zset != null) {
            for (var entry : zset) {
                String key = entry.getValue();
                result.add(Map.of(
                        "route", key != null ? key : "",
                        "requests", entry.getScore() != null ? entry.getScore().longValue() : 0L,
                        "source", "redis"
                ));
            }
        }

        // Supplement with Postgres aggregate if Redis is sparse
        if (result.size() < limit) {
            List<Object[]> rows = stopRepo.popularRoutesByStopCount(limit - result.size());
            for (Object[] row : rows) {
                result.add(Map.of(
                        "route_id", row[0] != null ? row[0].toString() : "",
                        "stop_count", ((Number) row[1]).longValue(),
                        "source", "postgres"
                ));
            }
        }

        return result;
    }
}
