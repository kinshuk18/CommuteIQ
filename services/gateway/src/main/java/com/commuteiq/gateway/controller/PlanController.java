package com.commuteiq.gateway.controller;

import com.commuteiq.gateway.dto.PlanRequest;
import com.commuteiq.gateway.dto.PlanResponse;
import com.commuteiq.gateway.service.PlanService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/plan")
@Tag(name = "Plan", description = "Commute planning with ML-predicted runtime")
public class PlanController {

    private final PlanService svc;

    public PlanController(PlanService svc) { this.svc = svc; }

    @PostMapping
    @Operation(summary = "Plan a commute; Redis-cached by origin:dest:hour")
    public ResponseEntity<PlanResponse> plan(@RequestBody @Valid PlanRequest req) {
        return ResponseEntity.ok(svc.plan(req));
    }
}
