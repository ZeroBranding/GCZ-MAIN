### Agents SLA/SLO für LangGraph-Orchestrierung

Diese Seite definiert Betriebsrichtlinien, SLOs/SLA, monatliche Error Budgets und Release-Gates für die LangGraph-Orchestrierung (Control-Plane, Worker/Executors, Queue-Backend, Checkpoint-Store).

- Scope: Prod-Umgebung für interaktive und Batch-Agents.
- Messung: Über Prometheus/OpenTelemetry Metriken und Queue/Store Telemetrie.
- Reporting: Wöchentliches Review, monatlicher Budgetabschluss.


### SLI/SLO-Ziele

Die folgenden SLOs gelten pro Monat und sind auf Minutenbasis (rollierend) zu messen, sofern nicht anders angegeben.

| SLI | Definition | Ziel (p95) | Ziel (p99) | Messfenster |
| --- | --- | --- | --- | --- |
| node_latency | Dauer eines einzelnen Graph-Node-Schritts (ohne externe Wartezeiten, falls getrennt instrumentiert) | ≤ 1.5 s | ≤ 5 s | 5m-Rates / Histogramme |
| success_rate | Anteil erfolgreicher Node-Ausführungen (success/total) | ≥ 99.5% | n/a | 5m-Rates, monatlich aggregiert |
| resume_time | Zeit bis Wiederaufnahme eines pausierten/abgebrochenen Runs (Scheduling bis erster Schritt) | ≤ 60 s | ≤ 180 s | 5m-Rates / Histogramme |
| queue_depth | Maximale Backlog-Zeit oder -Tiefe je Queue | backlog_seconds ≤ 300 s ODER depth ≤ 10,000 | n/a | 1m Gültigkeitsprüfung, 99% der Minuten |

Hinweise:
- Für node_latency werden Histogramme bevorzugt. Externe LLM- oder API-Latenzen sollten, wenn möglich, gesondert ausgewiesen werden.
- Für queue_depth ist die bevorzugte Metrik backlog_seconds (geschätzte Zeit bis Abarbeitung bei aktueller Verarbeitungsrate). Alternativ gilt eine Tiefen-Obergrenze.


### Error Budgets (monatlich) und Policy

- Primäres SLO für Budget: success_rate ≥ 99.5%/Monat
  - 30-Tage-Monat: 43,200 min → Budget 0.5% = 216 min Fehlzeit/Fehlerbudget
  - 31-Tage-Monat: 44,640 min → Budget 0.5% = 223.2 min
- Budget-Verbrauch (Burn) Definition: 1 − success_rate über Zeit, gewichtet nach Traffic.

Burn-Alerts (SRE Multi-Window Policy):
- Fast Burn (P1): ≥ 2% des Monatsbudgets in 1 Stunde verbraucht (≈ 4.32 min in 60 min)
  - Aktion: Sofortige Traffic-Drosselung oder Degradation, On-Call Eskalation, Incident eröffnen
- Slow Burn (P2): ≥ 5% des Monatsbudgets in 6 Stunden verbraucht (≈ 10.8 min in 360 min)
  - Aktion: Fehlerbudget-Review, Hotfix/Feature-Flag, verstärkte Beobachtung

Release-Stop-Policy:
- Wenn verbleibendes Monatsbudget < 50%: Feature-Release einfrieren, nur Fixes zulassen
- Wenn verbleibendes Monatsbudget < 20%: Striktes Freeze, Load-Tests/Chaos abgeschaltet, Kapazitätsreserven erhöhen


### PromQL Referenzen (Beispiele)

Setze PROM_URL und ggf. env="prod".

- node_latency (p95/p99):
```bash
curl -sG "$PROM_URL/api/v1/query" \
  --data-urlencode 'query=histogram_quantile(0.95, sum by (le) (rate(langgraph_node_duration_seconds_bucket{env="prod"}[5m])))' | jq

curl -sG "$PROM_URL/api/v1/query" \
  --data-urlencode 'query=histogram_quantile(0.99, sum by (le) (rate(langgraph_node_duration_seconds_bucket{env="prod"}[5m])))' | jq
```

- success_rate:
```bash
curl -sG "$PROM_URL/api/v1/query" \
  --data-urlencode 'query=sum(rate(langgraph_node_completed_total{status="success",env="prod"}[5m])) / sum(rate(langgraph_node_completed_total{env="prod"}[5m]))' | jq
```

- resume_time (p95/p99):
```bash
curl -sG "$PROM_URL/api/v1/query" \
  --data-urlencode 'query=histogram_quantile(0.95, sum by (le) (rate(langgraph_resume_time_seconds_bucket{env="prod"}[5m])))' | jq

curl -sG "$PROM_URL/api/v1/query" \
  --data-urlencode 'query=histogram_quantile(0.99, sum by (le) (rate(langgraph_resume_time_seconds_bucket{env="prod"}[5m])))' | jq
```

- queue_depth / backlog_seconds (Beispiele nach Backend):
```bash
# Redis Streams (PENDING pro Consumer-Group)
curl -sG "$PROM_URL/api/v1/query" \
  --data-urlencode 'query=sum(redis_stream_pending_entries{stream=~"langgraph.*",env="prod"})' | jq

# Kafka Lag
auth_header="-H Authorization: Bearer $PROM_TOKEN" # falls benötigt
curl -sG "$PROM_URL/api/v1/query" $auth_header \
  --data-urlencode 'query=sum(kafka_consumergroup_group_lag{consumergroup=~"langgraph.*",env="prod"})' | jq

# SQS ApproximateNumberOfMessagesVisible
aws cloudwatch get-metric-statistics \
  --namespace AWS/SQS --metric-name ApproximateNumberOfMessagesVisible \
  --dimensions Name=QueueName,Value=$SQS_QUEUE_NAME \
  --statistics Average --period 60 \
  --start-time $(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ)
```


### SLA (äußerer Vertrag)

- Verfügbarkeit des Orchestrator-API-Endpunkts (HTTP 2xx/3xx): 99.9%/Monat
- Support-Reaktionszeit: P1 in ≤ 15 min, P2 in ≤ 1 h, P3 in ≤ 8 h
- Datenhaltungs-SLA (Checkpoints und Logs): RPO ≤ 15 min, RTO ≤ 60 min


### Release-Gates (Load-Test Kriterien)

Ein Release darf nur live gehen, wenn alle Kriterien gleichzeitig erfüllt sind:

- Performance unter Last:
  - Bei 1× erwarteter Peak-Last: node_latency p95 ≤ 1.5 s, p99 ≤ 5 s (stabil ≥ 30 min)
  - Bei 2× erwarteter Peak-Last: p95 ≤ 2.5 s, p99 ≤ 8 s, success_rate ≥ 99.5%
  - queue_backlog_seconds ≤ 300 s (p99 über 30 min Messung)
  - Error-Rate ≤ 0.2% (5m Rate) ohne Retry-Storms
- Ressourcen-Headroom:
  - CPU-Usage der Worker median < 70% (p95 < 85%), Memory p95 < 75% des Limits
  - GPU-Utilization: 50–85% Durchschnitt ohne Throttling/Thermal Capping
- Stabilität:
  - Keine DLQ-Anstiege > 10 Nachrichten/min (oder 0 bei SQS) während 30 min
  - 0 stuck nodes (keine "no progress > 5 min")

Beispiel-Befehle für Lasttest (HTTP Entry-Point der Orchestrierung anpassen):
```bash
# 1× Peak: 100 RPS für 30 min, 200 gleichzeitige Verbindungen
hey -z 30m -q 100 -c 200 -H "Authorization: Bearer $TOKEN" \
  -m POST -d '{"graph":"agent","input":"ping"}' https://orchestrator.example.com/runs

# 2× Peak: 200 RPS für 30 min
hey -z 30m -q 200 -c 400 -H "Authorization: Bearer $TOKEN" \
  -m POST -d '{"graph":"agent","input":"ping"}' https://orchestrator.example.com/runs

# Begleitende Metrikprüfung (PromQL via API)
curl -sG "$PROM_URL/api/v1/query" \
  --data-urlencode 'query=histogram_quantile(0.95, sum by (le) (rate(langgraph_node_duration_seconds_bucket{env="staging"}[5m])))' | jq
```

Ressourcenkontrolle während des Tests:
```bash
kubectl -n $NAMESPACE top pods | sort -k3 -nr | head -20
kubectl -n $NAMESPACE top nodes
kubectl -n $NAMESPACE get hpa
```

Queue/DLQ überwachen:
```bash
# Redis
redis-cli -u $REDIS_URL XLEN langgraph:queue
redis-cli -u $REDIS_URL XLEN langgraph:dlq

# Kafka
kafka-consumer-groups --bootstrap-server $KAFKA_BOOTSTRAP \
  --group langgraph-consumers --describe

# SQS
aws sqs get-queue-attributes --queue-url $SQS_QUEUE_URL \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible RedrivePolicy
```

Dokumentation der Ergebnisse (obligatorisch):
- Rohdaten (hey/k6), Prometheus Snapshots, Screenshots von Dashboards
- Entscheidung: Pass/Fail pro Gate mit Begründung
- Tickets/Tasks aus Auffälligkeiten