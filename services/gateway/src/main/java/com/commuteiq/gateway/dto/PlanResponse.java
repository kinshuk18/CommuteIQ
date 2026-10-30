package com.commuteiq.gateway.dto;

import java.util.List;
import java.util.Map;

/** Response body for POST /api/v1/plan */
public record PlanResponse(
        String originStopId,
        String destStopId,
        Integer estimatedMinutes,
        Double distanceKm,
        List<String> segments,
        Map<String, Object> mlPrediction,
        boolean fromCache
) {}
