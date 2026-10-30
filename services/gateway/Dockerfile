# Runtime-only image for CommuteIQ Gateway.
# Requires the jar to be built locally first (via `make build-gateway`).
FROM eclipse-temurin:21-jre
WORKDIR /app

RUN groupadd -r commuteiq && useradd -r -g commuteiq -s /sbin/nologin commuteiq

COPY target/gateway-*.jar app.jar
RUN chown commuteiq:commuteiq app.jar

USER commuteiq

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=5s --retries=12 --start-period=30s \
    CMD java -version || exit 1

ENTRYPOINT ["java", \
    "-XX:+UseContainerSupport", \
    "-XX:MaxRAMPercentage=75.0", \
    "-jar", "app.jar"]
