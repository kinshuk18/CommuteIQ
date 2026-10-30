package com.commuteiq.gateway.service;

import com.commuteiq.gateway.dto.PlanRequest;
import com.commuteiq.gateway.dto.PlanResponse;
import com.commuteiq.gateway.repository.StopRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Orchestrates commute plan creation.
 * Cache key uses origin+dest+hour for normalised lookup;
 * ML runtime prediction is fetched from the ai-service.
 * Kafka publish is best-effort (no KafkaTemplate if bean absent).
 */
@Service
public class PlanService {

    private static final Logger log = LoggerFactory.getLogger(PlanService.class);

    private final StopRepository stopRepo;
    private final AiProxyService aiProxy;
    private final StringRedisTemplate redis;
    private final Optional<KafkaTemplate<String, String>> kafka;
    private final ObjectMapper json;
    private final MeterRegistry metrics;

    public PlanService(StopRepository stopRepo,
                       AiProxyService aiProxy,
                       StringRedisTemplate redis,
                       Optional<KafkaTemplate<String, String>> kafka,
                       ObjectMapper json,
                       MeterRegistry metrics) {
        this.stopRepo = stopRepo;
        this.aiProxy  = aiProxy;
        this.redis    = redis;
        this.kafka    = kafka;
        this.json     = json;
        this.metrics  = metrics;
    }

    /**
     * Spring Cache uses the method parameters as key.
     * The cache name `plans` is configured with 5-min TTL in RedisConfig.
     */
    @Cacheable(value = "plans", key = "#request.originStopId() + ':' + #request.destStopId() + ':' + #request.hour()")
    public PlanResponse plan(PlanRequest request) {
        int hour = request.hour() != null ? request.hour() : LocalTime.now().getHour();

        // Fetch stops for coordinate lookup
        var origin = stopRepo.findById(request.originStopId()).orElseThrow(
                () -> new IllegalArgumentException("Unknown stop: " + request.originStopId()));
        var dest = stopRepo.findById(request.destStopId()).orElseThrow(
                () -> new IllegalArgumentException("Unknown stop: " + request.destStopId()));

        // Haversine distance (km) between the two stops
        double dist = haversine(
                origin.getStopLat().doubleValue(), origin.getStopLon().doubleValue(),
                dest.getStopLat().doubleValue(), dest.getStopLon().doubleValue());

        // ML prediction from ai-service (circuit-broken in AiProxyService)
        Map<String, Object> mlPred = aiProxy.predictRuntime(
                origin.getStopLat().doubleValue(), origin.getStopLon().doubleValue(),
                dest.getStopLat().doubleValue(), dest.getStopLon().doubleValue(),
                hour);

        int estMin = extractMinutes(mlPred, dist);

        PlanResponse resp = new PlanResponse(
                request.originStopId(), request.destStopId(),
                estMin, dist,
                List.of(request.originStopId() + " → " + request.destStopId()),
                mlPred, false);

        // Publish plan event to Kafka (best-effort)
        publishPlanEvent(request, resp);

        // Track popular routes in Redis ZSET
        String routeKey = request.originStopId() + ":" + request.destStopId();
        redis.opsForZSet().incrementScore("popular_routes", routeKey, 1.0);

        metrics.counter("commuteiq_plans_total").increment();
        return resp;
    }

    private void publishPlanEvent(PlanRequest req, PlanResponse resp) {
        kafka.ifPresent(t -> {
            try {
                t.send("commute.plans", json.writeValueAsString(Map.of(
                        "origin", req.originStopId(),
                        "dest", req.destStopId(),
                        "estimatedMinutes", resp.estimatedMinutes())));
            } catch (Exception e) {
                log.warn("Kafka plan publish failed: {}", e.getMessage());
            }
        });
    }

    private int extractMinutes(Map<String, Object> mlPred, double distKm) {
        if (mlPred != null && mlPred.containsKey("predicted_minutes")) {
            Object v = mlPred.get("predicted_minutes");
            if (v instanceof Number n) return n.intValue();
        }
        // fallback: 3 min/km average Bengaluru urban speed
        return (int) Math.round(distKm * 3);
    }

    /** Haversine formula — returns distance in km. */
    private static double haversine(double lat1, double lon1, double lat2, double lon2) {
        final double R = 6371.0;
        double dLat = Math.toRadians(lat2 - lat1);
        double dLon = Math.toRadians(lon2 - lon1);
        double a = Math.sin(dLat / 2) * Math.sin(dLat / 2)
                + Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2))
                * Math.sin(dLon / 2) * Math.sin(dLon / 2);
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }
}
