package com.commuteiq.gateway.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** Request body for POST /api/v1/assistant/ask */
public record AskRequest(
        @NotBlank @Size(max = 2000) String query,
        @Size(max = 128) String userId
) {}
