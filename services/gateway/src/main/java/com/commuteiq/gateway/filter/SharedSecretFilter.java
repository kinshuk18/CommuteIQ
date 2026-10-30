package com.commuteiq.gateway.filter;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * Validates the X-Internal-Secret header on requests from the gateway to the
 * ai-service. When this filter runs inside the gateway it adds the header on
 * outbound WebClient calls (see AiProxyService). The corresponding check lives
 * in the ai service's middleware.
 *
 * This filter also validates the incoming shared secret on any path under
 * /internal/** so service-to-service calls within the compose network are
 * authenticated without a full JWT stack.
 */
@Component
public class SharedSecretFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(SharedSecretFilter.class);

    @Value("${ai-service.shared-secret:changeme-dev-secret}")
    private String sharedSecret;

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain chain)
            throws ServletException, IOException {

        String path = request.getRequestURI();
        if (path.startsWith("/internal/")) {
            String secret = request.getHeader("X-Internal-Secret");
            if (!sharedSecret.equals(secret)) {
                log.warn("Rejected /internal request with bad secret from {}", request.getRemoteAddr());
                response.setStatus(403);
                response.setContentType("application/json");
                response.getWriter().write("{\"status\":403,\"title\":\"Forbidden\","
                        + "\"detail\":\"Missing or invalid internal secret\"}");
                return;
            }
        }
        chain.doFilter(request, response);
    }
}
