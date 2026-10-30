package com.commuteiq.gateway.graphql;

import com.commuteiq.gateway.entity.SavedCommute;
import com.commuteiq.gateway.entity.Stop;
import com.commuteiq.gateway.repository.SavedCommuteRepository;
import com.commuteiq.gateway.repository.StopRepository;
import org.springframework.graphql.data.method.annotation.Argument;
import org.springframework.graphql.data.method.annotation.MutationMapping;
import org.springframework.graphql.data.method.annotation.QueryMapping;
import org.springframework.stereotype.Controller;

import java.util.List;
import java.util.Map;

/**
 * GraphQL resolvers.
 * Spring for GraphQL maps query/mutation names to @QueryMapping/@MutationMapping.
 */
@Controller
public class CommuteGraphQLController {

    private final StopRepository stopRepo;
    private final SavedCommuteRepository savedRepo;

    public CommuteGraphQLController(StopRepository stopRepo,
                                    SavedCommuteRepository savedRepo) {
        this.stopRepo  = stopRepo;
        this.savedRepo = savedRepo;
    }

    @QueryMapping
    public List<Stop> stopsNearby(
            @Argument Double lat,
            @Argument Double lon,
            @Argument Double radiusKm,
            @Argument Integer limit) {
        double r = radiusKm != null ? radiusKm : 1.0;
        int    l = limit    != null ? limit    : 20;
        double delta = r / 111.0;
        return stopRepo.findNearby(lat, lon, r, delta, l);
    }

    @QueryMapping
    public Map<String, Object> route(@Argument String id) {
        // Aggregate stop count for this route from the stop_times join
        List<Object[]> rows = stopRepo.popularRoutesByStopCount(500);
        for (Object[] row : rows) {
            if (id.equals(row[0])) {
                return Map.of("routeId", row[0], "stopCount", ((Number) row[1]).intValue());
            }
        }
        return null;
    }

    @QueryMapping
    public List<SavedCommute> savedCommutes(@Argument String userId) {
        return savedRepo.findByUserIdOrderByCreatedAtDesc(userId);
    }

    @MutationMapping
    public SavedCommute saveCommute(
            @Argument String userId,
            @Argument String originStopId,
            @Argument String destStopId,
            @Argument String label) {
        SavedCommute sc = new SavedCommute();
        sc.setUserId(userId);
        sc.setOriginStopId(originStopId);
        sc.setDestStopId(destStopId);
        sc.setLabel(label);
        return savedRepo.save(sc);
    }
}
