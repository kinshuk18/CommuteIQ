package com.commuteiq.gateway.config;

import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import io.github.resilience4j.reactor.circuitbreaker.operator.CircuitBreakerOperator;
import io.github.resilience4j.reactor.retry.RetryOperator;
import io.github.resilience4j.reactor.timelimiter.TimeLimiterOperator;
import io.github.resilience4j.retry.RetryRegistry;
import io.github.resilience4j.timelimiter.TimeLimiterRegistry;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.WebClient;

/**
 * Builds the WebClient used to call the ai-service, pre-wired with:
 * - shared-secret header injected on every request
 * - Resilience4j circuit breaker + retry + time limiter applied at call site
 *   (operators applied in AiProxyService, not here, for per-call flexibility)
 */
@Configuration
public class WebClientConfig {

    @Value("${ai-service.base-url:http://localhost:8001}")
    private String aiBaseUrl;

    @Value("${ai-service.shared-secret:changeme-dev-secret}")
    private String sharedSecret;

    @Bean
    public WebClient aiWebClient(WebClient.Builder builder) {
        return builder
                .baseUrl(aiBaseUrl)
                .defaultHeader("X-Internal-Secret", sharedSecret)
                .codecs(c -> c.defaultCodecs().maxInMemorySize(2 * 1024 * 1024))
                .build();
    }
}
