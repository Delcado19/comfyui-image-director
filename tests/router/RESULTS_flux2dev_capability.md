# Ergebnis: Flux.2 Dev als Alternative zu Qwen Image Edit 2511 für Fall 3

Codex-Design und -Auswertung, Thread `019fd14f-0515-7a91-958a-ce162f468ce2`.
Auf Nutzerwunsch getestet ("teste flux.2 dev zuerst, bevor du flux.2 klein
in erwägung ziehst") als "anderer referenz-fähiger Modellzweig", nachdem
alle Nicht-Masking-Hebel auf dem Qwen-Image-Edit-2511-Pfad ausgeschöpft
waren (`RESULTS_ref_weight.md`).

## Setup

Flux.2 Dev (NVFP4-Quantisierung) ist installiert:
`Flux.2 Dev\flux2-dev-nvfp4-mixed.safetensors` (UNet),
`Flux.2 Dev\mistral_3_small_flux2_fp4_mixed.safetensors` (CLIP/Text-Encoder,
Typ `flux2`), `Flux.2\flux2-vae.safetensors` (VAE). Graph-Form abgeleitet
aus einem vorhandenen, funktionierenden Nutzer-Workflow
(`user/default/workflows/Flux.2 Dev/TooReal Studio - Flux2 Dev NVFP4
img2img.json`) und erweitert von Einzelbild auf Fall 3s Zwei-Bild-Form
(Quellbild + Farbreferenz) via `ReferenceLatent`-Verkettung (generischer
ComfyUI-Core-Node, "chain multiple to set multiple reference images"):

```
positive: CLIPTextEncode -> ReferenceLatent(Quellbild) -> ReferenceLatent(Referenz)
negative: ConditioningZeroOut -> ReferenceLatent(Quellbild)   [Referenz NICHT im Negativ]
Output-Latent: leeres EmptyFlux2LatentImage (Quellgröße), NICHT das Quell-Latent selbst
```

`cfg=1.2`, `steps=28`, Sampler `dpmpp_sde`, `Flux2Scheduler` - aus dem
vorhandenen Workflow übernommen, nicht von Qwen portiert (anderes Modell,
andere Sampler-Kette). Graph-Verdrahtung vor der Auswertung verifiziert
(Referenz nur im Positiv-Pfad, Output-Latent ist leer, nicht Quell-Latent).

## Test 1: Volle Konditionierung (Quellbild + Referenz), n=3

Flux-nativer, sauberer Prompt (nicht Qwens bekannt-schlechte
"background"-Formulierung): *"Change only the woman's black leather dress
to match the blue material shown in the second reference image. Keep her
face, hair, skin, pose, bench, buildings, pavement, sky, lighting, camera
framing, and all background details unchanged."*

**3/3 PASS, visuell konsistent.** Kleid in allen drei Läufen zu Blau/Violett
umgefärbt (Material wirkt zusätzlich glatter/satinartiger), restliche Szene
(Himmel, Gebäude, Straße, Mülleimer, Bierflasche, Gesicht, Pose, Leggings,
Stiefel, Tasche) durchgängig unverändert und stabil zwischen den Seeds -
kein Ganzbild-Tint, kein Bleeding. **Der erste erfolgreiche
referenzbasierte lokale Farbwechsel dieser gesamten Session**, nachdem
jeder Qwen-Image-Edit-2511-Ansatz (Analyzer-Guidance, Negative-Prompt,
deterministisches Templating, Few-Shot/`temperature=0`, gewichtete
Referenz-Attention) gescheitert war.

## Test 2: Ablation ohne Referenzbild, gleicher Prompt (n=1)

Gleicher Seed (314001), gleicher Prompt ("...blue material..."), aber
**ohne** die Referenzbild-`ReferenceLatent` - nur Quellbild als Referenz.

**Ergebnis: Kleid färbt sich ebenfalls blau**, optisch mindestens
ebenso gesättigt wie bei voller Konditionierung. Das zeigt: der Text-Prompt
allein ("blue material") trägt bereits reale, möglicherweise dominante
Farbinformation - der spezifische Beitrag des Referenzbilds zur Farbe ist
durch Test 1 **nicht** belegt.

## Test 3 (entscheidend): kein Farbwort im Prompt, mit/ohne Referenz (n=1 je Variante)

Prompt ohne jede Farb-/Materialbezeichnung: *"Change only the woman's
black leather dress to match the appearance shown in the second reference
image. [...]"* - zwei Varianten, gleicher Seed (314001): mit
Referenzbild, ohne Referenzbild.

**Ergebnis: Kleid bleibt in BEIDEN Varianten vollständig SCHWARZ
(unverändert).** Kein sichtbarer Unterschied zwischen den beiden Bildern
und dem Originalfoto. Ohne dass der Text das Zielergebnis benennt, hat
Flux.2 Dev die Farbinformation in diesem Test **nicht** allein aus dem
Referenzbild übernommen.

## Codex' Bewertung (Zitat)

> Flux.2 Dev is a real locality improvement over Qwen Image Edit 2511 for
> this case: with a text prompt that explicitly names "blue material," it
> recolored the dress cleanly without scene bleed across n=3, while Qwen
> repeatedly bled color globally. However, the source-only ablation also
> recolored the dress blue, and the decisive no-color-name test produced
> no dress change with or without the swatch reference. Therefore this
> Flux.2 Dev graph demonstrates strong text-driven local editing, but does
> not demonstrate image-based color/material transfer from the reference
> image, which is the project's harder requirement.

## Test 4 (Bestätigung): fotografische statt Flat-Color-Referenz, kein Farbwort im Prompt

Einwand aus einem separaten VTON-Schwesterprojekt
(`G:\ComfyUI-Easy-Install\ComfyUI\user\default\workflows\VTON`, siehe
[[project_vton_sibling_history]]): die meisten Referenz-Mechanismen
erwarten ein Produktfoto mit neutralem Hintergrund, keinen abstrakten
Farbfleck. Test 3 wiederholt mit einem echten Foto aus dem ComfyUI-
Input-Ordner (`new-jitrois-kill-jumpsuit-red-stretch-leather-woman-
attitude.png` - roter Stretch-Leder-Overall, sauberer Studio-Hintergrund),
gleicher Seed, gleicher Prompt ohne Farb-/Materialnennung, mit/ohne
Referenz.

**Ergebnis: Kleid bleibt wieder in BEIDEN Varianten vollständig
schwarz.** Identisch zum Flat-Swatch-Ergebnis. Das entkräftet den Einwand
"vielleicht war nur das Testbild ungeeignet" - auch mit einem sauberen,
fotografischen Produktbild überträgt dieser `ReferenceLatent`-Aufbau keine
Bildinformation, wenn der Prompt das Ziel nicht benennt.

## Test 5: `reference_latents_method`-Sweep (Nutzerfrage: "Flux.2 Dev doch besser?")

Vor dem Start des Qwen-Attention-Bias-Spikes gegengeprüft: verwendet Test 3/4
den Standardwert (`ref_latents_method` implizit "offset")? Falls ein
anderer Verkettungsmodus die Referenz tatsächlich als Bildinformationsquelle
nutzt, wäre Flux.2 Dev doch der bessere Kandidat. Codex bestätigte vorab:
falls diese Wiederholung negativ bleibt, ist Qwen der sauberere Spike-Kandidat
(Referenzkonsum dort bereits bewiesen, hier nicht).

Offizieller Core-Node `FluxKontextMultiReferenceLatentMethod`
(`comfy_extras/nodes_flux.py:153-181`, `is_experimental=True`) bietet
`reference_latents_method` mit den Optionen `offset` (Default), `index`,
`uxo/uno`, `index_timestep_zero`. Kein Custom-Code nötig - vor `CFGGuider`
eingefügt, gleicher Seed (314001), gleicher Prompt ohne Farbwort, gleiche
Flat-Swatch-Referenz wie Test 3.

| Methode | Ergebnis |
|---|---|
| `offset` (Default, = Test 3) | Kleid schwarz, Szene korrekt erhalten |
| `index` | Kleid schwarz, Szene korrekt erhalten - identisch zum Default |
| `index_timestep_zero` | **Bildidentität komplett zerstört** (andere Person, andere Szene, anderes Outfit - keine lokale Bearbeitung mehr, sondern Neugenerierung) |
| `uxo/uno` | **Generierung komplett kollabiert** (flächige Rauschausgabe, keine erkennbare Szene) |

Keine der vier verfügbaren `reference_latents_method`-Varianten zeigt
echten Bildreferenz-Transfer; zwei davon (`index_timestep_zero`, `uxo/uno`)
sind für diesen Anwendungsfall zusätzlich strukturell unbrauchbar
(Identitätsverlust bzw. Totalkollaps). Der "vielleicht war nur der
Verkettungsmodus falsch"-Einwand ist damit ausgeräumt.

## Fazit

**Bestätigt:** Flux.2 Dev löst - zumindest in diesem Setup - das
Lokalitätsproblem, an dem Qwen Image Edit 2511 in dieser gesamten Session
wiederholt gescheitert ist, sofern der Text-Prompt das Zielergebnis
explizit benennt.

**Widerlegt, mit zwei unabhängigen Referenzbild-Typen (Flat-Swatch UND
echtes Produktfoto):** dass Flux.2 Dev Bildinformation überträgt, die der
Text nicht ausdrücken kann - genau die Fähigkeit, die dieses Projekt für
Referenzbild-Rollen (`garment_reference`, `material_style_reference` etc.)
eigentlich braucht. Wenn der Prompt das Ziel nicht benennt, bleibt die
Referenz in diesem `ReferenceLatent`-Aufbau wirkungslos - unabhängig davon,
ob die Referenz ein abstraktes Farbfeld oder ein sauberes fotografisches
Produktbild ist. Der "vielleicht war nur das Testbild ungeeignet"-Einwand
ist damit ausgeräumt.

Codex' finale Zusammenfassung: "Flux.2 Dev is a useful locality datapoint
but not a solved reference-transfer path. [...] this Flux.2 Dev
`ReferenceLatent` graph does not demonstrate genuine image-based
garment/material transfer; it only demonstrates strong text-driven local
editing." Für diese Graph-Verdrahtung gibt es keinen offensichtlichen
"Stärke"-Hebel wie beim Qwen-Attention-Patch - weiteres Herumprobieren an
Guidance-Knoten wäre wieder empirisches Herumtasten ohne Mechanismus.
**Vollständig abgeschlossen, nicht weiterverfolgt.**

Damit ist dieser konkrete `ReferenceLatent`-Aufbau für Flux.2 Dev
**abgeschlossen, nicht weiterverfolgt** (Codex: "No more cheap test is
likely to change the conclusion without changing the mechanism"). Reale
Bild-basierte Referenzübertragung war ohnehin nie das eigentliche Problem
dieser Session (Fall 3 nutzte selbst bei Qwen nur eine Farbnennung im
Prompt) - aber dieser Test zeigt, dass Flux.2 Dev diese Lücke ebenfalls
nicht automatisch schließt.

**Empfohlener nächster Schritt (Codex, nach Test 4, bestätigt nach Test 5):**
SAM3-als-Attention-Hint-Patch auf dem Qwen-Pfad (siehe `RESULTS_ref_weight.md`)
- Begründung: Qwen konsumiert das Referenzbild nachweislich (reagiert
darauf), sein Problem ist Routing/Lokalität. Flux.2 Dev hat das
umgekehrte Problem: Lokalität funktioniert, aber die Referenz wird in
keinem der vier getesteten Verkettungsmodi konsumiert (Test 5). Ein
Attention-Bias-Patch kann vorhandene Referenz-Attention nur umlenken,
nicht erzeugen - Flux.2 Dev scheidet damit als Spike-Ziel aus, nicht nur
als vorläufige, sondern als abschließende Einschätzung für diesen
Modellzweig. Ein Schwesterprojekt ([[project_vton_sibling_history]]) hat
dieselbe Problemklasse bereits 2+ Monate bearbeitet und keine generische
Architektur gefunden - Erwartungshaltung entsprechend gedämpft:
realistisches Nahziel ist ein einzelner kontrollierter Nachweis, keine
vollständige Lösung.

**Umfang/Scope-Hinweis:** Dies ist ein Fähigkeits-Smoke-Test auf einem
komplett anderen Modellzweig (eigene UNet/CLIP/VAE/Sampler-Kette), keine
Router-fertige Implementierung. Eine Adoption für den Router (z. B. als
dritter, lazy-geschalteter Edit-Zweig neben Qwen und Z-Image) wäre eine
eigenständige Architekturentscheidung mit eigenem Codex-Abstimmungsprozess,
VRAM-Tests und Rollback-Planung - hier nicht begonnen.
