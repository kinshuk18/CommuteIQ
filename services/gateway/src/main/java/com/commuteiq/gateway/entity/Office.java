package com.commuteiq.gateway.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;

/** Maps the `offices` table (loaded from offices.json via Flyway V2). */
@Entity
@Table(name = "offices")
public class Office {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String name;

    @Column(nullable = false)
    private BigDecimal lat;

    @Column(nullable = false)
    private BigDecimal lon;

    private String area;
    private String pincode;

    public Long getId() { return id; }
    public String getName() { return name; }
    public BigDecimal getLat() { return lat; }
    public BigDecimal getLon() { return lon; }
    public String getArea() { return area; }
    public String getPincode() { return pincode; }
}
