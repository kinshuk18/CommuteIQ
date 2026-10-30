package com.commuteiq.gateway.exception;

/** Thrown by RateLimitFilter when the Lua token bucket is exhausted. */
public class RateLimitException extends RuntimeException {
    public RateLimitException(String clientId) {
        super("Rate limit exceeded for client: " + clientId);
    }
}
