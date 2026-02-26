# Administratorhandbuch

## Inhaltsverzeichnis

1. [Voraussetzungen](#voraussetzungen)
2. [Solidtime installieren](#solidtime-installieren)
3. [Overtime Report installieren](#overtime-report-installieren)
4. [Netzwerk-Konfiguration](#netzwerk-konfiguration)
5. [Member-ID und Client-ID ermitteln](#member-id-und-client-id-ermitteln)
6. [E-Mail einrichten (Gmail)](#e-mail-einrichten-gmail)
7. [Google Drive Sync (rclone)](#google-drive-sync-rclone)
8. [Erster Testlauf](#erster-testlauf)
9. [Produktivbetrieb](#produktivbetrieb)
10. [Troubleshooting](#troubleshooting)
11. [Updates](#updates)

---

## Voraussetzungen

| Komponente | Version | Hinweis |
|-----------|---------|---------|
| Docker | ≥ 20.10 | `docker --version` |
| Docker Compose | ≥ 2.0 | `docker compose version` |
| Solidtime | beliebig | Muss als Docker-Container laufen |
| Git | beliebig | Zum Klonen des Repos |

### Systemanforderungen

- Linux/macOS/Windows (mit Docker Desktop)
- ~100 MB Speicher für den Container
- Netzwerkzugang zur Solidtime-Datenbank (Docker-Netzwerk)
- Optional: Gmail-Konto mit App-Passwort für E-Mail-Versand
- Optional: Google-Konto für Drive-Sync

---

## Solidtime installieren

Falls du noch keine Solidtime-Installation hast:

### 1. Repository klonen

```bash
mkdir -p /opt/docker/solidtime
cd /opt/docker/solidtime
```

### 2. docker-compose.yml erstellen

```yaml
services:
  app:
    image: solidtime/solidtime:latest
    ports:
      - "8080:80"
    env_file: .env
    volumes:
      - app-storage:/var/www/html/storage
    depends_on:
      database:
        condition: service_healthy
    networks:
      - internal

  database:
    image: postgres:15
    environment:
      POSTGRES_DB: solidtime
      POSTGRES_USER: solidtime
      POSTGRES_PASSWORD: solidtime
    volumes:
      - db:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U solidtime"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - internal

  scheduler:
    image: solidtime/solidtime:latest
    command: php artisan schedule:work
    env_file: .env
    depends_on:
      database:
        condition: service_healthy
    networks:
      - internal

  queue:
    image: solidtime/solidtime:latest
    command: php artisan queue:work
    env_file: .env
    depends_on:
      database:
        condition: service_healthy
    networks:
      - internal

volumes:
  app-storage:
  db:

networks:
  internal:
    name: solidtime_internal
```

### 3. Umgebungsvariablen (.env)

Erstelle eine `.env` im Solidtime-Verzeichnis. Siehe [Solidtime Dokumentation](https://docs.solidtime.io/) für Details.

### 4. Starten

```bash
docker compose up -d
```

### 5. Verifizieren

```bash
# Container laufen?
docker ps | grep solidtime

# Datenbank erreichbar?
docker exec solidtime-database-1 psql -U solidtime -d solidtime -c "SELECT 1"

# Webinterface öffnen
# http://localhost:8080
```

---

## Overtime Report installieren

### 1. Repository klonen

```bash
cd /opt/docker  # oder dein bevorzugtes Verzeichnis
git clone https://github.com/your-org/overtime-report.git
cd overtime-report
```

### 2. Konfiguration erstellen

```bash
cp .env.example .env
```

Bearbeite die `.env`-Datei:

```bash
nano .env
```

**Mindestens diese Werte anpassen:**

```env
# Solidtime-Datenbank (Container-Name als Host)
DB_HOST=solidtime-database-1

# Deine Member-ID (siehe nächster Abschnitt)
MEMBER_ID=deine-uuid-hier

# Persönliche Daten
EMPLOYEE_NAME=Dein Name
HOURS_PER_WEEK=39
STATE=BY
```

### 3. Docker-Netzwerk prüfen

Das Overtime-Report-Tool muss im selben Docker-Netzwerk wie Solidtime sein:

```bash
# Solidtime-Netzwerk finden
docker network ls | grep solidtime
```

Passe ggf. den Netzwerknamen in `docker-compose.yml` an:

```yaml
networks:
  solidtime_internal:    # ← muss zum Solidtime-Netzwerk passen
    external: true
```

### 4. Container bauen und starten

```bash
docker compose up -d --build
```

---

## Netzwerk-Konfiguration

### Standard-Setup (gleicher Host)

Wenn Solidtime und Overtime Report auf dem gleichen Host laufen:

```
┌─────────────────────────────────────────────────────┐
│                Docker Host                           │
│                                                      │
│  ┌──────────────┐     ┌───────────────────┐         │
│  │  solidtime-  │     │  overtime-report   │         │
│  │  database-1  │◄────│                    │         │
│  │  (postgres)  │     │  (python + cron)   │         │
│  └──────────────┘     └───────────────────┘         │
│         │                      │                     │
│         └──────────┬───────────┘                     │
│              solidtime_internal                      │
└─────────────────────────────────────────────────────┘
```

Beide Container teilen sich das Netzwerk `solidtime_internal`. Der DB_HOST ist der Container-Name (`solidtime-database-1`).

### Externer Zugriff

Falls die Solidtime-DB auf einem anderen Host läuft oder der Port exponiert ist:

```env
DB_HOST=192.168.1.100
DB_PORT=5432
```

In diesem Fall brauchst du kein gemeinsames Docker-Netzwerk. Entferne den `networks`-Block aus `docker-compose.yml`:

```yaml
services:
  overtime-report:
    # ... (alles wie gehabt, aber ohne networks)
    network_mode: bridge
```

---

## Member-ID und Client-ID ermitteln

### Member-ID finden

Jeder Solidtime-Benutzer hat eine oder mehrere Member-IDs (eine pro Organisation):

```bash
docker exec solidtime-database-1 psql -U solidtime -d solidtime \
  -c "SELECT m.id as member_id, u.name, u.email
      FROM members m
      JOIN users u ON m.user_id = u.id"
```

Ausgabe:
```
              member_id               |    name     |      email
--------------------------------------+-------------+------------------
 xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx | Max Muster  | max@example.com
```

Trage deine `member_id` als `MEMBER_ID` in die `.env` ein.

### Client-IDs finden (optional)

Das Tool wertet standardmäßig alle Zeiteinträge des Members aus. Über Client-IDs können bestimmte Kunden ausgeschlossen werden:

```bash
docker exec solidtime-database-1 psql -U solidtime -d solidtime \
  -c "SELECT id, name FROM clients"
```

Ausgabe:
```
                  id                  |    name
--------------------------------------+----------
 f0b38ad4-0de8-... | Arbeitgeber
 c854e48e-7c0b-... | THW
 a1b2c3d4-5e6f-... | Privat
```

#### EXCLUDE_CLIENTS

Komma-getrennte Client-IDs, die komplett aus der Berechnung ausgeschlossen werden (z.B. private Nebenprojekte):

```env
EXCLUDE_CLIENTS=a1b2c3d4-5e6f-...
```

Mehrere IDs mit Komma trennen:

```env
EXCLUDE_CLIENTS=uuid-1,uuid-2,uuid-3
```

#### THW_CLIENT_ID

Client-ID für ehrenamtliche/freiwillige Arbeit (z.B. THW). **Wochenend-Einträge** dieses Clients werden ausgeschlossen (private Freiwilligenarbeit), **Werktags-Einträge** zählen normal (Freistellung durch den Arbeitgeber):

```env
THW_CLIENT_ID=c854e48e-7c0b-...
```

#### Zusammenfassung Filterverhalten

| Szenario | Ergebnis |
|----------|----------|
| Kein `EXCLUDE_CLIENTS`, kein `THW_CLIENT_ID` | Alle Einträge zählen |
| `EXCLUDE_CLIENTS` gesetzt | Diese Clients komplett ausgeschlossen |
| `THW_CLIENT_ID` gesetzt | Nur Wochenend-Einträge dieses Clients ausgeschlossen |
| Einträge ohne Client | Zählen immer |

### Projekte anzeigen

Prüfe welche Projekte für deine Zeiteinträge existieren:

```bash
docker exec solidtime-database-1 psql -U solidtime -d solidtime \
  -c "SELECT DISTINCT p.name
      FROM projects p
      JOIN time_entries te ON te.project_id = p.id
      WHERE te.member_id = 'DEINE-MEMBER-ID'
      ORDER BY p.name"
```

**Wichtig für die automatische Erkennung:** Das Tool erkennt Urlaub/Krankheit/Gleittage automatisch, wenn die Solidtime-Projektnamen diese Wörter enthalten:
- `Urlaub` → Urlaubstag
- `Krank` → Krankheitstag
- `Gleittag` oder `Gleitzeit` → Gleittag

---

## E-Mail einrichten (Gmail)

### 1. Gmail App-Passwort erstellen

1. Gehe zu [Google Konto → Sicherheit](https://myaccount.google.com/security)
2. Aktiviere **2-Faktor-Authentifizierung** (falls noch nicht aktiv)
3. Gehe zu [App-Passwörter](https://myaccount.google.com/apppasswords)
4. Erstelle ein neues App-Passwort für "Mail" / "Andere (benutzerdefiniert)"
5. Kopiere das 16-stellige Passwort

### 2. In .env eintragen

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=deine-email@gmail.com
SMTP_PASS=xxxx-xxxx-xxxx-xxxx    # App-Passwort (nicht dein normales Passwort!)
MAIL_FROM=deine-email@gmail.com
MAIL_TO=chef@firma.de
MAIL_CC=kopie@example.com         # Optional, mehrere mit Komma trennen
```

### 3. Testen

```bash
docker exec overtime-report python3 /app/main.py send-email --test
```

Die Test-Mail geht nur an `SMTP_USER` (dich selbst), nicht an den Chef.

### Andere SMTP-Anbieter

Das Tool funktioniert mit jedem SMTP-Server:

```env
# Outlook/Office 365
SMTP_HOST=smtp.office365.com
SMTP_PORT=587

# Eigener Mailserver
SMTP_HOST=mail.example.com
SMTP_PORT=465
```

---

## Google Drive Sync (rclone)

### 1. rclone auf dem Host konfigurieren

```bash
# rclone installieren (falls nötig)
curl https://rclone.org/install.sh | bash

# Interaktiv konfigurieren
rclone config
# → n (new remote)
# → Name: gdrive
# → Storage: drive (Google Drive)
# → Folge den Anweisungen für OAuth
```

### 2. Konfiguration in den Container kopieren

```bash
cp ~/.config/rclone/rclone.conf /opt/docker/overtime-report/rclone.conf
```

### 3. In .env konfigurieren

```env
RCLONE_REMOTE=gdrive                  # Name des rclone-Remotes
RCLONE_PATH=Arbeitszeitnachweis        # Ordner in Google Drive
```

### 4. Testen

```bash
# Im Container
docker exec overtime-report rclone ls gdrive:Arbeitszeitnachweis

# Manuell synchronisieren
docker exec overtime-report rclone copy /output/office gdrive:Arbeitszeitnachweis
```

### Ohne Google Drive

Wenn du kein Google Drive brauchst, ignoriere einfach die `RCLONE_*`-Variablen und erstelle eine leere `rclone.conf`. Die rclone-Cron-Jobs schlagen dann fehl, haben aber keinen Einfluss auf die Report-Generierung.

---

## Erster Testlauf

### 1. Container-Status prüfen

```bash
docker compose ps
docker compose logs
```

### 2. Datenbankverbindung testen

```bash
docker exec overtime-report python3 -c "
import db
entries = db.fetch_entries(
    __import__('datetime').date(2024,1,1),
    __import__('datetime').date(2024,1,31)
)
print(f'{len(entries)} Einträge im Januar 2024')
"
```

### 3. Reports generieren

```bash
# Alle Jahre seit START_DATE generieren (mit kumulativem Übertrag)
docker exec overtime-report python3 /app/main.py generate

# Oder ein bestimmtes Jahr (Vorjahre werden für den Übertrag berechnet)
docker exec overtime-report python3 /app/main.py generate --year 2025
```

### 4. Ergebnis prüfen

```bash
ls -la output/real/ output/office/
```

Öffne die Excel-Dateien und prüfe:
- **Real:** Stimmen die Stunden mit Solidtime überein?
- **Real:** Werden Verstöße korrekt markiert?
- **Office:** Ist kein Tag > 10h?
- **Office:** Gibt es keine Wochenend-/Feiertagsarbeit?
- Sind die Monats- und Jahressummen plausibel?

### 5. ArbZG-Check

```bash
docker exec overtime-report python3 /app/main.py check --year 2024
```

### 6. Test-E-Mail (optional)

```bash
docker exec overtime-report python3 /app/main.py send-email --test
```

---

## Produktivbetrieb

Nach erfolgreichem Test läuft der Container automatisch mit Cron:

| Job | Zeit | Aktion |
|-----|------|--------|
| Report generieren | Täglich 06:00 | Beide Excel-Dateien aktualisiert |
| Google Drive Sync | Täglich 06:05 | Büro-Version hochgeladen |
| Monats-E-Mail | 1. des Monats 07:00 | Vormonat per Mail an Chef |

### Logs überwachen

```bash
# Aktuelle Logs
docker exec overtime-report cat /var/log/overtime-report.log

# Live-Logs
docker exec overtime-report tail -f /var/log/overtime-report.log
```

### Container neustarten

```bash
docker compose restart
```

### Container aktualisieren

```bash
git pull
docker compose up -d --build
```

---

## Troubleshooting

### Container startet nicht

```bash
docker compose logs overtime-report
```

Häufige Ursachen:
- Netzwerk `solidtime_internal` existiert nicht
- `.env`-Datei fehlt oder hat Syntaxfehler

### "Connection refused" zur Datenbank

```bash
# Ist die DB erreichbar?
docker exec overtime-report python3 -c "import db; db.get_connection()"

# Netzwerk prüfen
docker network inspect solidtime_internal

# Container im Netzwerk?
docker inspect overtime-report --format '{{range $net,$conf := .NetworkSettings.Networks}}{{$net}} {{end}}'
```

**Lösung:** Stelle sicher, dass beide Container im Netzwerk `solidtime_internal` sind.

### "Member not found" / Keine Einträge

```bash
# Einträge für den Member prüfen
docker exec solidtime-database-1 psql -U solidtime -d solidtime \
  -c "SELECT count(*) FROM time_entries WHERE member_id = 'DEINE-ID'"
```

**Lösung:** Prüfe ob `MEMBER_ID` korrekt ist. Prüfe auch `EXCLUDE_CLIENTS` und `THW_CLIENT_ID` — falsche IDs könnten relevante Einträge versehentlich ausschließen.

### Excel-Dateien leer

- Prüfe den Datumsbereich: `--year` korrekt?
- Gibt es Einträge ohne End-Zeitpunkt (`end IS NULL`)?
- Läuft noch ein Timer in Solidtime?

### E-Mail-Versand schlägt fehl

```
Email error: (535, b'5.7.8 Username and Password not accepted')
```

**Lösung:** Verwende ein [Gmail App-Passwort](https://myaccount.google.com/apppasswords), nicht dein normales Passwort. 2FA muss aktiviert sein.

### rclone "Failed to create file system"

**Lösung:** rclone.conf im Container prüfen:

```bash
docker exec overtime-report cat /root/.config/rclone/rclone.conf
docker exec overtime-report rclone listremotes
```

### Feiertage stimmen nicht

Prüfe ob `STATE` in der `.env` korrekt ist. Beispiel für Bayern:

```bash
docker exec overtime-report python3 -c "
from holidays import get_holidays
for d, name in sorted(get_holidays(2025, 'BY').items()):
    print(f'{d}: {name}')
"
```

---

## Updates

### Neue Version installieren

```bash
cd /opt/docker/overtime-report
git pull
docker compose up -d --build
```

Deine `.env` und `output/`-Dateien bleiben erhalten (git-ignored).

### Eigene Anpassungen

Falls du den Code anpassen willst:

| Datei | Beschreibung |
|-------|-------------|
| `app/holidays.py` | Feiertage hinzufügen/ändern |
| `app/azg.py` | Korrektur-Algorithmus anpassen |
| `app/excel_real.py` | Layout der realen Version |
| `app/excel_office.py` | Layout der Büro-Version |
| `app/mailer.py` | E-Mail-Template |
| `crontab` | Scheduling ändern |
