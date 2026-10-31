# Prüfung der geführten Vorlagen — 31. Oktober 2026

Aktuelle Auswahl: **Anima Aesthetic 1.1 und MOSS SFT**. Die vorherigen anderen Modelle sind aus Auswahl, Konfiguration und Downloadmanifest entfernt. Unbenutzte dienst-eigene Gewichte wurden gelöscht: **19.800.621.400 Bytes**. Bestehende Bilder und extern gemeinsam genutzte Gewichte bleiben erhalten.

## Automatisierte Prüfung

- 48 Python-Tests bestanden, einschließlich Vorlagenkompilierung, Modellzuordnung, Pflichtfeldern, Validierung, Speicherung der ursprünglichen Eingaben und sicherer Modellbereinigung. Ein eigener Prozess-Test prüft die JSON-Fehlerbehandlung beim direkten Serverstart.
- Astro-Produktionsbuild erfolgreich.
- Semgrep: keine Befunde, keine Scanfehler.

## Echte GPU-Läufe

Alle zwölf Vorlagen wurden im Entwurfsprofil erfolgreich erzeugt. Zusätzlich wurden die großen Querformate mit Anima und MOSS geprüft: insgesamt **14 erfolgreiche Läufe**. Die gespeicherten Beispiele verwenden Vorlagenversion 3. Die unterbrochene letzte MOSS-Prüfung wurde am 31. Oktober nachgeholt; bereits fertige Beispiele wurden beibehalten.

| Vorlage | Profil | Format | Schritte | Dauer |
| --- | --- | --- | ---: | ---: |
| anima-portrait | preview | 576x832 | 30 | 22.60 s |
| anima-cozy | preview | 768x768 | 30 | 25.50 s |
| anima-film | preview | 832x576 | 30 | 22.23 s |
| anima-fantasy | preview | 576x832 | 30 | 20.04 s |
| anima-neon | preview | 832x576 | 30 | 20.00 s |
| anima-landscape | preview | 832x576 | 30 | 19.90 s |
| anima-manga | preview | 576x832 | 30 | 19.97 s |
| anima-watercolor | preview | 576x832 | 30 | 19.98 s |
| anima-chibi | preview | 768x768 | 30 | 25.06 s |
| anima-neon | standard | 1216x832 | 35 | 57.33 s |
| lowpoly-diorama | preview | 768x768 | 20 | 43.01 s |
| lowpoly-retro | preview | 832x576 | 20 | 29.05 s |
| lowpoly-world | preview | 832x576 | 20 | 29.07 s |
| lowpoly-retro | standard | 1216x832 | 50 | 188.57 s |

Die Bildbeispiele wurden im lokalen Archiv gespeichert; `recipe-report.json` enthält IDs, vollständige Prompts, Eingabefelder, Seeds und Einstellungen. Die Zeitmessungen gelten für diesen Rechner und sind keine universelle Qualitätsrangliste.

Bei der Sichtprüfung wurden zunächst unerwünschte Comic-Panels gefunden. Die fertigen Anima-Vorlagen verwenden deshalb kürzere, beschreibende Prompts mit jeweils einem Bildaufbau statt langer Regieanweisungen. Die überarbeiteten Porträt- und Low-Poly-Beispiele wurden visuell geprüft. Ein deutscher Motivtext wurde ebenfalls getestet und unverändert übernommen.

## Browserprüfung

**Drei Firefox-Tests bestanden** gegen die installierte Version. Geprüft wurden die automatische Modellwahl durch Vorlagen, vollständige Prompt-Vorschau, freier Modus, Anleitung, mobiles Layout, echte Bilderzeugung, Übernahme ursprünglicher Felder und Zurückweisung entfernter Modelle. Beim UI-Test wurden keine Browser-Seitenfehler beobachtet.
