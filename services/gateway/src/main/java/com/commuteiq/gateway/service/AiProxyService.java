package com.commuteiq.gateway.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.github.resilience4j.retry.annotation.Retry;
import io.github.resilience4j.timelimiter.annotation.TimeLimiter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.Map;
import java.util.concurrent.CompletableFuture;

/**
 * Proxies calls to the Python ai-service.
 * Resilience4j annotations provide:
 *   - CircuitBreaker: opens after 50% failures in a 10-call sliding window
 *   - Retry: up to 3 attempts with 500ms wait
 *   - TimeLimiter: 30-second overall timeout (applied at call-site as async)
 *
 * The shared-secret header is injected by WebClientConfig.
 */
@Service
public class AiProxyService {

    private static final Logger log = LoggerFactory.getLogger(AiProxyService.class);
    private static final String CB = "ai-service";

    private final WebClient client;
    private final ObjectMapper json;

    public AiProxyService(WebClient aiWebClient, ObjectMapper json) {
        this.client = aiWebClient;
        this.json   = json;
    }

    @CircuitBreaker(name = CB, fallbackMethod = "predictFallback")
    @Retry(name = CB)
    public Map<String, Object> predictRuntime(double fromLat, double fromLon,
                                              double toLat, double toLon,
                                              int hour) {
        String body = client.post()
                .uri("/predict/runtime")
                .bodyValue(Map.of(
                        "from_lat", fromLat, "from_lon", fromLon,
                        "to_lat", toLat, "to_lon", toLon, "hour", hour))
                .retrieve()
                .bodyToMono(String.class)
                .block();
        return parseMap(body);
    }

    /** Circuit-breaker fallback — returns a sentinel so PlanService can degrade. */
    public Map<String, Object> predictFallback(double fl, double fo, double tl, double to,
                                               int hour, Throwable t) {
        log.warn("ai-service circuit breaker / retry exhausted: {}", t.getMessage());
        return Map.of("predicted_minutes", -1, "source", "fallback");
    }

    @CircuitBreaker(name = CB, fallbackMethod = "askFallback")
    @Retry(name = CB)
    public Map<String, Object> ask(String query, String userId) {
        String body = client.post()
                .uri("/ask")
                .bodyValue(Map.of("query", query, "user_id", userId != null ? userId : "gateway"))
                .retrieve()
                .bodyToMono(String.class)
                .block();
        return parseMap(body);
    }

    public Map<String, Object> askFallback(String query, String userId, Throwable t) {
        log.warn("ai-service /ask unavailable: {}", t.getMessage());
        return Map.of("answer", "AI assistant is temporarily unavailable.",
                "citations", java.util.List.of(), "source", "fallback");
    }

    private Map<String, Object> parseMap(String raw) {
        try {
            return json.readValue(raw, new TypeReference<>() {});
        } catch (Exception e) {
            log.error("Failed to parse ai-service response", e);
            return Map.of("error", "parse_failure");
        }
    }
}
