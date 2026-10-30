package com.commuteiq.gateway.controller;

import com.commuteiq.gateway.dto.FeedbackRequest;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/api/v1/feedback")
@Tag(name = "Feedback", description = "Submit commute rating/comment; published to Kafka")
public class FeedbackController {

    private static final Logger log = LoggerFactory.getLogger(FeedbackController.class);

    private final Optional<KafkaTemplate<String, String>> kafka;
    private final ObjectMapper json;

    public FeedbackController(Optional<KafkaTemplate<String, String>> kafka, ObjectMapper json) {
        this.kafka = kafka;
        this.json  = json;
    }

    @PostMapping
    @Operation(summary = "Submit feedback on a plan; published to commute.feedback Kafka topic")
    public ResponseEntity<Map<String, String>> submit(@RequestBody @Valid FeedbackRequest req) {
        kafka.ifPresent(t -> {
            try {
                t.send("commute.feedback", json.writeValueAsString(Map.of(
                        "planId", req.planId(),
                        "userId", req.userId(),
                        "rating", req.rating(),
                        "comment", req.comment() != null ? req.comment() : "")));
            } catch (Exception e) {
                log.warn("Kafka feedback publish failed: {}", e.getMessage());
            }
        });
        return ResponseEntity.accepted().body(Map.of("status", "accepted"));
    }
}
