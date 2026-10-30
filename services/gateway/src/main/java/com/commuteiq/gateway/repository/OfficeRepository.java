package com.commuteiq.gateway.repository;

import com.commuteiq.gateway.entity.Office;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface OfficeRepository extends JpaRepository<Office, Long> {

    @Query("SELECT o FROM Office o WHERE LOWER(o.name) LIKE LOWER(CONCAT(:q, '%')) ORDER BY o.name")
    List<Office> searchByName(@Param("q") String q);
}
