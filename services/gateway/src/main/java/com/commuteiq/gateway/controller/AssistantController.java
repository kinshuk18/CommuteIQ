package com.commuteiq.gateway.controller;

import com.commuteiq.gateway.dto.AskRequest;
import com.commuteiq.gateway.service.AiProxyService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/assistant")
@Tag(name = "Assistant", description = "RAG-backed commute assistant with trust-tier citations")
public class AssistantController {

    private final AiProxyService aiProxy;

    public AssistantController(AiProxyService aiProxy) { this.aiProxy = aiProxy; }

    @PostMapping("/ask")
    @Operation(summary = "Ask the LangGraph RAG assistant; returns answer + citations")
    public ResponseEntity<Map<String, Object>> ask(@RequestBody @Valid AskRequest req) {
        Map<String, Object> resp = aiProxy.ask(req.query(), req.userId());
        return ResponseEntity.ok(resp);
    }
}
