package com.commuteiq.gateway.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** Request body for POST /api/v1/feedback */
public record FeedbackRequest(
        @NotBlank String planId,
        @NotBlank @Size(max = 128) String userId,
        int rating,            // 1-5
        @Size(max = 1000) String comment
) {}
