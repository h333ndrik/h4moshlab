# H4 MOSH LAB — Übergabe an GLM-5.3-flash

Stand: 27. Oktober 2026. Diese Datei ist eine verdichtete Projektübergabe, kein wortgetreues Chatarchiv. Lies zusätzlich AGENTS.md und den tatsächlichen Code. Aussagen hier ersetzen keine erneute Prüfung lokaler Dateien.

## Aktueller Auftrag — höchste Priorität

Der Nutzer möchte zunächst **Ideen und Verbesserungen an echten Video-Mosh-Effekten und deren Smoothness**, vor der Handyansicht. Keine weiteren Mobile-Arbeiten ohne neuen Anlass. Aktuelles Design erhalten. Zuletzt besprochen: weicheren Ausgang aus Motion Loop entwickeln und mit gleichem Material gegen den bisherigen vergleichen. Das war eine Empfehlung, noch keine getestete Implementierung. Der Nutzer bittet jetzt um diese Modellübergabe.

Kommuniziere auf Deutsch, verständlich und konkret. Nutzer ist bei Terminal/Git nicht routiniert. Arbeite schrittweise; behaupte keine Erfolge ohne tatsächlich abgeschlossene Tests. Keine unnötigen Rückfragen, keine neuen Abhängigkeiten ohne Bedarf.

## Repository und Git-Stand

- GitHub: https://github.com/h333ndrik/h4moshlab
- Arbeitsverzeichnis dieser Cloud: /workspace/h4moshlab
- Lokaler Branch: work. Bisheriger Veröffentlichungsbranch: editor-workflow. main nicht überschreiben.
- Letzter Commit: ba9bfa4 (Layout-Präferenzen), davor 5580d7d (Originalton), 142bc16 (ein Exportbutton, Cursor-Vormerkung).
- ZIP des bisher gepushten Branches: https://github.com/h333ndrik/h4moshlab/archive/refs/heads/editor-workflow.zip
- **Es gibt uncommittete Mobile/WLAN-Änderungen.** Nicht versehentlich löschen oder als bereits veröffentlicht beschreiben. Vor Arbeit git status und git diff lesen.
- Die Übergabedatei allein enthält den Code nicht. Das neue Modell benötigt Repository plus uncommitteten Stand oder ein vollständiges Archiv davon.

## Produkt und verbindliche Vorgaben

Minimaler Videoeditor mit echter Codec-Datamoshing-Verarbeitung. Kein simuliertes Shader-Glitch als echter Mosh ausgeben. Originale niemals ändern. Medien, temporäre Dateien, Render in ignorierten Ordnern halten. Separate h4ngelic-Website nicht verändern.

Aktuelles Layout ausdrücklich beibehalten: Arial/Helvetica, dezenter hellgrauer Gradient, Überschrift exakt `h4 mosh lab` in Kleinbuchstaben, ohne `/ editor` und ohne Unterzeile. Import rechts oben, großer Player, kompakte horizontal scrollende Timeline, Clip-Pfeile/Entfernen, passende zweizeilige Übergangsboxen, kontextueller Dialog. Hauptaktionen Assemble preview und Export MP4. Kein zusätzlicher Download-Link und keine separaten Clip-/Sequenz-Tabs.

Video-only: Bilder und Photo Mosh zurückgestellt. Originalton wurde integriert; Audio-Moshing wurde nur theoretisch besprochen, ist nicht implementiert. Langfristig mobile Website über Internet ohne Mac; kurzfristig gleiches WLAN mit laufendem Mac. Keine native App/App Store aktuell.

Für spätere Designarbeit merken: H4-Mauscursor, Ruhelage -15 Grad, über aktiviertem anklickbarem Element +15 Grad. Nutzer proaktiv bei nächster Designphase daran erinnern. Asset fehlt; noch nicht implementieren. Touchgeräte haben keinen entsprechenden Mauszeiger.

## Architektur und tatsächlich funktionierender Stand

Python-Standardbibliothek + FFmpeg/FFprobe, Vanilla HTML/CSS/JS. **Kein React/Vite**, auch wenn früher ein fremdes Template erwähnt wurde. Browser schickt Clips an Python; Verarbeitung läuft auf dem Rechner des Servers.

- tools/mosh.py: ursprünglicher reproduzierbarer Classic-Proof, gemeinsame Auflösung **640x480**, 24 fps. Normalisierung auf MPEG-4 Part 2, I/P ohne B-Frames, großer GOP (10000), Szenenschnitte deaktiviert, q4. setpts=PTS-STARTPTS, Scale/Pad/FPS. Parser trennt VOPs am Startcode 00 00 01 b6, Bildtyp aus nächsten Bits. CLI-Proof nimmt standardmäßig bis sechs Sekunden je Clip; Editor nutzt ganze Clips innerhalb seiner Grenzen.
- tools/effects.py: wiederverwendbares Paar-API process(effect, a, b, transition_duration, output, parameters=None). prediction_plan liefert Donor-P-Frame-Indizes. Payloads werden unverändert wiederverwendet.
- Classic Mosh: I-Frame von Clip B weglassen, B-P-Frames auf Referenz aus A anwenden.
- Frame Melt: einzelne komprimierte P-Frames mehrfach wiederholen, repeat 2–12, Standard 4.
- Motion Loop: kurze Gruppen komprimierter P-Frames wiederholen, loop_frames 2–48, motion_start als Quellbewegungsfenster. Anders als Melt wird eine Gruppe statt eines einzelnen Frames wiederholt.
- tools/sequence.py: vorbereitete Clips cachen, vollständige Multi-Clip-Sequenz rendern, Cuts/Mosh-Übergänge, Berichte mit VOP-Indizes, Hashes, Referenz-Reset-Information. Dauer bleibt bis auf weggelassenen ersten B-Frame nachvollziehbar. Transition maximal sechs Sekunden.
- Ending `flow`: normale weitere B-P-Frames anhängen, kein frisches I-Frame einfügen; Verzerrung kann bestehen bleiben. Standard für Loop/Melt. **Das beseitigt den harten Reset, ist aber noch kein garantiert weicher Loop-Ausgang.**
- Ending `reset`: Rest ab entsprechender Position mit neuem I-Frame beginnen; klares Bild kann abrupt zurückspringen. Classic-Standard.
- tools/clip_audio.py: Originalton normalisieren/cachen, 48 kHz Stereo, exakte PCM-Samplezahl anhand 24fps, Stille auffüllen, Video-Startoffset beachten. Sequenzton folgt ursprünglicher Clip-Zeit, NICHT wiederholten Video-Donorframes. Mosh entfernt ersten B-Frame und dazu 2000 Audiosamples. AAC 192 kbit/s im MP4. Rein stille Quellen bleiben ohne Audiostream.
- tools/server.py: ThreadingHTTPServer, ein Processing-Job zugleich, Uploads bis 128 MiB/Clip, bis zwölf Clips, 120 Sekunden/Clip. Temporäre Sitzungen unter work/editor-*. HTTP-Media mit Range-Support, Jobs/Progress/Fehler. Lokale Host/Origin-Prüfung. Start prüft ffmpeg/ffprobe und gibt verständliche Fehlermeldungen.
- web/app.js: Import, horizontale Timeline, Desktop-Drag und Pfeile, Entfernen, aktive Clips, Übergangsdialog mit Dauer/Ending/Repeat/Loop/Bewegungsquelle, Vorschau, Scrubbing, Export, SessionStorage-Recovery. Assemble preview wechselt von Einzelclip zum bereits gerenderten langen Video zurück und merkt Position; nicht erneut rendern, solange Einstellungen gleich. Ein Exportbutton erstellt temporären Downloadanker.

## Offene Mobile/WLAN-Änderungen (bereits im Arbeitsverzeichnis)

Dateien: AGENTS.md, README.md, tools/server.py, web/app.js, web/index.html, web/style.css; neu tools/lan.py, MOBILE_WEB.md, tests/test_lan.py, tests/mobile_smoke.py.

- `--lan` bindet optional 0.0.0.0 statt weiterhin standardmäßig 127.0.0.1. Private IPv4-Erkennung, optional --lan-address.
- Generierter Sitzungslink mit Pairing-Key, nach Besuch Redirect auf saubere URL und HttpOnly/SameSite=Strict-Cookie. Nicht gepaarte Remote-Anfragen 401. Host/Origin-Sperren bleiben. /api/connection gibt den Handy-Link nur lokalen Loopback-Clients. UI zeigt Copy phone link nur dann an.
- Privates vertrauenswürdiges WLAN, HTTP unverschlüsselt. Nicht für Portfreigabe/öffentliches Hosting gedacht. Tokens nicht in Git, Logs externer Tools oder Dokumentation kopieren. Lokales Programm zeigt absichtlich den eigenen Sitzungslink an.
- Größere Touch-Ziele, Pfeilsteuerung statt Drag auf grobem Pointer, 16px Select-Schrift gegen iOS-Zoom. Layout erhalten.
- Wenn Export auf Touch erst rendern musste: Hinweis auf zweiten Tipp zum Download, um verlorene Browser-User-Geste abzufangen.
- **Noch keine verifizierte echte iPhone/Safari-Nutzung.** Mobile-Auftrag wurde zugunsten der Effekte zurückgestellt.

## Tests und letzter tatsächlicher Befund

- `python3 -m unittest discover -s tests -v`: zuletzt **24 Tests bestanden**, 55.699 Sekunden. Ergebnis aus /tmp/h4-tests.log geprüft. Darunter neue LAN-HTTP-Tests mit simuliertem Remote-Peer, Cookie-Pairing, abgelaufenem Key, Host/Origin-Sperre; außerdem Engine/Sequenz/Audio/Importfehler.
- `python3 -m py_compile tools/server.py tools/lan.py` und `node --check web/app.js`: bestanden.
- tests/browser_smoke.py: umfangreicher vorhandener Desktop-Chromium-End-to-End-Test, zuletzt vor Mobile-Änderungen bestanden; seit Mobile-Änderungen noch nicht erneut abgeschlossen.
- tests/mobile_smoke.py: erster Lauf scheiterte an Testvergleich der nummerierten Clipnamen nach Reorder (die Nummern ändern sich erwartungsgemäß). Assertion auf Namen ohne Nummer korrigiert; **korrigierter Test noch NICHT ausgeführt/als bestanden nachgewiesen**. Prüft Touch-Import, Größen, Reorder, Dialog, zwei Export-Tipps und vollständiges Decoding.
- Bestehende Tests prüfen echte komprimierte Payloads/Indexfolge und Full Decode, nicht bloß FFmpeg-Exit.
- Testartefakte unter work/ sind nicht eingecheckt. Keine neuen privaten Video-/Audioaufnahmen veröffentlichen, nur weil Testdateien vorhanden sind.

## Effektideen — klar als noch ungebaut behandeln

Priorität 1: Loop schrittweise freigeben: Wiederholungen zum Ende reduzieren, danach normale P-Frame-Folge fortführen, ohne frisches I-Frame. Visuell prüfen, ob es wirklich weicher wird; falsche Referenzen können weiterhin sichtbare Sprünge erzeugen. Komprimierte Frames nicht unbedacht umordnen. Classic und bisherigen reproduzierbaren Workflow erhalten.

Priorität 2: Bessere Bewegungsfenster wählen, statt bloß mehr Modi. Kamerafahrten, Motivbewegung und ruhige Stellen vergleichen. Vorhandene Quellvorschau nutzen.

Weitere Kandidaten: im Verlauf längere Loop-Gruppen; Motion Stutter als ehrliches Preset auf vorhandener Technik; Reset Pulse mit absichtlich eingefügten klaren Referenzbildern (rhythmischer harter Effekt, kein Smoothness-Fix). Keine davon bereits als funktionierend bewerben.

Sinnvoller nächster Arbeitsschritt nach Nutzerauftrag: EINEN weicheren Loop-Ausgang prototypisieren, gleiche Quellen/bestehender Loop/neuer Ausgang, exportierte Vergleichsvideos, Representative Frames, Full Decode, Regressionen. Kein Shader oder Crossfade als Codec-Mosh tarnen. Parameter erst exponieren, wenn getestet und visuell sinnvoll.

FFglitch/ffedit war diskutiert, aber kein verifiziertes zusätzliches Motion-Vector-Manipulationsverfahren implementiert. Nicht behaupten, Motion Loop sei ein eigenständiger FFglitch Motion Transfer.

## Lokaler Mac — Nutzeranleitung

Im Projektordner, der tools enthält:

```sh
eval "$(/opt/homebrew/bin/brew shellenv)"
python3 tools/server.py --port 8766
```

Dann Mac-Browser http://127.0.0.1:8766. Terminal offen lassen. Zum Stoppen Control+C (nicht Command+C). Während Python läuft, werden hineingetippte Shellbefehle nicht ausgeführt. Address already in use heißt alter Server/anderes Programm belegt Port; anderen Port wählen oder eigenen alten Server sauber stoppen.

Homebrew FFmpeg ist auf Nutzers Mac bereits installiert (damals 9.0.2_1). ffprobe gehört dazu. Nutzer nutzt Apple-Silicon-Mac, Python war Apple 3.9; Laufzeitcode kompatibel halten. Nicht Cloud-Linux-Binaries auf Mac übernehmen.

WLAN-Modus ist im uncommitteten Stand dokumentiert in MOBILE_WEB.md. Public Link ohne Mac braucht später eigenes Hosting/HTTPS/Sitzungsisolierung; GitHub Pages kann den Python/FFmpeg-Server nicht ausführen. Privates Repo kann GitHub-Login erfordern; Passwortauth für git clone ist nicht unterstützt. Niemals Tokens im Chat anfordern.

## Quellen und Referenzen

README.md, EDITOR.md, AUDIO.md, MOTION_LOOP.md, PHASE2.md und AGENTS.md lesen. Supermosh-Referenz wurde untersucht: https://github.com/supermosh/supermosh.github.io (GPLv3; keine Codeübernahme). Referenzvideo war 640x480. Eigene Engine bleibt MPEG-4 Part 2 mit H264-Auslieferung.

Frühere Nutzerdateien: IMG_3194.MOV, IMG_1993.MOV, Supermosh_2026-10-26T01-01-55.mp4. Cloud-Anhänge befinden sich gegebenenfalls unter /workspace/attachments; diese Pfade sind nicht portabel und Dateien nicht Teil des Git-Repos. Bei Bedarf Nutzer um erneute Bereitstellung bitten. Ohne diese Dateien synthetische samples/clip-a.mp4 und clip-b.mp4 verwenden/generieren, Originale nie ändern.

## Übergabe-Prompt

„Lies HANDOFF_GLM.md und AGENTS.md. Inspiziere Code und git diff, bevor du Änderungen machst. Erhalte das aktuelle Layout und echte Codec-Verarbeitung. Priorisiere jetzt Mosh-Effekte und deren Smoothness vor Mobile. Besprich bzw. entwickle als nächsten gezielten Schritt einen weicheren Motion-Loop-Ausgang mit direktem Rendervergleich zum bisherigen Verhalten. Bewahre Classic Mosh und Originalton. Prüfe tatsächliche Outputs und Regressionen; erfinde keine fertigen Effekte oder Testergebnisse.“

## Update nach dieser Übergabe

Effektarbeit wurde priorisiert. Loop Release ist inzwischen als neuer MPEG-4-P-Frame-Scheduling-Modus in Engine und Dialog integriert; siehe LOOP_RELEASE.md und tools/compare_release.py. 26 Integrationstests bestanden. Kein kontinuierliches Ausblenden der Verzerrung: frühere Blockwechsel bleiben möglich. Cursor-Asset wurde im Workspace nicht gefunden, anderer h4ngelic-Chat ist nicht zugänglich. Schwarz-Weiß/kleiner/sanfte Rotation bleiben vorgemerkt. Mobile-Änderungen weiterhin uncommittet und ohne physischen iPhone-Nachweis. Git-Status prüfen.

## Cursor umgesetzt

Original-H4-SVG aus hochgeladener h4ngelic-preview (5).html extrahiert. web/h4-cursor.svg, web/cursor.js, CSS und feste Serverrouten implementiert: 22x33px, schwarz/weiße Kontur, -15/+15 Grad mit 180ms ease-out. Touch/Video/native Fallback, reduzierte Bewegung, Modal und deaktivierte Controls berücksichtigt. tests/browser_cursor.py ist erfolgreich gelaufen; Screenshot work/h4-cursor.png visuell geprüft. Frühere Aussagen zum fehlenden Asset sind überholt.

## Aktuelle Cursorwinkel (ersetzt vorherige Angaben)

Nutzerkorrektur: Ruhelage -25 Grad, über aktivierter Klickmöglichkeit 0 Grad. Weiche Rotation und Größe unverändert.

## Neue Videoeffekte

Progressive Melt und Motion Stutter sind in Engine und Dialog integriert, siehe DYNAMIC_EFFECTS.md. Nutzer hat Hosting/Verlinkung ausdrücklich vertagt. Progressive Melt reduziert P-VOP-Wiederholungen, Stutter wechselt Vorhersage-Bursts mit Vorwärtsbewegung. Beide enden mit zusammenhängenden Donorframes ohne Reset, benötigen mindestens 0.5s und motion_start=0. 29 Integrationstests bestanden; neue Browsernachweise gesondert prüfen. Keine Audio-Mosh- oder Shader-Effekte.

Abschlussnachweis: tests/browser_dynamic.py bestanden (beide neuen Modi, echter Render, Export, Assemble-Rückkehr). Bestehender tests/browser_smoke.py mit zwei Original-MOVs und synthetischem Clip erneut bestanden, keine JavaScript-Fehler. Ein während Entwicklung gefundener falscher DOM-Selektor wurde korrigiert und beide Browserläufe danach erfolgreich wiederholt. Vergleich output/dynamic-effects-real/comparison.mp4 vollständig decodiert und during.png visuell geprüft. Private Medien nicht hochladen.

## Gentler repetition movement

Frame Melt, Progressive Melt und Motion Stutter haben jetzt optional `smooth` (Default API false, neu ausgewählte UI-Modi true). Vorwärtssprünge zwischen Donorframes maximal2, letztes Viertel zusammenhängend, Gesamtdauer und Originalton identisch. Details SMOOTH_REPETITIONS.md, reproduzierbar tools/compare_smooth.py. Original cadence bleibt auswählbar; andere Effekte unverändert. Im Realvideo-Frame-Melt-Test maximaler Donorsprung41→2. Browsertest für alle3 geglätteten Modi bestanden; vollständigen letzten Unittest-/Regression-Status vor Behauptung prüfen.

Abschluss Glättung: neuer Browserlauf tests/browser_dynamic.py für alle3 geglätteten Modi bestanden; bestehender kompletter Browser-Smoke mit Original-MOVs erneut bestanden, keine JS-Fehler. Unittest-Gesamtlauf führte31Tests aus:30bestanden, eine neue Vergleichsassertion verlangte fälschlich strikt kleinere Sprünge auch bei bereits nur2Frames. Sie wurde auf nichtgrößer korrigiert; beide neuen Smooth-Tests danach erneut ausgeführt und bestanden (12.211s). Keine Engine-/Payload-/Audio-Regression fehlgeschlagen. Original und Gentler mit echten MOVs vollständig decodiert, PCM bytegleich und Exit-Frames visuell geprüft.

## Aktuelles Designexperiment

Nutzer hat ausdrücklich dunkle/negative Designvariante gewünscht: schwarzer Hintergrund, helle Schrift, graues Videofeld. Palette in web/style.css angepasst, natives color-scheme dark. Layout/Engine/Cursor unverändert. Noch keine endgültige Nutzerabnahme. Screenshot demo/editor/dark.png. Browser-Dynamic-Smoke mit echtem Render/Export bestanden, leere/gefüllte Desktop-/schmale Ansicht und Modal visuell geprüft; kein Seitenoverflow bei320/390/600/1200px. Letzter Nutzer fragte nach Öffnen: im entpackten Projekt eval Homebrew shellenv, python3 tools/server.py --port 8770, Mac-Browser http://127.0.0.1:8770, Terminal offenlassen.
