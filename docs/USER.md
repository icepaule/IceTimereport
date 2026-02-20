# Benutzerhandbuch

## Inhaltsverzeichnis

1. [Überblick](#überblick)
2. [Konfiguration](#konfiguration)
3. [Befehle](#befehle)
4. [Excel-Berichte](#excel-berichte)
5. [Automatisierung](#automatisierung)
6. [FAQ](#faq)

> Detaillierte Erklärung aller Formeln und Algorithmen: [Berechnungslogik](CALCULATIONS.md)

---

## Überblick

Der Overtime Report Generator liest deine Zeiterfassung aus Solidtime und erstellt zwei Excel-Arbeitszeitnachweise:

- **Reale Version** (`Arbeitszeitnachweis_YYYY_real.xlsx`): Deine tatsächlichen Arbeitszeiten mit einer Spalte, die ArbZG-Verstöße markiert. Nur für dich.
- **Büro-Version** (`Arbeitszeitnachweis_YYYY.xlsx`): ArbZG-konforme Version mit korrigierten Zeiten. Für den Vorgesetzten.

### Wie funktioniert die Korrektur?

Die Büro-Version verschiebt Stunden so, dass keine ArbZG-Verstöße mehr sichtbar sind:

| Problem | Korrektur |
|---------|-----------|
| Sonntags-/Feiertagsarbeit | Stunden → nächster Werktag |
| Mehr als 10h an einem Tag | Überschuss → nächster Werktag |
| Fehlende Pausen | Fiktive Pausenzeiten eingefügt |

**Wichtig:** Die Gesamtstundenzahl bleibt gleich! Es wird nichts gelöscht, nur die Verteilung über die Tage geändert.

---

## Konfiguration

Alle Einstellungen stehen in der Datei `.env`. Kopiere `.env.example` und passe die Werte an:

```bash
cp .env.example .env
nano .env
```

### Pflichtfelder

| Variable | Beschreibung | Beispiel |
|----------|-------------|---------|
| `DB_HOST` | Solidtime DB Hostname/Container | `solidtime-database-1` |
| `DB_PORT` | PostgreSQL Port | `5432` |
| `DB_NAME` | Datenbankname | `solidtime` |
| `DB_USER` | DB Benutzer | `solidtime` |
| `DB_PASS` | DB Passwort | `solidtime` |
| `MEMBER_ID` | Deine Member-UUID aus Solidtime | `820cff5d-...` |
| `EMPLOYEE_NAME` | Dein Name (für Excel-Header) | `Max Mustermann` |
| `HOURS_PER_WEEK` | Vertragliche Wochenstunden | `39` |
| `STATE` | Bundesland (für Feiertage) | `BY` |

### Member-ID herausfinden

```bash
docker exec solidtime-database-1 psql -U solidtime -d solidtime \
  -c "SELECT m.id, u.name, u.email FROM members m JOIN users u ON m.user_id = u.id"
```

### Client-ID herausfinden (optional)

Wenn du nur Einträge eines bestimmten Kunden/Arbeitgebers auswerten willst:

```bash
docker exec solidtime-database-1 psql -U solidtime -d solidtime \
  -c "SELECT id, name FROM clients"
```

Trage die gewünschte Client-ID als `MHB_CLIENT_ID` ein. Leer lassen = alle Kunden.

### Optionale Felder

| Variable | Beschreibung | Standard |
|----------|-------------|---------|
| `MHB_CLIENT_ID` | Filter nach Client | (leer = alle) |
| `EMPLOYEE_ROLE` | Funktion/Rolle | (leer) |
| `VACATION_DAYS` | Urlaubstage pro Jahr | `30` |
| `START_DATE` | Beginn der Erfassung | `2024-01-01` |
| `SMTP_*` | E-Mail-Konfiguration | (siehe ADMIN.md) |
| `RCLONE_*` | Google Drive Sync | (siehe ADMIN.md) |

### Bundesländer

| Kürzel | Land | Kürzel | Land |
|--------|------|--------|------|
| BW | Baden-Württemberg | NI | Niedersachsen |
| BY | Bayern | NW | Nordrhein-Westfalen |
| BE | Berlin | RP | Rheinland-Pfalz |
| BB | Brandenburg | SL | Saarland |
| HB | Bremen | SN | Sachsen |
| HH | Hamburg | ST | Sachsen-Anhalt |
| HE | Hessen | SH | Schleswig-Holstein |
| MV | Mecklenburg-Vorpommern | TH | Thüringen |

---

## Befehle

Alle Befehle werden im Container ausgeführt:

```bash
docker exec overtime-report python3 /app/main.py <befehl> [optionen]
```

### `generate` - Berichte erstellen

Erzeugt beide Excel-Dateien (real + office) für ein ganzes Jahr:

```bash
# Aktuelles Jahr
docker exec overtime-report python3 /app/main.py generate

# Bestimmtes Jahr
docker exec overtime-report python3 /app/main.py generate --year 2024
```

Ausgabe:
```
Generating reports for 2025 (State: BY)...
Checking ArbZG compliance...
  12 days with violations (15 total violations)
Generating real report...
  -> /output/real/Arbeitszeitnachweis_2025_real.xlsx
Applying ArbZG corrections for office version...
  Original: 2048.5h -> Corrected: 2048.5h (delta: 0.0h)
Generating office report...
  -> /output/office/Arbeitszeitnachweis_2025.xlsx
Done.
```

Die Dateien liegen danach unter:
- `./output/real/Arbeitszeitnachweis_YYYY_real.xlsx`
- `./output/office/Arbeitszeitnachweis_YYYY.xlsx`

### `check` - ArbZG-Compliance prüfen

Zeigt alle ArbZG-Verstöße ohne Excel zu generieren:

```bash
docker exec overtime-report python3 /app/main.py check --year 2025
```

Ausgabe:
```
ArbZG Check for 2025 (Marcus Pauli):
============================================================
  26.04.2025 (11.1h): §3 >10h (11.1h)
  25.06.2025 (23.3h): §3 >10h (23.3h), §5 Ruhezeit (3.2h < 11h)
  ...

Summary (12 days with violations):
  §3 >10h: 8x
  §4 Pause: 3x
  §5 Ruhezeit: 2x
  §9 Sonntag: 2x
```

### `send-email` - Monats-E-Mail senden

Sendet den Arbeitszeitnachweis per E-Mail:

```bash
# Vormonat automatisch
docker exec overtime-report python3 /app/main.py send-email

# Bestimmter Monat
docker exec overtime-report python3 /app/main.py send-email --year 2025 --month 6

# Test-Mail (an sich selbst)
docker exec overtime-report python3 /app/main.py send-email --test
```

---

## Excel-Berichte

### Reale Version (Arbeitszeitnachweis_YYYY_real.xlsx)

Ein Sheet pro Monat + Zusammenfassungs-Sheet.

**Spalten:**

| Spalte | Inhalt |
|--------|--------|
| Datum | TT.MM.JJJJ |
| Tag | Mo, Di, Mi, ... |
| Typ | Arbeit, Urlaub, Krank, Gleittag, Feiertag, Samstag, Sonntag |
| Projekt | Solidtime-Projektname(n) |
| Beschreibung | Solidtime-Beschreibung(en) |
| Ist (h) | Tatsächliche Stunden |
| Soll (h) | Vertragliche Stunden |
| ArbZG | OK / §3 >10h / §4 Pause / §5 Ruhezeit / §9 Sonntag |

**Farbcodierung:**
- Rot: ArbZG-Verstoß
- Grau: Wochenende/Feiertag
- Gelb: Urlaub/Krank/Gleittag

### Büro-Version (Arbeitszeitnachweis_YYYY.xlsx)

Ein Sheet pro Monat + Zusammenfassungs-Sheet mit Urlaubskonto.

**Spalten:**

| Spalte | Inhalt |
|--------|--------|
| Datum | TT.MM.JJJJ |
| Tag | Mo, Di, Mi, ... |
| Typ | Arbeit, Urlaub, Krank, Gleittag, Feiertag, Samstag, Sonntag |
| Beginn | Fiktive Startzeit (08:00) |
| Ende | Berechnete Endzeit |
| Pause (min) | 0/30/45 je nach Stunden |
| Ist (h) | Korrigierte Stunden (max 10h) |
| Soll (h) | Vertragliche Stunden |

**Keine** Projektnamen oder Beschreibungen in dieser Version.

### Zusammenfassungs-Sheet

Beide Versionen enthalten ein Zusammenfassungs-Sheet mit:
- Jahres-Ist- und Soll-Stunden
- Überstundenkonto
- Urlaubskonto (genommen / Restanspruch)
- Krankheitstage
- (Nur real) ArbZG-Verstoß-Statistik

---

## Automatisierung

Der Container führt automatisch folgende Cron-Jobs aus:

| Zeitpunkt | Aktion |
|-----------|--------|
| Täglich 06:00 | Berichte generieren |
| Täglich 06:05 | Büro-Version zu Google Drive synchronisieren |
| 1. jedes Monats 07:00 | Monats-E-Mail senden |

### Logs prüfen

```bash
docker exec overtime-report cat /var/log/overtime-report.log
```

### Cron anpassen

Bearbeite die Datei `crontab` und baue den Container neu:

```bash
nano crontab
docker compose up -d --build
```

---

## FAQ

### Warum unterscheiden sich die Monatssummen zwischen real und Büro?

Die **Jahressumme** ist identisch. Monatlich kann es Abweichungen geben, weil Wochenend-/Feiertagsstunden auf den nächsten Werktag verschoben werden - auch über Monatsgrenzen hinweg.

### Was passiert mit Urlaubs-/Krankheitstagen?

Das Tool erkennt automatisch Solidtime-Projekte mit den Namen "Urlaub", "Krank" oder "Gleittag" und markiert die Tage entsprechend. Für diese Tage gilt: **Ist = Soll = hours_per_day** (z.B. 7,8h bei einer 39h-Woche). Damit haben Krankheits- und Urlaubstage keinen Einfluss auf das Überstundenkonto — sie werden als bezahlte Abwesenheit (Entgeltfortzahlung) behandelt.

In der Büro-Version werden dafür fiktive Arbeitszeiten generiert (z.B. 08:00–15:48 bei 7,8h).

Siehe [Berechnungslogik](CALCULATIONS.md) für Details und Beispielrechnungen.

### Kann ich mehrere Jahre generieren?

Ja, führe den Befehl für jedes Jahr einzeln aus:

```bash
docker exec overtime-report python3 /app/main.py generate --year 2024
docker exec overtime-report python3 /app/main.py generate --year 2025
```

### Der Container findet die Solidtime-Datenbank nicht?

Beide Container müssen im selben Docker-Netzwerk sein. Prüfe:

```bash
docker network inspect solidtime_internal
```

Siehe [Administratorhandbuch](ADMIN.md#netzwerk-konfiguration) für Details.

### Wie genau sind die Pausenzeiten in der Büro-Version?

Die Pausenzeiten sind **fiktiv** und werden nach ArbZG-Mindestvorgaben berechnet:
- ≤ 6h: keine Pause
- 6-9h: 30 Minuten
- \> 9h: 45 Minuten

Die reale Version prüft deine tatsächlichen Pausen (Lücken zwischen Solidtime-Einträgen). Wenn du pro Tag nur **einen durchgehenden Eintrag** buchst, wird keine Pausenprüfung durchgeführt — denn ohne Lücken zwischen Einträgen ist eine Messung nicht möglich.
