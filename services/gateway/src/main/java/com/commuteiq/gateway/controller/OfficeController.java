package com.commuteiq.gateway.controller;

import com.commuteiq.gateway.entity.Office;
import com.commuteiq.gateway.repository.OfficeRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.NotBlank;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/offices")
@Tag(name = "Offices", description = "Tech-park office lookup")
@Validated
public class OfficeController {

    private final OfficeRepository repo;

    public OfficeController(OfficeRepository repo) { this.repo = repo; }

    @GetMapping
    @Operation(summary = "Search offices by name prefix")
    public ResponseEntity<List<Office>> search(@RequestParam @NotBlank String q) {
        return ResponseEntity.ok(repo.searchByName(q.trim()));
    }

    @GetMapping("/{id}")
    public ResponseEntity<Office> getOne(@PathVariable Long id) {
        return repo.findById(id).map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }
}
