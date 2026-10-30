# Multi-stage build for the Spring Boot gateway.
# Stage 1: build with Maven; Stage 2: minimal JRE runtime (non-root).

# ── Build stage ────────────────────────────────────────────────────────────────
FROM eclipse-temurin:21-jdk AS build
WORKDIR /build

# Cache Maven dependencies before copying source
COPY pom.xml mvnw ./
COPY .mvn .mvn
RUN ./mvnw -q dependency:go-offline

COPY src src
RUN ./mvnw -q -DskipTests package

# ── Runtime stage ──────────────────────────────────────────────────────────────
FROM eclipse-temurin:21-jre AS runtime
WORKDIR /app

# Create a non-root user
RUN groupadd -r commuteiq && useradd -r -g commuteiq -s /sbin/nologin commuteiq

COPY --from=build /build/target/gateway-*.jar app.jar
RUN chown commuteiq:commuteiq app.jar

USER commuteiq

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=5s --retries=12 --start-period=40s \
    CMD curl -sf http://localhost:8080/actuator/health || exit 1

ENTRYPOINT ["java", \
    "-XX:+UseContainerSupport", \
    "-XX:MaxRAMPercentage=75.0", \
    "-jar", "app.jar"]
