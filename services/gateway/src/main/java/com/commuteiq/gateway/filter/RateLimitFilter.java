package com.commuteiq.gateway.filter;

import com.commuteiq.gateway.exception.RateLimitException;
import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ClassPathResource;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.scripting.support.ResourceScriptSource;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;

/**
 * Token-bucket rate limiter backed by a Redis Lua script.
 * Key is per-IP (or X-User-Id header if present); 120 req/60 s default.
 */
@Component
public class RateLimitFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(RateLimitFilter.class);

    private final StringRedisTemplate redis;
    private final DefaultRedisScript<Long> script;
    private final int capacity;
    private final int windowSeconds;

    public RateLimitFilter(
            StringRedisTemplate redis,
            @Value("${rate-limit.capacity:120}") int capacity,
            @Value("${rate-limit.window-seconds:60}") int windowSeconds) {
        this.redis = redis;
        this.capacity = capacity;
        this.windowSeconds = windowSeconds;

        DefaultRedisScript<Long> s = new DefaultRedisScript<>();
        s.setScriptSource(new ResourceScriptSource(
                new ClassPathResource("lua/token_bucket.lua")));
        s.setResultType(Long.class);
        this.script = s;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain chain)
            throws ServletException, IOException {

        // Skip actuator and health endpoints from rate limiting
        String path = request.getRequestURI();
        if (path.startsWith("/actuator") || path.startsWith("/health")) {
            chain.doFilter(request, response);
            return;
        }

        String clientId = getClientId(request);
        String key = "rl:" + clientId;

        try {
            Long allowed = redis.execute(script,
                    List.of(key),
                    String.valueOf(capacity),
                    String.valueOf(windowSeconds));

            if (allowed == null || allowed == 0L) {
                log.warn("Rate limit exceeded for client {}", clientId);
                response.setStatus(429);
                response.setContentType("application/json");
                response.getWriter().write(
                        "{\"status\":429,\"title\":\"Rate Limit Exceeded\","
                        + "\"detail\":\"Too many requests. Retry after " + windowSeconds + "s.\"}");
                return;
            }
        } catch (Exception e) {
            // Redis unavailable → fail-open (do not block legitimate traffic)
            log.warn("Redis rate limit check failed, failing open: {}", e.getMessage());
        }

        chain.doFilter(request, response);
    }

    private String getClientId(HttpServletRequest req) {
        String userId = req.getHeader("X-User-Id");
        if (userId != null && !userId.isBlank()) return "user:" + userId;
        String ip = req.getHeader("X-Forwarded-For");
        return "ip:" + (ip != null ? ip.split(",")[0].trim() : req.getRemoteAddr());
    }
}
