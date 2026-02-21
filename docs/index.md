---
layout: default
title: Overtime Report Generator
---

# Overtime Report Generator (ArbZG-Compliant)

Automatisierte Arbeitszeitnachweise aus [Solidtime](https://www.solidtime.io/) mit ArbZG-Compliance-Prüfung.

## Dokumentation

- [Berechnungslogik](CALCULATIONS.md) — Detaillierte Erklärung aller Formeln, Algorithmen und Beispielrechnungen
- [Benutzerhandbuch](USER.md) — Tägliche Nutzung, Konfiguration, FAQ
- [Administratorhandbuch](ADMIN.md) — Installation, Solidtime-Setup, E-Mail, rclone, Troubleshooting

## ArbZG-Prüfungen

Der Report wird automatisch auf Konformität mit dem Arbeitszeitgesetz geprüft:

| Paragraph | Regel |
|-----------|-------|
| §3 ArbZG | Tägliche Arbeitszeit max. 10 Stunden |
| §3 ArbZG | Durchschnittliche Arbeitszeit ≤ 8 Stunden über 24 Wochen |
| §4 ArbZG | Ruhepausen: 30 min ab 6h, 45 min ab 9h |
| §5 ArbZG | Ruhezeit zwischen Arbeitstagen ≥ 11 Stunden |
| §9 ArbZG | Sonn- und Feiertagsruhe |

---

[Quellcode auf GitHub](https://github.com/icepaule/IceTimereport)
