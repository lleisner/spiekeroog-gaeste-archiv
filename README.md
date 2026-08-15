# Spiekerooger Gästestatistik-Archiv

`collect_spiekeroog.py` ruft einmal täglich die [öffentlich sichtbare
Gästestatistik](https://www.spiekeroog.de/buchung/file/codebehind/loadGaesteStatistik.php)
der Nordseebad Spiekeroog GmbH ab und speichert sowohl die unveränderte
HTML-Antwort als auch normalisierte CSV-Zeilen.

Das Projekt ist bewusst klein und benötigt außer Python keine zusätzlichen
Pakete. Es ist ein unabhängiges Community-Projekt und nicht mit der
Nordseebad Spiekeroog GmbH verbunden.

## Installation auf macOS

```sh
git clone https://github.com/lleisner/spiekeroog-gaeste-archiv.git
cd spiekeroog-gaeste-archiv
./install.sh
```

Der Installer richtet einen persönlichen macOS-LaunchAgent ein. Er startet den
Sammler täglich um 06:15 Uhr lokaler Zeit und einmal direkt nach der
Installation. Repository- und Python-Pfad werden automatisch ermittelt.

## Manuell ausführen

```sh
/usr/bin/python3 collect_spiekeroog.py
```

Nur Abruf und Formatprüfung, ohne Speicherung:

```sh
/usr/bin/python3 collect_spiekeroog.py --dry-run
```

Die Ergebnisse liegen unter `data/gaestestatistik/`:

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

Die Standardinstallation erzeugt genau einen Abruf pro Tag. Bitte das Intervall
nicht unnötig verkürzen. Der öffentliche Endpunkt kann sich jederzeit ändern;
in diesem Fall beendet sich der Sammler mit einem Fehler, statt unbemerkt
falsch formatierte Daten zu speichern.
