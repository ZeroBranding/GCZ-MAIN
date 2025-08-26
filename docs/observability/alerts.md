# Beispiel-Alerts für Prometheus

Dieses Dokument enthält Beispiel-Alerting-Regeln in PromQL, die auf den in diesem Projekt exponierten Metriken basieren. Diese Regeln können in einer Prometheus-Konfiguration verwendet werden, um das System proaktiv zu überwachen.

## 1. Hohe Fehlerrate bei Workflow-Schritten (Step Failure Rate)

Dieser Alert wird ausgelöst, wenn die Rate der fehlgeschlagenen Schritte für einen bestimmten Schritttyp in den letzten 5 Minuten einen Schwellenwert (z.B. 25%) überschreitet. Dies kann auf ein Problem mit einem bestimmten Tool oder einer externen API hinweisen.

**PromQL-Ausdruck:**

```promql
# Triggers if the 5-minute failure rate for any step is above 25%
sum(rate(engine_step_errors_total[5m])) by (step_name) / sum(rate(engine_step_duration_ms_count[5m])) by (step_name) > 0.25
```

**Annotations & Labels:**

```yaml
- alert: HighStepFailureRate
  expr: sum(rate(engine_step_errors_total[5m])) by (step_name) / sum(rate(engine_step_duration_ms_count[5m])) by (step_name) > 0.25
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Hohe Fehlerrate für Schritt '{{ $labels.step_name }}'"
    description: "Der Workflow-Schritt '{{ $labels.step_name }}' hat eine Fehlerrate von {{ $value | humanizePercentage }} in den letzten 5 Minuten."
```

## 2. Hohe Latenz bei einem Workflow-Schritt (High Step Latency)

Dieser Alert wird ausgelöst, wenn die 95. Perzentil-Latenz für einen bestimmten Schritt über einen längeren Zeitraum (z.B. 10 Minuten) einen hohen Schwellenwert (z.B. 15 Sekunden) überschreitet. Dies hilft, Leistungsengpässe zu identifizieren.

**PromQL-Ausdruck:**

```promql
# Triggers if the 95th percentile latency for any step is over 15 seconds
histogram_quantile(0.95, sum(rate(engine_step_duration_ms_bucket[10m])) by (le, step_name)) > 15000
```

**Annotations & Labels:**

```yaml
- alert: HighStepLatency
  expr: histogram_quantile(0.95, sum(rate(engine_step_duration_ms_bucket[10m])) by (le, step_name)) > 15000
  for: 10m
  labels:
    severity: critical
  annotations:
    summary: "Hohe Latenz für Schritt '{{ $labels.step_name }}'"
    description: "Die 95. Perzentil-Latenz für den Schritt '{{ $labels.step_name }}' liegt bei über {{ $value | humanize }}ms."
```

## 3. Hohe Latenz bei der gesamten Graph-Sitzung (High Graph Session Latency)

Dieser Alert wird ausgelöst, wenn die durchschnittliche Dauer einer gesamten Graph-Sitzung über einen längeren Zeitraum einen Schwellenwert überschreitet.

**PromQL-Ausdruck:**

```promql
# Triggers if the average session duration over the last 15 minutes is over 45 seconds
rate(graph_session_duration_ms_sum[15m]) / rate(graph_session_duration_ms_count[15m]) > 45000
```

**Annotations & Labels:**

```yaml
- alert: HighGraphSessionLatency
  expr: rate(graph_session_duration_ms_sum[15m]) / rate(graph_session_duration_ms_count[15m]) > 45000
  for: 15m
  labels:
    severity: warning
  annotations:
    summary: "Hohe durchschnittliche Sitzungsdauer"
    description: "Die durchschnittliche Dauer einer Graph-Sitzung liegt bei über {{ $value | humanize }}ms."
```
