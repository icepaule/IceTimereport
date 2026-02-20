# Overtime Report Generator (ArbZG-Compliant)

Automatisierte Arbeitszeitnachweise aus [Solidtime](https://www.solidtime.io/) mit ArbZG-Compliance-Prüfung.

## Was macht dieses Tool?

Dieses Tool liest Zeiteinträge aus einer lokalen Solidtime-Installation (PostgreSQL-Datenbank) und erzeugt zwei Excel-Arbeitszeitnachweise:

| Version | Datei | Zweck |
|---------|-------|-------|
| **Real** | `Arbeitszeitnachweis_YYYY_real.xlsx` | Echte Stunden + ArbZG-Verstoß-Spalte (privat) |
| **Büro** | `Arbeitszeitnachweis_YYYY.xlsx` | Korrigierte Stunden, ArbZG-konform (für Vorgesetzte) |

### ArbZG-Prüfungen

| § | Regel | Prüfung |
|---|-------|---------|
| §3 | Max. 10 Stunden pro Tag | Tägliche Arbeitszeit |
| §3 | Durchschnitt ≤ 8h über 24 Wochen | Gleitender Durchschnitt |
| §4 | Pause: 30 min > 6h, 45 min > 9h | Lücken zwischen Einträgen |
| §5 | Ruhezeit ≥ 11 Stunden | Ende Tag N → Start Tag N+1 |
| §9 | Keine Sonn-/Feiertagsarbeit | Datumsprüfung |

### Korrektur-Algorithmus (Büro-Version)

- Wochenend-/Feiertagsstunden → auf nächsten Werktag verschoben
- Max. 10h/Tag, Überschuss → Carry-Over auf Folgetage
- Fiktive Start-/End-/Pausenzeiten (Start 08:00)
- Bezahlte Abwesenheit (Urlaub/Krank/Gleittag) → Ist = Soll = hours_per_day
- **Gesamtstunden bleiben erhalten** (nur Verteilung ändert sich)

Siehe [Berechnungslogik](docs/CALCULATIONS.md) für eine detaillierte Erklärung aller Formeln.

## Features

- Automatische Feiertagsberechnung für alle 16 Bundesländer
- Erkennung von Urlaub/Krankheit/Gleittagen aus Projekt-Namen
- Urlaubs- und Überstundenkonto
- Monatliche E-Mail mit Zusammenfassung + Excel-Anhang
- Google Drive Sync via rclone
- Täglicher Cron-Job für automatische Generierung

## Schnellstart

Siehe [Benutzerhandbuch](docs/USER.md) für die vollständige Anleitung.

```bash
# 1. Repository klonen
git clone https://github.com/your-org/overtime-report.git
cd overtime-report

# 2. Konfiguration anpassen
cp .env.example .env
nano .env  # Member-ID, Client-ID, E-Mail etc. eintragen

# 3. Container bauen und starten
docker compose up -d

# 4. Manuell generieren (Test)
docker exec overtime-report python3 /app/main.py generate --year 2025

# 5. Ergebnis prüfen
ls -la output/real/ output/office/
```

## Voraussetzungen

- Docker + Docker Compose
- Laufende [Solidtime](https://www.solidtime.io/)-Installation (Docker)
- Beide Container im selben Docker-Netzwerk

## Dokumentation

| Dokument | Inhalt |
|----------|--------|
| [Benutzerhandbuch](docs/USER.md) | Tägliche Nutzung, Konfiguration, FAQ |
| [Berechnungslogik](docs/CALCULATIONS.md) | Detaillierte Erklärung aller Formeln und Algorithmen |
| [Administratorhandbuch](docs/ADMIN.md) | Installation, Solidtime-Setup, E-Mail, rclone, Troubleshooting |

## Projektstruktur

```
overtime-report/
├── Dockerfile              # Python 3.11 + psycopg2 + openpyxl + rclone
├── docker-compose.yml      # Container-Definition
├── requirements.txt        # Python-Abhängigkeiten
├── .env.example            # Konfigurations-Template
├── .env                    # Lokale Konfiguration (git-ignored)
├── rclone.conf             # Google Drive Konfiguration (git-ignored)
├── entrypoint.sh           # Container-Startskript
├── crontab                 # Scheduling-Konfiguration
├── app/
│   ├── main.py             # CLI: generate / send-email / check
│   ├── db.py               # PostgreSQL-Abfragen (Solidtime)
│   ├── holidays.py         # Deutsche Feiertage (alle Bundesländer)
│   ├── azg.py              # ArbZG Verstoß-Erkennung + Korrektur
│   ├── excel_real.py       # Reale Version (+ ArbZG-Spalte)
│   ├── excel_office.py     # Büro-Version (korrigiert)
│   └── mailer.py           # E-Mail-Versand (SMTP)
├── output/                 # Generierte Excel-Dateien (git-ignored)
│   ├── real/               # Private Version
│   └── office/             # Büro-Version
└── docs/
    ├── USER.md             # Benutzerhandbuch
    ├── CALCULATIONS.md     # Berechnungslogik (Formeln, Algorithmen, Beispiele)
    └── ADMIN.md            # Administratorhandbuch
```

## Lizenz

MIT
