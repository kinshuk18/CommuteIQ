package com.commuteiq.gateway.exception;

import java.time.Instant;

/**
 * RFC 7807 Problem Details JSON body.
 * Returned by GlobalExceptionHandler for all error responses.
 */
public record ProblemResponse(
        String type,
        String title,
        int status,
        String detail,
        Instant timestamp
) {
    public static ProblemResponse of(int status, String title, String detail) {
        return new ProblemResponse(
                "about:blank", title, status, detail, Instant.now());
    }
}
