# Berechnungslogik

Dieses Dokument erklärt im Detail, wie die Überstunden, Abwesenheiten und ArbZG-Korrekturen berechnet werden.

## Inhaltsverzeichnis

1. [Grundbegriffe](#grundbegriffe)
2. [Tagestyp-Erkennung](#tagestyp-erkennung)
3. [Überstundenberechnung](#überstundenberechnung)
4. [ArbZG-Verstöße](#arbzg-verstöße)
5. [Korrektur-Algorithmus (Büro-Version)](#korrektur-algorithmus-büro-version)
6. [Monats-E-Mail und kumulative Überstunden](#monats-e-mail-und-kumulative-überstunden)
7. [Beispielrechnungen](#beispielrechnungen)

---

## Grundbegriffe

| Begriff | Bedeutung |
|---------|-----------|
| **Ist-Stunden** | Tatsächlich gearbeitete/gutgeschriebene Stunden |
| **Soll-Stunden** | Vertragliche Stunden (z.B. 7,8h bei 39h-Woche) |
| **hours_per_day** | `HOURS_PER_WEEK / 5` (z.B. 39 / 5 = 7,8h) |
| **Carry-Over** | Stundenübertrag von einem Tag auf den nächsten Werktag |
| **Abwesenheitstypen** | Urlaub, Krank, Gleittag |

---

## Tagestyp-Erkennung

Jeder Tag wird anhand der Solidtime-Projektname automatisch klassifiziert:

```
Solidtime-Projekt enthält...    →  Tagestyp
────────────────────────────────────────────
"urlaub"  (Groß-/Kleinschreibung egal)  →  Urlaub
"krank"                                 →  Krank
"gleittag" oder "gleitzeit"             →  Gleittag
Wochenende (Sa/So)                      →  Samstag/Sonntag
Feiertag (bundeslandabhängig)           →  Feiertag
Alles andere                            →  Arbeit
```

**Reihenfolge ist wichtig:** Wenn ein Solidtime-Eintrag auf "Urlaub" steht, wird der Tag als Urlaub erkannt — selbst wenn er auf ein Wochenende fällt.

---

## Überstundenberechnung

Die zentrale Formel:

```
Überstunden = Σ Ist-Stunden − Σ Soll-Stunden
```

### Wie Ist- und Soll-Stunden pro Tag berechnet werden

| Tagestyp | Ist-Stunden | Soll-Stunden | Netto-Effekt auf Überstunden |
|----------|-------------|-------------|------------------------------|
| **Arbeit** (mit Einträgen) | Tatsächliche Arbeitszeit | hours_per_day | Positiv bei Mehrarbeit, negativ bei Minderarbeit |
| **Arbeit** (leer, Vergangenheit) | 0 | hours_per_day | **-hours_per_day** (Überstundenabbau) |
| **Urlaub** | hours_per_day | hours_per_day | Kein Effekt (bezahlte Abwesenheit) |
| **Krank** | hours_per_day | hours_per_day | Kein Effekt (Entgeltfortzahlung) |
| **Gleittag** | 0 | hours_per_day | **-hours_per_day** (Überstundenabbau) |
| **Wochenende** | Tatsächliche Arbeitszeit | 0 | Vollständig als Überstunden |
| **Feiertag** | Tatsächliche Arbeitszeit | 0 | Vollständig als Überstunden |

### Erklärung der einzelnen Typen

**Arbeitstage mit Einträgen:**
Einfachster Fall — die Differenz zwischen tatsächlicher Arbeitszeit und Soll bestimmt, ob Überstunden aufgebaut (+) oder abgebaut (-) werden.

**Leere Werktage (keine Solidtime-Einträge):**
Ein vergangener Werktag ohne Einträge gilt als Überstundenabbau (Brückentag, Gleitzeitabbau). Das Soll (hours_per_day) wird gezählt, Ist = 0. Dadurch sinkt das Überstundenkonto um hours_per_day pro Tag.

**Urlaub / Krank:**
Bezahlte Abwesenheit — es wird so gerechnet, als hätte man einen normalen Arbeitstag absolviert (Ist = Soll = hours_per_day). Das Überstundenkonto bleibt unverändert.

**Gleittag:**
Überstundenabbau — der Tag wird explizit in Solidtime als Gleittag gebucht. Ist = 0, Soll = hours_per_day. Das Überstundenkonto sinkt um hours_per_day.

**Wochenende und Feiertage:**
Hier ist Soll = 0 (man muss nicht arbeiten). Jede gearbeitete Stunde geht daher 1:1 als Überstunde ins Konto.

---

## ArbZG-Verstöße

Das Tool prüft folgende Regeln des Arbeitszeitgesetzes:

### §3 — Max. 10 Stunden pro Tag

```
Wenn actual_hours > 10 → Verstoß
```

Einfacher Grenzwert-Check. Die 10h-Grenze gilt als absolutes Maximum.

### §3 — 24-Wochen-Durchschnitt ≤ 8 Stunden

```
Fenster: 120 Werktage (= 24 Wochen × 5 Arbeitstage)
Berechnung: Gleitender Durchschnitt über 120 aufeinanderfolgende Arbeitstage
Wenn Durchschnitt > 8h → Verstoß (markiert am letzten Tag des Fensters)
```

Nur geprüft, wenn genügend Daten vorliegen (≥ 120 Arbeitstage). Wochenenden und Feiertage sind ausgeschlossen.

### §4 — Pausenpflicht

```
Wenn actual_hours > 6 UND mehrere Einträge vorhanden:
  Pflichtpause = 45 min (bei >9h) oder 30 min (bei >6h)
  Gemessene Pause = Summe aller Lücken zwischen aufeinanderfolgenden Einträgen
  Wenn gemessene Pause < Pflichtpause → Verstoß
```

**Wichtig:** Die Pausenprüfung erfolgt nur bei Tagen mit **mindestens 2 Solidtime-Einträgen**, da bei einem einzelnen durchgehenden Eintrag keine Lücke messbar ist. Das bedeutet nicht, dass keine Pause gemacht wurde — sie ist nur nicht separat gebucht.

### §5 — Ruhezeit ≥ 11 Stunden

```
rest = Startzeit(Tag N) − Endzeit(Tag N-1)
Wenn rest < 11h → Verstoß
```

Vergleicht das späteste Arbeitsende eines Tages mit dem frühesten Arbeitsbeginn des Folgetags.

### §9 — Sonn- und Feiertagsruhe

```
Wenn Arbeitszeit > 0 an einem Sonntag → Verstoß
Wenn Arbeitszeit > 0 an einem Feiertag → Verstoß
```

Feiertage werden bundeslandabhängig berechnet (Konfiguration: `STATE`).

---

## Korrektur-Algorithmus (Büro-Version)

Die Büro-Version verschiebt Stunden so, dass keine ArbZG-Verstöße sichtbar sind. Die **Gesamtstundenzahl bleibt erhalten** — es ändert sich nur die Verteilung.

### Ablauf (Vorwärts-Durchlauf)

```
carry_over = 0

Für jeden Tag im Jahr (1. Jan → heute):
  ┌─ Urlaub/Krank/Gleittag?
  │    → Ist = hours_per_day, Zeiten = fiktiv (08:00-15:48 bei 7,8h)
  │
  ├─ Wochenende/Feiertag?
  │    → carry_over += actual_hours
  │    → Ist = 0 (Stunden werden verschoben)
  │
  └─ Normaler Arbeitstag:
       total = actual_hours + carry_over
       Wenn total > 10:
         → Ist = 10
         → carry_over = total - 10
       Sonst:
         → Ist = total
         → carry_over = 0
```

### Restverteilung (Rückwärts-Durchlauf)

Falls nach dem letzten Tag noch `carry_over > 0` übrig ist:

```
Für jeden Tag RÜCKWÄRTS:
  Wenn Arbeitstag UND Ist > 0 UND Ist < 10:
    Platz = 10 - Ist
    Auffüllung = min(Platz, carry_over)
    Ist += Auffüllung
    carry_over -= Auffüllung
```

### Fiktive Zeiten

Für jeden Tag mit Ist-Stunden > 0 werden plausible Zeiten generiert:

```
Beginn: immer 08:00
Pause:
  > 9h → 45 min
  > 6h → 30 min
  ≤ 6h → keine
Ende: 08:00 + (Ist × 60 min) + Pausenminuten
```

**Beispiele:**

| Ist-Stunden | Pause | Ende |
|-------------|-------|------|
| 4,0h | 0 min | 12:00 |
| 7,8h | 30 min | 16:18 |
| 8,0h | 30 min | 16:30 |
| 9,5h | 45 min | 18:15 |
| 10,0h | 45 min | 18:45 |

### Carry-Over über Monatsgrenzen

Stunden können über Monatsgrenzen hinweg verschoben werden. Beispiel:

```
Fr 31. Jan:  12h gearbeitet → 10h (Ist) + 2h carry_over
Sa  1. Feb:  (Wochenende)
So  2. Feb:  (Wochenende)
Mo  3. Feb:  6h gearbeitet → 6h + 2h carry_over = 8h (Ist)
```

Das führt dazu, dass die **Monatssummen** in der Büro-Version von den echten Monatssummen abweichen können. Die **Jahressumme** bleibt aber identisch.

---

## Monats-E-Mail und kumulative Überstunden

Die monatliche E-Mail enthält eine kumulative Überstundenberechnung seit `START_DATE` (Vertragsstart).

### Berechnung

```
Für jedes Jahr von START_DATE.year bis aktuelles Jahr:
  Für jeden Tag bis einschließlich Zielmonat:
    → Tagestyp bestimmen (siehe oben)
    → Ist und Soll addieren (Regeln wie in der Tabelle oben)

Gesamtüberstunden = Σ Ist − Σ Soll
```

### Monatliche Statistiken

Zusätzlich berechnet die E-Mail die Monatsstatistiken aus der **korrigierten** Büro-Version:

```
Monats-Ist  = Summe corrected_hours aller Tage im Monat
Monats-Soll = Anzahl Werktage × hours_per_day
```

### E-Mail-Zusammenfassung

Die E-Mail enthält:
- Monats-Ist und Monats-Soll
- Kumulative Überstunden seit Vertragsstart
- Resturlaub (Anspruch − genommene Tage im laufenden Jahr)

---

## Beispielrechnungen

### Beispiel 1: Normale Arbeitswoche (39h-Vertrag)

```
Mo: 8,5h gearbeitet  →  Ist: 8,5h  Soll: 7,8h  Diff: +0,7h
Di: 7,0h gearbeitet  →  Ist: 7,0h  Soll: 7,8h  Diff: -0,8h
Mi: 9,0h gearbeitet  →  Ist: 9,0h  Soll: 7,8h  Diff: +1,2h
Do: 7,8h gearbeitet  →  Ist: 7,8h  Soll: 7,8h  Diff:  0,0h
Fr: 6,5h gearbeitet  →  Ist: 6,5h  Soll: 7,8h  Diff: -1,3h
────────────────────────────────────────────────────────────
Woche:                    Ist: 38,8h Soll: 39,0h Diff: -0,2h
```

### Beispiel 2: Woche mit Krankheit

```
Mo: 7,8h gearbeitet  →  Ist: 7,8h  Soll: 7,8h  Diff:  0,0h
Di: Krank             →  Ist: 7,8h  Soll: 7,8h  Diff:  0,0h
Mi: Krank             →  Ist: 7,8h  Soll: 7,8h  Diff:  0,0h
Do: 8,5h gearbeitet  →  Ist: 8,5h  Soll: 7,8h  Diff: +0,7h
Fr: 7,0h gearbeitet  →  Ist: 7,0h  Soll: 7,8h  Diff: -0,8h
────────────────────────────────────────────────────────────
Woche:                    Ist: 38,9h Soll: 39,0h Diff: -0,1h
```

Krankheitstage haben keinen Einfluss auf das Überstundenkonto.

### Beispiel 3: Wochenendarbeit mit Carry-Over

```
                        Real          →   Büro-Version
Fr: 10h gearbeitet   →  Ist: 10h         Ist: 10h
Sa:  4h gearbeitet   →  Ist:  4h         Ist:  0h (→ 4h carry)
So:  2h gearbeitet   →  Ist:  2h         Ist:  0h (→ 6h carry)
Mo:  8h gearbeitet   →  Ist:  8h         Ist: 10h (8h + 2h carry, Rest: 4h carry)
Di:  7h gearbeitet   →  Ist:  7h         Ist: 10h (7h + 3h carry, Rest: 1h carry)
Mi:  6h gearbeitet   →  Ist:  6h         Ist:  7h (6h + 1h carry)
────────────────────────────────────────────────────────────
Gesamt:                  Ist: 37h         Ist: 37h  ✓ (gleich)
```

### Beispiel 4: Leerer Werktag / Gleittag (Überstundenabbau)

```
Mo: 9,0h gearbeitet  →  Ist: 9,0h  Soll: 7,8h  Diff: +1,2h
Di: 8,5h gearbeitet  →  Ist: 8,5h  Soll: 7,8h  Diff: +0,7h
Mi: (leer, kein Eintrag) →  Ist: 0,0h  Soll: 7,8h  Diff: -7,8h
Do: 8,0h gearbeitet  →  Ist: 8,0h  Soll: 7,8h  Diff: +0,2h
Fr: 7,5h gearbeitet  →  Ist: 7,5h  Soll: 7,8h  Diff: -0,3h
────────────────────────────────────────────────────────────
Woche:                    Ist: 33,0h Soll: 39,0h Diff: -6,0h
```

Der leere Mittwoch (z.B. Brückentag) erzeugt einen Soll-Abzug von 7,8h.
Das Überstundenkonto sinkt entsprechend. Gleiches gilt für Gleittage.
