# gz2k2's Python Coding Style Guide

Konventionen für `.py`-Dateien in diesem Repository.

## Dateistruktur

Große, überladene Dateien sollten vermieden werden zugunsten strukturierter Dateien, die jeweils eine spezifische Reihe von Verantwortlichkeiten abdecken und eine minimale, fokussierte öffentliche Schnittstelle exponieren.

Während die Entscheidung, eine neue Datei hinzuzufügen, sorgfältig getroffen werden sollte, sind die Kosten einer neuen Datei gering. Die Kosten für das Vermischen von Belangen in einer riesigen Datei sind Code, der schwer zu lesen, zu warten und voller technischer Schulden ist.

### Zerlegung (Decomposition)

Erstellen Sie eine neue Datei (ein Modul), wenn eine der folgenden Bedingungen zutrifft:

-   **Der Code könnte plausibel wiederverwendet werden.** Schon bevor ein zweiter Konsument existiert, sollte Code mit dem Potenzial zur Wiederverwendung in eine eigene Datei. Extrahieren Sie ein wiederverwendbares Widget oder eine Fähigkeit, sobald das Design auf einen zweiten Konsumenten hindeutet. Das spätere Aufteilen des Codes, wenn er bereits mehrere Konsumenten hat, ist weitaus teurer als ein zusätzliches Modul.

-   **Der Code besitzt einen Zustand, den niemand sonst berühren sollte.** Pythons Modul-Scope ist eine starke Abgrenzung für die Privatsphäre, und er ist auf die Datei beschränkt. Zustand, der Invarianten enthält – Caches, Deduplizierungstabellen, Singleton-Einstellungen – gehört als Modul-Level-Variablen in eine eigene Datei, wo er vom Rest des Addons physisch unerreichbar ist. Jeder Zugriff muss dann über eine bewusste öffentliche API erfolgen, die den Vertrag durchsetzt, den Sie tatsächlich für die Nutzung des Moduls festlegen möchten.

-   **Abstraktion würde die Auswirkungen von Änderungen minimieren.** Wenn Sie eine Fähigkeit so kapseln können, dass Konsumenten dieser Fähigkeit von Änderungen an den zugrunde liegenden Daten, Ereignissen oder API-Aufrufen, von denen die Fähigkeit abhängt, isoliert werden können, wird Ihr Code erheblich einfacher zu warten sein, und Sie können schneller auf Änderungen reagieren.

-   **Die Datei ist zu groß geworden, um sie im Kopf zu behalten.** Wenn Sie kein funktionierendes Modell einer Datei im Kopf behalten können, macht die Datei mit ziemlicher Sicherheit zu viel. Sie müssen nicht jede Codezeile verstehen oder genau wissen, wo sie sich in einer Datei befindet, aber Sie sollten in der Lage sein, eine starke Intuition basierend auf einem einmaligen Durchlesen einer Datei zu entwickeln. Eine mehrere tausend Zeilen umfassende Datei mit UI-Konstruktion, Aktualisierungs-Orchestrierung, Ereignisversand und wer weiß was noch, ist resistent gegen Refactoring und schwer zu warten, da niemand alles gleichzeitig im Kopf behalten kann.

### Module vs. Klassen

Die Logik in den meisten Dateien sollte entweder als Module oder Klassen gekapselt werden.

Ein **Modul** wird als eine Sammlung von Funktionen, Variablen und Klassen exponiert. Andere Dateien greifen über `import module_name` oder `from module_name import ...` darauf zu. Module eignen sich hervorragend für Utility-Funktionen, Singletons oder zur Gruppierung verwandter Funktionalitäten.

```python
# my_module.py

import logging

# Modul-Level-Konstanten
DEFAULT_TIMEOUT = 30

# Modul-Level-Zustand (vorsichtig verwenden, da global)
_cache = {}

def _private_helper_function(data):
    """Eine private Hilfsfunktion."""
    logging.debug(f"Processing data: {data}")
    return data.upper()

def process_data(data_item):
    """
    Verarbeitet ein Datenelement.

    Dies ist Teil der öffentlichen API des Moduls.
    """
    if data_item in _cache:
        return _cache[data_item]
    
    result = _private_helper_function(data_item)
    _cache[data_item] = result
    return result

if __name__ == "__main__":
    # Beispielnutzung, wenn das Modul direkt ausgeführt wird
    print(process_data("hello"))
    print(process_data("world"))
    print(process_data("hello")) # Sollte aus dem Cache kommen
```

Eine **Klasse** exponiert einen Konstruktor (`__init__`), der es anderen Dateien ermöglicht, Instanzen über `ClassName(...)` zu erstellen und Methoden aufzurufen, die auf einer spezifischen/dedizierten Instanz der Klasse statt auf einer einzelnen gemeinsam genutzten Instanz operieren.

Klassen eignen sich hervorragend für Dinge wie UI-Widgets, bei denen Sie möglicherweise mehrere Instanzen gleichzeitig betreiben, die jeweils eine ähnliche Funktion, aber mit leicht unterschiedlichen Zielen ausführen. Klassen bieten eine stärkere Kapselung von Instanzzustand im Vergleich zu Modulen, die eher für globalen oder Singleton-Zustand verwendet werden.

```python
# ui_panel.py

class ListPanel:
    """
    Eine Klasse zur Darstellung eines Listenpanels in der Benutzeroberfläche.
    """
    ROW_HEIGHT = 20 # Klassenkonstante

    def __init__(self, parent, options=None):
        """
        Konstruktor für ListPanel.
        """
        self.parent = parent
        self.options = options if options is not None else {}
        self._items = [] # Instanz-privater Zustand (Konvention)
        self._create_ui()

    def _create_ui(self):
        """
        Private Methode zum Erstellen der UI-Komponenten.
        """
        print(f"Creating UI for panel in {self.parent} with options {self.options}")

    def set_items(self, items):
        """
        Setzt die anzuzeigenden Elemente im Panel.
        """
        self._items = list(items)
        print(f"Items set: {self._items}")

    def get_item_count(self):
        """
        Gibt die Anzahl der Elemente zurück.
        """
        return len(self._items)

if __name__ == "__main__":
    panel1 = ListPanel("main_window", {"sortable": True})
    panel1.set_items(["Apple", "Banana"])
    print(f"Panel 1 item count: {panel1.get_item_count()}")

    panel2 = ListPanel("sidebar")
    panel2.set_items(["Orange"])
    print(f"Panel 2 item count: {panel2.get_item_count()}")
```

Die Standardreihenfolge von oben nach unten ist: Imports → Modul-Level-Konstanten → Modul-Level-Variablen → Modul-Level-Funktionen → Klassen-Definitionen → `if __name__ == "__main__":` Block. Die Reihenfolge *innerhalb* eines Abschnitts ist eine Entscheidung zur Lesbarkeit – Funktionen und Methoden haben keine Ladezeitabhängigkeit voneinander, daher können sie in jeder Reihenfolge erscheinen, die am einfachsten zu verstehen ist.

Verwenden Sie Abschnitte und Unterabschnitts-Banner (siehe Kommentare), um die Struktur der Datei zu verdeutlichen und gemeinsame Logik zu gruppieren.

### Benennung und Privatsphäre

| Art | Form | Beispiel | Privatsphäre (Konvention) |
|---|---|---|---|
| Modulname | `snake_case` | `event_capture`, `list_panel` | — |
| Klassenname | `PascalCase` | `EventCapture`, `ListPanel` | — |
| Konstanten | `UPPER_SNAKE_CASE` | `ROW_HEIGHT`, `NOTIFY_INTERVAL` | Modul-lokal, durch Konvention |
| Modul-lokale Funktion | `_snake_case` | `def _notify():` | Modul-lokal, durch Konvention |
| Modul-lokaler Wert | `_snake_case` | `_hide_older = False` | Modul-lokal, durch Konvention |
| Öffentliche Funktion oder Methode | `snake_case` | `event_capture.exclude`, `panel.set_items` | Exponiert |
| Klassenfeld (Instanzvariable) | `self.field_name` | `self.frame` | Keine echte Privatsphäre, `_field_name` für "protected", `__field_name` für Namens-Mangling |

`PascalCase` ist für Klassennamen reserviert. Funktionen, Methoden und Variablen verwenden immer `snake_case`. Ein führender Unterstrich (`_`) kennzeichnet eine Variable, Funktion oder Methode als "intern" oder "nicht-öffentlich" – dies ist eine Konvention, keine erzwungene Privatsphäre. Python hat keine echte private Zugriffsmodifikatoren wie andere Sprachen.

Verwenden Sie standardmäßig Modul-lokal für alles, was nicht Teil der öffentlichen API ist. Wenn ein Verhalten nicht von außerhalb der Datei aufrufbar sein sollte, kennzeichnen Sie es mit einem führenden Unterstrich (`_`). Verlassen Sie sich nicht auf Namenskonventionen, um Methoden als "privat" zu kennzeichnen – wenn sie auf der Klasse oder Instanz zugänglich sind, sind sie technisch öffentlich.

---

## Leerraum & Visuelles Layout

Wir sollten unseren Code logisch in Absätze gliedern, die visuell von ihren Nachbarn getrennt sind, so wie wir unsere Ideen beim Schreiben in Absätze gliedern. Dies ermöglicht es dem Leser, verwandten Code/Ideen leicht zu identifizieren, ohne erneut lesen zu müssen.

---

### 1. Funktionskörper atmen

Fügen Sie eine Leerzeile nach der Funktionssignatur und vor dem schließenden `return` (falls vorhanden) oder dem Ende des Funktionskörpers ein. Gilt für jede Funktion mit einem echten Körper. Überspringen Sie dies für triviale einzeilige Accessoren (z.B. `def is_foo(x): return x.y`).

```python
# Vermeiden
def scroll_into_view(child):
    if not child: return
    # ...

# Bevorzugen
def scroll_into_view(child):

    if not child:
        return
    # ...

```

---

### 2. Verzweigungen: nur kompakt, wenn einfach

Eine Verzweigung kann in einer Zeile bleiben, wenn **beide** Bedingungen erfüllt sind:

1.  Ihr Körper ist eine einzelne Anweisung.
2.  Ihre Bedingung ist kurz genug, um auf einen Blick gelesen zu werden.

Erweitern Sie auf mehrere Zeilen, wenn eine Seite komplex wird: mehrere Anweisungen im Körper oder eine lange / tief kombinierte Bedingung.

```python
# OK: einfache Bedingung, einzelne Anweisung
if not row: return
if target < 0: target = 0
if a or b: do_thing()

# Grenzwertig: ein paar einfache Prüfungen können kompakt bleiben, wenn
# die Zeile immer noch auf einen Blick lesbar ist (verwenden Sie Ihr Urteilsvermögen)
if not c_top or not r_top or not r_bottom: return

# Vermeiden: mehrere Aktionen in einer Zeile zusammengepfercht
if reset: target = 0; pending_scroll_key = None

# Bevorzugen: erweitert
if reset:
    target = 0
    pending_scroll_key = None
```

Die gleiche Regel gilt pro Zweig in `elif` / `else`-Ketten – zählen Sie Anweisungen und Bedingungskomplexität für jeden Zweig unabhängig, nicht über den gesamten `if`/`end`-Block.

---

### 3. Logische Absätze durch Leerzeilen getrennt

Innerhalb einer Funktion gruppieren Sie verwandte Ideen und Anweisungen, die "eine Sache zusammen tun", in Absätze, mit einer Leerzeile zwischen jedem Absatz. Ein Absatz mit einer Zeile ist in Ordnung, wenn die Zeile tragend ist – frühe Rückgaben, wichtige Zustandsänderungen, der primäre Nebeneffekt der Funktion.

Dies gilt nicht nur für die Top-Level-Logik in einer Funktion, sondern auch für die Logik innerhalb von `if`-Blöcken, `for`-Blöcken usw.

```python
c_top = content.get_top()
r_top = child.get_top()
r_bottom = child.get_bottom()

if not c_top or not r_top or not r_bottom:
    return

padding = padding or ROW_GAP

y = c_top - r_top
h = r_top - r_bottom
```

---

### 4. Variablendeklarationen sind ein eigener Absatz

Eine Reihe von Zuweisungen von lokalen Variablen ist ein eigener Absatz. Wenn der nächste Codeblock diese testet, validiert oder anderweitig bearbeitet, fügen Sie eine Leerzeile zwischen den Deklarationen und dieser Logik ein.

Die Ausnahme: Eine einzelne Deklaration, die eng mit etwas wie einem einfachen Clamp oder einer Normalisierung gepaart ist, die *dieselbe Variable* mutiert, liest sich als eine Einheit und kann ohne Leerzeile zusammenbleiben.

```python
# OK: einzelne Deklaration + sofortiger Clamp an derselben Variable
c_top = content.get_top()
if c_top < min_top: c_top = min_top

# Vermeiden: Deklarationen gefolgt von Logik ohne Unterbrechung
c_top = content.get_top()
r_top = child.get_top()
r_bottom = child.get_bottom()
if not c_top or not r_top or not r_bottom:
    return

# Bevorzugen: Leerzeile vor dem Logikabsatz
c_top = content.get_top()
r_top = child.get_top()
r_bottom = child.get_bottom()

if not c_top or not r_top or not r_bottom:
    return

# Vermeiden: mehrere Deklarationen + Clamp an nur einer davon
c_top = content.get_top()
r_top = child.get_top()
r_bottom = child.get_bottom()
if r_bottom < max_bottom: r_bottom = max_bottom

# Bevorzugen: zuerst Leerzeile
c_top = content.get_top()
r_top = child.get_top()
r_bottom = child.get_bottom()

if r_bottom < max_bottom: r_bottom = max_bottom
```

---

### 5. Kompakte Formen, die kompakt bleiben

Verwenden Sie den gesunden Menschenverstand bei der Anwendung dieser Regeln. Bestimmte Strukturen sind kompakter sinnvoller:

-   Lookup-Tabellen (Dictionaries) (`CLASSIFICATION_NAMES`, `REQUIRED_EVENTS`) – sie sind als flache Listen scanbar.
-   Triviale einzeilige Accessoren und Prädikate.
-   Kurze Schleifenkörper, bei denen eine Erweiterung mehr schadet als nützt.

Faustregel: **Erweitern Sie, wenn es die Lesbarkeit fördert.** Wenn eine kompakte Form bereits auf einen Blick leicht zu parsen ist, lassen Sie sie unverändert.

---

## Kommentare

Kommentare dienen dazu, Informationen hinzuzufügen, die aus dem Code selbst nicht ersichtlich sind. Der Code zeigt *was*, Kommentare sollten *warum* erklären (eine Einschränkung, eine Eigenart, eine nicht offensichtliche Entscheidung). Aber Sie sollten nur das Bedürfnis verspüren, *warum* zu erklären, wenn es aus dem Code nicht offensichtlich ist. Beachte dabei, dass vor Kommentaren (einschließlich Bannern) generell maximal zwei Leerzeilen stehen dürfen.

Ein Kommentar ist nur dann wertvoll, wenn seine Entfernung einen zukünftigen Leser mit einer Frage zurücklassen würde, die er nicht allein durch das Lesen des Codes beantworten kann. Jeder Kommentar, der entfernt werden kann, ohne jemanden zu verwirren, sollte gelöscht werden.

### Wertvolle Kommentare

-   Bug-Workarounds, API-Eigenheiten, versionsabhängiges Verhalten.
-   Nicht-offensichtliche Designentscheidungen (warum X statt Y).
-   Verträge, die der Code nicht selbst durchsetzen kann.
-   Externer Kontext (z.B. ein bestimmtes Systemereignis, eine Race Condition, eine Ladeabhängigkeit).

### Wertlose Kommentare

-   Wiederholung der Funktionssignatur ("Gibt den Wert von X zurück").
-   Erzählung von offensichtlichem Code ("Iteriert über jedes Element").
-   Einleitende Sätze, die die nächste Zeile zusammenfassen.
-   Verweise auf "die jüngste X-Änderung", die schnell veralten und bereits im Commit-Verlauf abgedeckt sind.

```python
# Vermeiden: wiederholt, was der Tabellenname und der Inhalt bereits vermitteln
# Alle Textur-Asset-Pfade, die vom Addon verwendet werden. Zentralisiert, damit ein zukünftiger
# Skin-Override eine einzeilige Änderung ist.
UI_TEXTURES = { ... }

# Bevorzugen: Kommentar ganz weglassen
UI_TEXTURES = { ... }

# Gut: externer Kontext, der aus dem Code nicht ersichtlich ist
# Blizzard gibt einen leeren `cstr` für einstufige Erfolge zurück; das
# `description`-Feld auf Erfolgsebene ist die menschenlesbare Bezeichnung.
def get_achievement_header(ach_id): ...
```

### Prägnante Inline-Kommentare schlagen lange Ausführungen

Wenn ein Kommentar etwas Spezifisches zu einer bestimmten Zeile oder einem Codeblock erklärt, platzieren Sie ihn an dieser Zeile. Lange Ausführungen am Anfang einer Funktion, die mehrere unzusammenhängende WARUMs bündeln, sind schwerer zu verstehen als dieselben Fakten, die inline an ihren jeweiligen Stellen platziert sind.

Ein Kommentar am Anfang einer Funktion ist in Ordnung für eine Invariante, die tatsächlich die gesamte Funktion umfasst. Es ist falsch, eine Sammlung unzusammenhängender Punkt-Kommentare als Header zu verkleiden.

```python
# Vermeiden: lange Ausführungen am Anfang der Funktion, die unzusammenhängende WARUMs mischen
# Die erste Aktualisierung nach dem Laden wird als Basislinie behandelt, damit wir nicht
# für jedes existierende verfolgte Element ausgelöst werden. Elemente, die durch den Zonenfilter
# ausgeblendet werden, werden trotzdem als erweitert markiert, und der Scroll-Pin
# führt stillschweigend einen No-Op aus, da sie nicht in active_rows sein werden.
def detect_and_show_newly_tracked(current_keys):
    # ...

# Bevorzugen: jedes WARUM an der Zeile oder dem Codeblock, den es erklärt
def detect_and_show_newly_tracked(current_keys):

    if not previous_tracked_keys:
        # Erste Aktualisierung nach dem Laden: Basislinie stillschweigend erfassen, damit wir
        # nicht für jedes bereits verfolgte Element ausgelöst werden.
        previous_tracked_keys = current_keys
        return

    # Als erweitert markieren, auch wenn der Zonenfilter dieses Element ausblendet.
    expanded_keys[key] = True

    # Durch Filter ausgeblendete Elemente haben keine passende Zeile in active_rows, daher
    # führt apply_pending_scroll natürlich einen No-Op für sie aus.
    if last_new_key: ...

```

### Trennzeichen in Tabellen (Dictionaries/Listen)

Kurze Beschriftungen, die Einträge in einem Dictionary oder einer Liste gruppieren, sind keine echten Kommentare – sie sind visuelle Hilfen. Verwenden Sie **Title Case** für kurze Überschriften.

```python
UI_COLORS = {
    # Row Backgrounds
    "super_track_bg": (1.0,  0.82, 0.0,  0.12),
    "completed_bg":   (0.12, 0.35, 0.15, 0.45),

    # Progress Bar
    "bar_bg":         (0.22, 0.22, 0.24, 0.95),
    # ...
}
```

---

### Abschnittsüberschriften

Abschnittsüberschriften sollten verwendet werden, um große Dateien aufzuteilen und die Navigation zu erleichtern.

Abschnittsüberschriften sollten ein dreizeiliges Banner sein, das genau auf 80 Spalten aufgefüllt ist. Es sollten zwei Leerzeilen über dem Banner (eine zusätzliche Leerzeile über die übliche einzelne Leerzeile zwischen Top-Level-Deklarationen hinaus) und eine Leerzeile darunter vor der ersten Deklaration im Abschnitt stehen.

Abschnittsnamen sollten in GROSSBUCHSTABEN geschrieben werden.

```python


################################################################################
# SECTION NAME
################################################################################

def first_thing_in_section():
    pass
```

Die zwei Leerzeilen darüber sind die Regel, die einen Abschnittswechsel von einem gewöhnlichen Deklarationswechsel unterscheidet. Ein Leser, der die Datei durchscrollt, sieht den zusätzlichen Platz, bevor er das Banner selbst sieht.

---

### Unterabschnittsüberschriften

Unterabschnittsüberschriften sollten ähnlichen Regeln wie Abschnittsüberschriften folgen, aber verwendet werden, um den Code innerhalb eines Abschnitts in logische Gruppierungen zu unterteilen.

Unterabschnittsüberschriften sollten einzeilige Banner sein, die genau auf 80 Spalten aufgefüllt sind. Es sollte nur eine einzelne Leerzeile darüber stehen.

Unterabschnittsnamen sollten in GROSSBUCHSTABEN geschrieben werden.

```python

# SUB-SECTION NAME #############################################################

def first_thing_in_sub_section():
    pass
```
