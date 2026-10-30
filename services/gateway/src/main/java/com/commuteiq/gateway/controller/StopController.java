package com.commuteiq.gateway.controller;

import com.commuteiq.gateway.entity.Stop;
import com.commuteiq.gateway.repository.StopRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/stops")
@Tag(name = "Stops", description = "BMTC/BMRCL stop lookup and proximity search")
@Validated
public class StopController {

    private final StopRepository repo;

    public StopController(StopRepository repo) { this.repo = repo; }

    @GetMapping
    @Operation(summary = "Search stops by name prefix")
    public ResponseEntity<List<Stop>> search(
            @RequestParam @NotBlank String q) {
        return ResponseEntity.ok(repo.searchByName(q.trim()));
    }

    @GetMapping("/nearby")
    @Operation(summary = "Find stops within radius (Haversine, bbox pre-filter)")
    public ResponseEntity<List<Stop>> nearby(
            @RequestParam double lat,
            @RequestParam double lon,
            @RequestParam(defaultValue = "1.0") @Min(0) @Max(20) double radiusKm,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int limit) {
        // bbox delta in degrees ≈ radiusKm / 111 km/degree
        double delta = radiusKm / 111.0;
        return ResponseEntity.ok(repo.findNearby(lat, lon, radiusKm, delta, limit));
    }

    @GetMapping("/{stopId}")
    @Operation(summary = "Get a single stop by ID")
    public ResponseEntity<Stop> getOne(@PathVariable String stopId) {
        return repo.findById(stopId)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }
}
