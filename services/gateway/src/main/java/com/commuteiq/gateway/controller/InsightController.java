package com.commuteiq.gateway.controller;

import com.commuteiq.gateway.service.InsightService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/insights")
@Tag(name = "Insights", description = "Aggregated usage data (Redis ZSET + Postgres aggregate)")
public class InsightController {

    private final InsightService svc;

    public InsightController(InsightService svc) { this.svc = svc; }

    @GetMapping("/popular")
    @Operation(summary = "Top routes by request count (Redis) + stop density (Postgres)")
    public ResponseEntity<List<Map<String, Object>>> popular(
            @RequestParam(defaultValue = "10") int limit) {
        return ResponseEntity.ok(svc.popularRoutes(Math.min(limit, 50)));
    }
}
