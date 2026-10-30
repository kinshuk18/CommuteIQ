package com.commuteiq.gateway.repository;

import com.commuteiq.gateway.entity.SavedCommute;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface SavedCommuteRepository extends JpaRepository<SavedCommute, Long> {

    List<SavedCommute> findByUserIdOrderByCreatedAtDesc(String userId);
}
