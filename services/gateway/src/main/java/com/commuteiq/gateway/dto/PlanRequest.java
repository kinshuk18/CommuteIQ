package com.commuteiq.gateway.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** Request body for POST /api/v1/plan */
public record PlanRequest(
        @NotBlank String originStopId,
        @NotBlank String destStopId,
        @Size(max = 128) String userId,
        Integer hour  // 0-23; null → current hour
) {}
