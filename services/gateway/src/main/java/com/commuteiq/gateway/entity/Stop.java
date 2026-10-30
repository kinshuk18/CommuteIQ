package com.commuteiq.gateway.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;

/**
 * Maps the `stops` table loaded by Flyway V2 from BMTC/BMRCL GTFS data.
 * DDL is owned by Flyway; Hibernate is validate-only.
 */
@Entity
@Table(name = "stops")
public class Stop {

    @Id
    @Column(name = "stop_id", length = 64)
    private String stopId;

    @Column(name = "stop_name", nullable = false)
    private String stopName;

    @Column(name = "stop_lat", precision = 9, scale = 6)
    private BigDecimal stopLat;

    @Column(name = "stop_lon", precision = 9, scale = 6)
    private BigDecimal stopLon;

    @Column(name = "wheelchair_boarding")
    private Integer wheelchairBoarding;

    // --- accessors ---

    public String getStopId() { return stopId; }
    public String getStopName() { return stopName; }
    public BigDecimal getStopLat() { return stopLat; }
    public BigDecimal getStopLon() { return stopLon; }
    public Integer getWheelchairBoarding() { return wheelchairBoarding; }
}
