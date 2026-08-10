# Notiz: Prompt-Orchestrierungs-Muster aus ComfyUI-Persona-Director

Quelle: https://github.com/18yz153/ComfyUI-Persona-Director (extern, nicht
integriert, nicht im Projekt-Repo enthalten). Untersucht am 2026-08-10 auf
Nutzeranfrage, ob das Paket für unser Case-3-Problem (referenzbasierter
lokaler Farb-/Material-Transfer) brauchbar ist - Ergebnis: **nein, nicht
direkt**, siehe `RESULTS_masking_test1.md`. Das Muster selbst ist aber für
den offenen Punkt "Analyzer muss maskenbewussten Prompt bauen" (siehe Fazit
in `RESULTS_masking_test1.md`) als Referenz interessant und wird hier für
eine spätere Session festgehalten.

## Was das Paket tatsächlich macht

Reiner Prompt-Orchestrator für Text-zu-Bild-Workflows, keine Bildbearbeitung,
kein Masking, kein Qwen-Support. Nutzt externe LLM-APIs (GPT-4o/Gemini/
OpenRouter), um bei mehreren aufeinanderfolgenden Generierungen denselben
Charakter konsistent zu halten (7 Layer: Character/Outfit/Action/Location/
Composition/Style/JSON-State).

## Das übertragbare Muster

Ein einziger Node (`PersonaDirectorNode`) kapselt den kompletten Zyklus
"State laden -> LLM-Diff-Update -> State speichern -> Prompt zusammenbauen":

- **State als JSON-Datei**, geladen/gespeichert pro Charakter-Name.
- **Update-Erkennung per Instruction-Vergleich**: wenn die neue
  `user_instruction` identisch mit der zuletzt gespeicherten ist, wird der
  gecachte Prompt zurückgegeben statt erneut das LLM aufzurufen (Kosten-/
  Latenz-Sparen bei wiederholten Runs mit gleichem Input).
- **LLM erhält den vollständigen aktuellen State als JSON** plus die neue
  Instruktion, und wird angewiesen, nur die betroffenen Felder zu mutieren:

  ```
  Current State JSON:
  {...}

  Instruction: {user_instruction}
  ```

- **Locked vs. dynamische Felder** sind eine reine Konvention im
  System-Prompt (externe Config-Datei), nicht strukturell im Code erzwungen:
  bestimmte Layer (Character-Identität, gewählte Outfit-Items) werden dem
  LLM als "nicht verändern" markiert, andere (Pose, Ort, Kamera) als frei
  aktualisierbar.
- **Fester Prompt-Rahmen**: `POS_PREFIX` + LLM-Output + `POS_SUFFIX`,
  danach dedupliziert - das LLM liefert nur den variablen Mittelteil, nicht
  den kompletten Prompt-String.
- Drei Outputs: `positive_prompt`, `negative_prompt`, `debug_state` (für
  Nachvollziehbarkeit/Debugging direkt im Graph sichtbar).

## Relevanz für unseren offenen Punkt

Unser Analyzer müsste künftig statt freier Prosa einen maskenbewussten
Prompt bauen (SAM3-Maskenregion + Referenzbild -> "Change only the masked
X to match Y, keep everything outside the mask unchanged", siehe
`masking_test1_setlatentnoisemask.py`). Übertragbare Ideen, keine fertige
Lösung:

1. **State-Diff-Ansatz statt Freitext-Neugenerierung**: der Analyzer könnte
   den strukturierten `edit_plan` (bereits vorhanden, `edit_plan.schema.json`
   V1) als "aktueller State" an den Prompt-Builder geben und nur die
   Zielregion + Referenz explizit markieren, statt jedes Mal einen ganzen
   Prompt aus Rohbeschreibung neu zu generieren.
2. **Fester Prompt-Rahmen mit variablem Kern** senkt das Risiko, dass
   ungewollte Formulierungen (wie das schon dokumentierte "background"-Wort-
   Problem, `RESULTS_ab_background_word.md`) wieder einschleichen - der
   maskenbewusste Rahmensatz könnte fest codiert sein, nur Zielfarbe/
   -material und Maskenregion-Label variabel.
3. **Instruction-Vergleich zum Cachen** ist für unseren Single-Shot-Router
   vermutlich nicht relevant (kein Multi-Turn-State), daher nicht
   übernehmenswert.

Kein Implementierungsvorschlag, keine Codex-Konsultation durchgeführt -
reine Dokumentation für den Einstieg in die spätere Router-Integrations-
Session (siehe Fazit in `RESULTS_masking_test1.md`).
