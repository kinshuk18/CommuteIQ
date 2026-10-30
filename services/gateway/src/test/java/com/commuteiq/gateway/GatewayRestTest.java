package com.commuteiq.gateway;

import com.commuteiq.gateway.dto.AskRequest;
import com.commuteiq.gateway.dto.FeedbackRequest;
import com.commuteiq.gateway.dto.PlanRequest;
import com.commuteiq.gateway.service.AiProxyService;
import com.commuteiq.gateway.service.InsightService;
import com.commuteiq.gateway.service.PlanService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * MockMvc tests for REST controllers.
 * All external deps (DB, Redis, Kafka, ai-service) are mocked.
 */
@SpringBootTest(properties = {
        "spring.datasource.url=jdbc:h2:mem:testdb;MODE=PostgreSQL;DB_CLOSE_DELAY=-1",
        "spring.datasource.driver-class-name=org.h2.Driver",
        "spring.datasource.username=sa",
        "spring.datasource.password=",
        "spring.jpa.hibernate.ddl-auto=create-drop",
        "spring.flyway.enabled=false",
        "spring.data.redis.host=localhost",
        "spring.data.redis.port=6370",  // non-existent — rate limit fails open
        "management.health.redis.enabled=false",
        "spring.kafka.producer.properties.max.block.ms=500",
        "kafka.enabled=false",
        "ai-service.base-url=http://localhost:19999"
})
@AutoConfigureMockMvc
class GatewayRestTest {

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;

    @MockBean PlanService planService;
    @MockBean AiProxyService aiProxy;
    @MockBean InsightService insightService;

    @Test
    void healthEndpoint() throws Exception {
        mvc.perform(get("/actuator/health"))
                .andExpect(status().isOk());
    }

    @Test
    void planValidationRejectsEmptyBody() throws Exception {
        mvc.perform(post("/api/v1/plan")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void planReturnsOkWithMockedService() throws Exception {
        var resp = new com.commuteiq.gateway.dto.PlanResponse(
                "S1", "S2", 25, 3.2, List.of("S1 → S2"), Map.of(), false);
        when(planService.plan(any())).thenReturn(resp);

        mvc.perform(post("/api/v1/plan")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(new PlanRequest("S1", "S2", null, 9))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.estimatedMinutes").value(25));
    }

    @Test
    void assistantAskReturnsOk() throws Exception {
        when(aiProxy.ask(anyString(), any()))
                .thenReturn(Map.of("answer", "Metro fare is Rs 10-60.", "citations", List.of()));

        mvc.perform(post("/api/v1/assistant/ask")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(new AskRequest("Metro fare?", "u1"))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.answer").exists());
    }

    @Test
    void feedbackAccepted() throws Exception {
        mvc.perform(post("/api/v1/feedback")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(
                                new FeedbackRequest("plan-1", "u1", 5, "Great!"))))
                .andExpect(status().isAccepted());
    }

    @Test
    void insightsPopular() throws Exception {
        when(insightService.popularRoutes(anyInt())).thenReturn(List.of(
                Map.of("route", "S1:S2", "requests", 42L)));

        mvc.perform(get("/api/v1/insights/popular"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].route").value("S1:S2"));
    }
}
