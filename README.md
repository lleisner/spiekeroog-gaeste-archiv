# Spiekerooger Gästestatistik-Archiv

[![Archive guest statistics](https://github.com/lleisner/spiekeroog-gaeste-archiv/actions/workflows/archive.yml/badge.svg)](https://github.com/lleisner/spiekeroog-gaeste-archiv/actions/workflows/archive.yml)

`collect_spiekeroog.py` ruft einmal täglich die [öffentlich sichtbare
Gästestatistik](https://www.spiekeroog.de/buchung/file/codebehind/loadGaesteStatistik.php)
der Nordseebad Spiekeroog GmbH ab und speichert sowohl die unveränderte
HTML-Antwort als auch normalisierte CSV-Zeilen.

Das Projekt ist bewusst klein und benötigt außer Python keine zusätzlichen
Pakete. Es ist ein unabhängiges Community-Projekt und nicht mit der
Nordseebad Spiekeroog GmbH verbunden.

## Daten direkt ansehen und herunterladen

Für die Nutzung des öffentlichen Archivs ist keine Installation erforderlich.
Die CSV-Dateien werden bei jedem erfolgreichen Cloud-Lauf automatisch
aktualisiert:

| Datensatz | Inhalt | Ansicht auf GitHub | Direkter CSV-Zugriff |
| --- | --- | --- | --- |
| `latest.csv` | Pro Datum der zuletzt beobachtete Zahlenstand | [Interaktive Tabelle](archive/latest.csv) | [Rohdaten / Download](https://raw.githubusercontent.com/lleisner/spiekeroog-gaeste-archiv/main/archive/latest.csv) |
| `snapshots.csv` | Alle täglichen Abrufe einschließlich späterer Revisionen | [Interaktive Tabelle](archive/snapshots.csv) | [Rohdaten / Download](https://raw.githubusercontent.com/lleisner/spiekeroog-gaeste-archiv/main/archive/snapshots.csv) |

GitHub stellt CSV-Dateien bis zu einer Größe von 512 KB automatisch als
durchsuchbare Tabelle dar. Auch wenn die vollständige `snapshots.csv` diese
Grenze später überschreitet, bleibt der direkte CSV-Zugriff erhalten.

Die kompakte Datei kann beispielsweise ohne lokalen Sammler direkt in ein
Pandas-DataFrame geladen werden:

```python
import pandas as pd

url = "https://raw.githubusercontent.com/lleisner/spiekeroog-gaeste-archiv/main/archive/latest.csv"
df = pd.read_csv(url, parse_dates=["abgerufen_am", "datum"])
```

Die unveränderten Antworten des öffentlichen Endpunkts liegen zusätzlich im
[Rohdatenverzeichnis](archive/raw/), sodass jeder normalisierte Zahlenstand
nachvollzogen werden kann.

## Cloud-Archiv über GitHub Actions

Das öffentliche Repository führt den Sammler in der GitHub-Cloud aus. Zwei
versetzte Termine um 06:17 und 12:47 Uhr (`Europe/Berlin`) geben dem täglichen
Lauf eine zweite Chance. Sobald an einem Kalendertag ein Snapshot vorliegt,
beendet sich jeder weitere Lauf ohne erneuten Webabruf.

Neue Daten werden direkt in `archive/` committed:

- `archive/latest.csv`: pro Datum der zuletzt beobachtete Wert
- `archive/snapshots.csv`: alle gespeicherten Abrufstände
- `archive/raw/*.html`: unveränderte Antworten des öffentlichen Endpunkts

Der Workflow lässt sich unter **Actions → Archive guest statistics → Run
workflow** auch manuell starten. GitHub-Zeitpläne können sich verspäten oder in
seltenen Lastspitzen ausfallen; die zwei Termine reduzieren dieses Risiko,
sind aber keine formale Verfügbarkeitsgarantie.

GitHub deaktiviert geplante Workflows in öffentlichen Repositories nach 60
Tagen ohne Repository-Aktivität. Die täglichen Archiv-Commits halten das Repo
im Normalbetrieb aktiv; trotzdem sollte der Actions-Status gelegentlich
kontrolliert werden.

## Optionale Installation auf macOS

```sh
git clone https://github.com/lleisner/spiekeroog-gaeste-archiv.git
cd spiekeroog-gaeste-archiv
./install.sh
```

Der Installer richtet zusätzlich einen persönlichen macOS-LaunchAgent ein. Er
startet den lokalen Sammler täglich um 06:15 Uhr und einmal direkt nach der
Installation. Repository- und Python-Pfad werden automatisch ermittelt. Diese
lokalen Daten bleiben unter `data/` und werden nicht ins Repository committed.

## Manuell ausführen

```sh
/usr/bin/python3 collect_spiekeroog.py
```

Nur Abruf und Formatprüfung, ohne Speicherung:

```sh
/usr/bin/python3 collect_spiekeroog.py --dry-run
```

Bei manueller oder lokaler Ausführung liegen die Ergebnisse unter
`data/gaestestatistik/`:

- `latest.csv`: pro Datum genau der zuletzt beobachtete Wert
- `snapshots.csv`: alle normalisierten Abrufstände
- `raw/*.html`: unveränderte Antworten des öffentlichen Endpunkts
- `collector.log` und `collector.error.log`: Ausgaben der täglichen Ausführung

Jeder Abruf enthält mehrere, zeitlich überlappende Tage. Diese Revisionen sind
beabsichtigt: So bleibt sichtbar, wie sich Planwerte bis zum jeweiligen Tag
verändert haben. Eine unmittelbar wiederholte, bitgenau identische
Serverantwort wird nicht doppelt gespeichert.

## CSV-Spalten

- `abgerufen_am`: Abrufzeit als ISO-8601-Zeitstempel mit Zeitzone
- `datum`: Datum des Zahlenwertes
- `geplante_anreisen`, `geplante_abreisen`, `geplante_tagesgaeste`
- `gaeste_auf_insel`
- `inhalt_sha256`: Prüfsumme der unveränderten HTML-Antwort
- `quell_url` und `rohdatei`: Herkunft und lokaler Prüfpfad

## Tägliche Ausführung auf macOS

`./install.sh` installiert die lokale LaunchAgent-Konfiguration. Die erzeugte
Datei enthält nur Pfade des jeweiligen Rechners und wird deshalb nicht im
Repository gespeichert.

Wenn das Repository später verschoben wird, `./install.sh` erneut ausführen.
Der Sammler kann nur Werte archivieren, während der Rechner regelmäßig läuft;
bereits verpasste Tage lassen sich über den Endpunkt nicht nachträglich laden.

Status prüfen:

```sh
launchctl print gui/$(id -u)/de.spiekeroog.gaestestatistik
```

Agent wieder entfernen, ohne bereits gesammelte Daten zu löschen:

```sh
./uninstall.sh
```

## Tests

```sh
/usr/bin/python3 -m unittest discover -s tests -v
```

## Rücksichtsvoller Betrieb

Cloud- und lokale Standardinstallation erzeugen jeweils höchstens einen Abruf
pro Kalendertag. Bitte das Intervall nicht unnötig verkürzen. Der öffentliche
Endpunkt kann sich jederzeit ändern; in diesem Fall beendet sich der Sammler
mit einem Fehler, statt unbemerkt falsch formatierte Daten zu speichern.

## Lizenz und Datenherkunft

Der Programmcode steht unter der MIT-Lizenz. Die archivierten Zahlen stammen
vom oben verlinkten öffentlichen Endpunkt; das Projekt beansprucht keine
Urheberschaft an den Quelldaten.
