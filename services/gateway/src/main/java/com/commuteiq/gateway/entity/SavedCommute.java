package com.commuteiq.gateway.entity;

import jakarta.persistence.*;
import java.time.Instant;

/** User-saved commute plans, stored for the GraphQL `savedCommutes` query. */
@Entity
@Table(name = "saved_commutes")
public class SavedCommute {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false, length = 128)
    private String userId;

    @Column(name = "origin_stop_id", length = 64)
    private String originStopId;

    @Column(name = "dest_stop_id", length = 64)
    private String destStopId;

    @Column(name = "label", length = 255)
    private String label;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();

    // --- accessors ---

    public Long getId() { return id; }
    public String getUserId() { return userId; }
    public String getOriginStopId() { return originStopId; }
    public String getDestStopId() { return destStopId; }
    public String getLabel() { return label; }
    public Instant getCreatedAt() { return createdAt; }

    public void setUserId(String userId) { this.userId = userId; }
    public void setOriginStopId(String originStopId) { this.originStopId = originStopId; }
    public void setDestStopId(String destStopId) { this.destStopId = destStopId; }
    public void setLabel(String label) { this.label = label; }
}
