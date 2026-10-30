# Datamodel van Golf Score

Wat de app bewaart, per object en per veld: wat het betekent, of het **opgeslagen**
wordt of **afgeleid** (dan rekent de app het steeds opnieuw uit en is een opgeslagen
waarde hooguit informatief), en wie het schrijft.

Alles staat in de `localStorage` van de browser, onder sleutels die met `golf_`
beginnen (zie het laatste hoofdstuk). Een backup (`exportAllRounds`, `exportAllClubs`)
bevat dezelfde objecten als JSON.

Wie een veld toevoegt of van betekenis verandert, past ook aan:
`zetRondeRecht` / `keurRonde` (rondes) of `validateImportedClubData` (clubs), een geval
in `tests/test-importkeuring.py`, `vol()` en `RONDEVELDEN`/`HOLEVELDEN` in
`tests/test-ronde-velden.py`, en dit bestand. Zie ook `tests/CONTROLELIJST.md`.

---

## Ronde

Eén gespeelde, lopende of geplande ronde van één speler. Twee spelers samen zijn twee
rondes met dezelfde `date` en `time`. Opgeslagen als lijst onder `golf_rounds`.

Een ronde ligt vast vanaf de start: par, SI, CR, SR en de slagverdeling worden bij het
starten gekopieerd uit de baan en de tee, en veranderen niet als de baan later wordt
aangepast (`startRoundConfirmed`, `buildRoundHoles`).

| Veld | Betekenis | Soort | Geschreven door |
|---|---|---|---|
| `id` | Unieke sleutel (getal of tekst). Rondes worden altijd op id gezocht, nooit op plaats in de lijst. | opgeslagen | `startRoundConfirmed`, import |
| `date` | Speeldatum, `JJJJ-MM-DD`. | opgeslagen | start, herplannen, Bewerken |
| `time` | Starttijd, `UU:MM`, of `null`/leeg. Samen met `date` het tijdstip; twee rondes van één speler mogen niet hetzelfde tijdstip hebben. | opgeslagen | idem |
| `player` | Naam van de speler. De handicap wordt alleen berekend voor de speler die bovenin Start staat. | opgeslagen | start, Bewerken, hernoemen |
| `hcp` | Handicap Index waarmee de baanhandicap is berekend (die gold bij de start). | opgeslagen | start |
| `gender` | `Heren` of `Dames`: welke tees en ratings gelden. | opgeslagen | start |
| `club` | Clubnaam zoals bij de start (sleutel in `golf_clubs`). | opgeslagen | start, hernoemen met "Alles aanpassen" |
| `clubShort` | Korte clubnaam voor de lijst. | opgeslagen | idem |
| `track` | Baannaam (of lusnaam). Alleen samen met `club` uniek: twee clubs kunnen een baan met dezelfde naam hebben (`holeSleutel`). | opgeslagen | idem |
| `tee` | Teenaam. | opgeslagen | idem |
| `lus` | `true` als de ronde op een wedstrijdlus is gespeeld; anders afwezig. | opgeslagen | start |
| `CR`, `SR` | Course Rating en Slope Rating van de tee bij de start. | opgeslagen | start |
| `PAR` | Par van de ronde (som van de holes bij de start). Een bewuste kopie: statistieken bewegen niet mee als de baan verandert. | opgeslagen | start |
| `chcp` | Baanhandicap (course handicap) waarmee is gespeeld, na eventueel +/− of percentage. Kan ontbreken bij een ingelezen ronde. | opgeslagen | start |
| `chcpPct` | Wedstrijdpercentage, alleen als `chcp` precies dat percentage van de berekende baanhandicap is (0 < pct < 100); anders afwezig. | opgeslagen | start (`percentageVan`) |
| `qualifying` | Telt mee voor handicap en statistiek (samen met: afgerond, zie `meetelFilter`). Een lus staat standaard uit. | opgeslagen | start, Bewerken |
| `pcc` | Playing Conditions Calculation zoals ingevuld (18 holes −1..3; 9 holes de waarde die de NGF-app toont, −0,5..1,5; de app telt bij 9 holes daar de helft van, zoals de NGF). `null` = niet ingevuld. | opgeslagen | Vaststellen |
| `sdFinal` | Vastgesteld dagresultaat (overgenomen uit de officiële app). Gaat altijd voor op de eigen berekening. `null` = niet vastgesteld (dan het oranje driehoekje). | opgeslagen | Vaststellen |
| `sd` | Dagresultaat. **Afgeleid** (`computeSD`/`effectiveSD`); een waarde in een bestand is informatief en wordt bij import weggegooid. | afgeleid | — |
| `note` | Notitie; afwezig als leeg. | opgeslagen | Start, Bewerken |
| `total` | Som van de ingevulde scores. Bijgehouden bij opslaan, maar het scherm rekent uit de holes. | opgeslagen (afgeleid) | `buildRoundEntry` |
| `holesCount` | Aantal holes; moet gelijk zijn aan `holes.length` (de keuring weigert anders). | opgeslagen (afgeleid) | `buildRoundEntry` |
| `currentHole` | Hole waar je was (0-based), om een gepauzeerde ronde daar te hervatten. | opgeslagen | scorekaart |
| `started` | `true` voor elke ronde die is aangemaakt. | opgeslagen | start |
| `holes` | Lijst van holes, zie hieronder. Een ronde zonder holes weigert de keuring. | opgeslagen | start, scorekaart |
| `totalStb`, `playedCount` | Oude velden; worden bij opslaan verwijderd. Stableford komt altijd uit de holes (`stbTotaal`). | — | — |
| `_justImported` | Alleen in het geheugen/de opslag zolang een ingelezen ronde nog niet met "Sla op" is bewaard; telt dan nergens mee. | tijdelijk | import, `clearImportedFlag` |

**Af** is geen veld maar een afleiding (`isRondeAf`): elke hole heeft een score.
**Meetellen** voor handicap en statistiek (`meetelFilter`) vraagt daarnaast: qualifying,
niet de lopende ronde, en niet `_justImported`; voor de handicap ook een dagresultaat
(`meetelVoorHandicap`). **Gepland**: niet af, met een tijdstip in de toekomst en niet de
lopende ronde (`geplandeMomenten`). **Gepauzeerd**: niet af en niet gepland.

## Hole (in een ronde)

| Veld | Betekenis | Soort |
|---|---|---|
| `id` | Holenaam (tekst, bijvoorbeeld `"7"` of `"A3"`), uit `holeIds` van de baan. | opgeslagen |
| `par` | Par van de hole, van de tee bij de start (3..6). | opgeslagen |
| `si` | Stroke index van de hole (1..18), van de tee. | opgeslagen |
| `phcp` | **Slagen op deze hole** (niet de playing handicap!): de verdeling van `chcp` over de holes (`distributeChcp`). Som over de holes = `chcp`. | opgeslagen |
| `ppar` | Persoonlijke par = `par + phcp`. Afgeleid, maar opgeslagen; het scherm rekent hem uit (`pparVan`). | opgeslagen (afgeleid) |
| `score` | Bruto slagen, of `null` = nog niet gespeeld. | opgeslagen |
| `putts` | Aantal putts (0..score−1), of afwezig/`null` als putts niet worden bijgehouden. | opgeslagen |
| `_initScore` | Score op het moment dat je de hole koos; voor "lang drukken op −". Wordt bij export en backup weggelaten. | tijdelijk |

Stableford, netto score en de aangepaste bruto score (AGS, net double bogey) staan
niet in de hole: ze worden uit `score`, `par` en `phcp` berekend (`stbFor`, `agsFor`).
De AGS rekent met de **volledige** baanhandicap, ook bij een wedstrijdpercentage
(`volleSlagen`, `agsSlagen`).

---

## Club

Opgeslagen als object onder `golf_clubs`: clubnaam → club. Clubnamen zijn uniek;
baannamen en lusnamen niet (over clubs heen).

| Veld | Betekenis |
|---|---|
| `club` | Clubnaam (gelijk aan de sleutel). |
| `shortName` | Korte naam voor lijsten. |
| `courses` | Object: baannaam → baan. |

## Baan (en wedstrijdlus)

| Veld | Betekenis |
|---|---|
| `holeIds` | Lijst holenamen in speelvolgorde. Een baan zonder holes wordt bij het laden weggehaald. |
| `tees` | Object: `Heren`/`Dames` → teenaam → tee. |
| `lus` | `true` voor een wedstrijdlus (samengesteld uit holes van andere banen). |
| `bron` | Alleen bij een lus: lijst `{baan, idx}` — waar elke hole vandaan komt. |
| `bronStempel` | Alleen bij een lus: vingerafdruk van de berekende holes en tees bij het maken (`lusStempel`). Wijkt de huidige berekening af, dan is de lus "verouderd" (`lusStatus`). |

Par en SI horen bij de **tee**, niet bij de baan: een baan heeft geen `holes` en geen
`PAR` (bewaakt door `tests/controle-baanmodel.js`).

## Tee

| Veld | Betekenis |
|---|---|
| `CR` | Course Rating. |
| `SR` | Slope Rating. |
| `holes` | Lijst `{par, si}`, even lang als `holeIds` van de baan. |

---

## Overige opslag (`localStorage`)

Elke sleutel staat ook in het register `OPSLAGSLEUTELS` in de app, met wat er bij "Alles
wissen" mee gebeurt: wissen, houden (de plek) of oud (bij elke start opgeruimd). Een nieuwe
sleutel hoort in beide; `tests/test-opslagsleutels.py` faalt anders.

| Sleutel | Inhoud |
|---|---|
| `golf_rounds` | Alle rondes (lijst). |
| `golf_clubs` | Alle clubs (object). |
| `golf_active_id`, `golf_game2_id` | Id van de lopende ronde van speler 1 en 2. |
| `golf_default_club`, `golf_home_club`, `golf_fav_clubs` | Gekozen club, thuisclub, favorieten. |
| `golf_profile_name`, `golf_profile_hcp`, `golf_gender` | Speler bovenin Start. |
| `golf_profile_name2`, `golf_profile_hcp2`, `golf_player2_visible` | Speler 2 op Start. |
| `golf_fav_player2_name`, `golf_fav_player2_hcp`, `golf_default_player2_name`, `golf_default_player2_hcp` | Favoriete en standaard speler 2. |
| `golf_setup_date`, `golf_setup_time`, `golf_setup_date_day` | Datum en tijd op Start (alleen dezelfde dag hergebruikt). |
| `golf_low_hi` | Handmatig ingevulde Low HI (leeg = afleiden). |
| `golf_last_backup_date`, `golf_last_backup_ts`, `golf_last_backup_count`, `golf_backup_inhoud`, `golf_backup_onzeker`, `golf_backup_fingerprint`, `golf_backup_fp_bij_backup`, `golf_rounds_changed` | Wat er in de laatste rondebackup zat (voor de backupmelding). |
| `golf_clubs_backup_date`, `golf_clubs_backup_fingerprint`, `golf_clubs_fingerprint` | Idem voor clubs. |
| `golf_storage_id`, `golf_opslag_kenmerk`, `golf_kenmerk_gevraagd` | Code en naam van deze installatie (in backupnamen). Blijven staan bij "Alles wissen": ze horen bij de plek, niet bij de gegevens. |
| `golf_fouten` | De laatste vijf onverwachte fouten (foutvanger). |
| `golf_theme`, `golf_bad_weather`, `golf_scorecard_symbols`, `golf_progress_indicator`, `golf_auto_next`, `golf_track_putts`, `golf_putts_stats`, `golf_whs_volgen`, `golf_lowhi_graph`, `golf_actions_always_visible`, `golf_min_rounds_stat` | Schakelaars in Instellingen. |
| `golf_set_sections`, `golf_stats_grp_*`, `golf_lussen_open`, `golf_seen_low_hi_*` | Wat er open of dicht staat en wat al is gezien. |
| `golf_export_folder_db` | Naam van de IndexedDB met de gekozen exportmap. |
| `golf_round_limit`, `golf_quick_grouping`, `golf_archive_years_closed`, `golf_backup_reminder_days`, `golf_backup_reminder_rounds`, `golf_backup_reminder_shown`, `golf_stats_handicap_always`, `golf_clubs_changed` | Oude sleutels; worden bij elke start opgeruimd. |

Daarnaast bestaat er toestand die alleen in het geheugen leeft (de lopende ronde
`game`, keuzes op Start in `sel`/`sel2`, open/dicht-standen in `window._…`); die staat
in sectie 3 (TOESTAND) en bij de sectie die hem gebruikt.
