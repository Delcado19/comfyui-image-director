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

## Fazit

**Bestätigt:** Flux.2 Dev löst - zumindest in diesem Setup - das
Lokalitätsproblem, an dem Qwen Image Edit 2511 in dieser gesamten Session
wiederholt gescheitert ist, sofern der Text-Prompt das Zielergebnis
explizit benennt.

**Nicht bestätigt, sondern widerlegt für diesen konkreten Aufbau:** dass
Flux.2 Dev Bildinformation überträgt, die der Text nicht ausdrücken kann -
genau die Fähigkeit, die dieses Projekt für Referenzbild-Rollen
(`garment_reference`, `material_style_reference` etc.) eigentlich braucht.
Wenn der Prompt das Ziel nicht benennt, bleibt die Referenz wirkungslos.

Damit ist dieser konkrete `ReferenceLatent`-Aufbau für Flux.2 Dev
**abgeschlossen, nicht weiterverfolgt** (Codex: "No more cheap test is
likely to change the conclusion without changing the mechanism"). Reale
Bild-basierte Referenzübertragung war ohnehin nie das eigentliche Problem
dieser Session (Fall 3 nutzte selbst bei Qwen nur eine Farbnennung im
Prompt) - aber dieser Test zeigt, dass Flux.2 Dev diese Lücke ebenfalls
nicht automatisch schließt.

**Verbleibende, nicht getestete Wege** (strukturell, laut Codex):
- Masking/Region-Conditioning (mit Qwen oder Flux) - weiterhin der einzige
  bewiesene Weg zur Lokalität ohne Text-Abhängigkeit.
- Ein anderer, tatsächlich referenz-fähiger Modellzweig/Mechanismus (nicht
  näher spezifiziert, nicht getestet).
- Fotografische/materialbasierte Referenz statt Flat-Color-Swatch - als
  eigenständiger Charakterisierungstest, nicht als Fix-Behauptung.

**Umfang/Scope-Hinweis:** Dies ist ein Fähigkeits-Smoke-Test auf einem
komplett anderen Modellzweig (eigene UNet/CLIP/VAE/Sampler-Kette), keine
Router-fertige Implementierung. Eine Adoption für den Router (z. B. als
dritter, lazy-geschalteter Edit-Zweig neben Qwen und Z-Image) wäre eine
eigenständige Architekturentscheidung mit eigenem Codex-Abstimmungsprozess,
VRAM-Tests und Rollback-Planung - hier nicht begonnen.
