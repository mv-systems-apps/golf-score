# Controlelijst bij elke wijziging aan Golf Score

De app is functioneel rijk geworden. Een wijziging op één plek kan iets raken op een
andere plek. Deze lijst is er om uit te breiden zonder dat ongemerkt te doen.

Bij **elke levering** staat per vraag één regel met het antwoord. Geen antwoord is ook
een antwoord: dan staat er "niet gedaan, omdat …".

## De zes vragen

1. **Wat mag hierdoor nooit veranderen, en is dat voor alles getest?**
   Niet één geval repareren, maar de regel controleren over alle gevallen heen. Zie de
   vaste regels hieronder: raakt de wijziging er een, dan draait de test van die regel,
   en komt er zo nodig een handeling of veld bij in die test.
2. **Is het getest met de eigen gegevens, vanaf de vorige versie?**
   `test-echte-gegevens.py` en `test-backup-overstap.py`. Verzonnen gegevens zijn te netjes.
3. **Is er op de knoppen getikt, of is de functie aangeroepen?**
   Een aanroep slaat de bevestiging, het venster en de volgorde over. Nieuwe routes
   komen in `test-echte-knoppen.py` of krijgen een eigen test met echte tikken.
4. **Faalt de nieuwe test op de vorige versie?**
   Een test die altijd slaagt bewijst niets.
5. **Welke nieuwe risico's brengt de wijziging mee?**
   Elke reparatie kan iets nieuws openen. Benoemen, en afdekken of bewust laten liggen.
6. **Wat is niet getest, en waarom niet?**

## Vaste regels en de test die ze bewaakt

Dit zijn de regels die over de hele app gelden. Een nieuwe functie mag er geen breken.

| Regel | Test |
|---|---|
| Het startscherm verandert nooit een lopende ronde | `test-startscherm-lopende-ronde.py` (elke bediening van het startscherm) |
| De andere schermen veranderen nooit een lopende ronde | `test-lopende-ronde-andere-schermen.py` (Rondes, Clubs, Instellingen, Statistiek) |
| Een ronde ligt vast vanaf de start: eigen par, SI, CR, SR en slagen | `test-wedstrijdlus-bron.py`, `test-startscherm-clubs.py` (deel 12) |
| Geen veld van een ronde valt onderweg weg, en er komt niets bij | `test-ronde-velden.py` |
| Een afgeronde ronde verandert alleen als je die ronde zelf bewerkt (één bewuste uitzondering sinds 039: een tijd als '9:00' of met spaties wordt bij het lezen '09:00', en bij de eerstvolgende schrijfactie zo opgeslagen; na de update kan de backupregel daardoor één keer '1 gewijzigd' melden) | `test-wedstrijdlus-bron.py`, `test-echte-gegevens.py`, `test-rondeverlies.py` |
| Iets definitief verwijderen kan nooit met één tik | `test-een-tik-wist-niets.py` (tikt in 19 standen op alles wat zichtbaar is, ruim 400 tikken) |
| Opschonen haalt nooit iets weg dat de handicap, de Low HI of een ESR-verlaging van een speler verandert, nu of bij een volgende ronde; nooit een geplande, gepauzeerde of niet opgeslagen ronde, en niets zolang er een ronde openstaat; eerst een archief met precies die rondes (ook hun inhoud), dat ze met Toevoegen exact terugzet en geen eerder archief overschrijft | `test-opschonen.py` (12 jaar met caps en ESR; 8 geschiedenissen × 120 volgende rondes), `mutaties-opschonen.py` (9 bewuste fouten, alle gevangen) |
| Backup maken en terugzetten geeft exact dezelfde rondes en clubs terug (behalve een tijd als '9:00', die als '09:00' terugkomt; 039) | `test-ronde-velden.py` (rondes), `test-clubs-heen-en-terug.py` (clubs, met het eigen bestand) |
| Een bestand dat niet deugt verandert niets | `test-clubs-heen-en-terug.py` (clubs), `controle-inlezen.js` (rondes) |
| Geen handeling haalt ingevulde scores weg of vervangt ze nadat de opslag ervóór is mislukt | `test-opslagstoring.py` (scores invoeren), `test-opslagstoring-handelingen.py` (afronden, opslaan vanaf de rondekaart, wisselen van speler, corrigeren met twee spelers) |
| Onleesbare gegevens worden nooit overschreven, behalve door een backup terug te zetten na bevestiging | `test-corrupt.py` (niets wordt weggeschreven), `test-herstel-na-onleesbaar.py` (terugzetten lukt, annuleren laat alles staan, al het andere blijft geweigerd; rondes en clubs) |
| De app start altijd op, wat er ook in de opslag staat: een element dat geen ronde of club kan zijn wordt apart gezet en gemeld, de goede gegevens blijven zichtbaar en er wordt niet overheen geschreven | `test-misvormde-opslag.py`, `test-keuring-bij-laden.py` (ook velden van het verkeerde soort: speler, par, slagverdeling, score; 25 soorten misvormde rondes en clubs naast de eigen gegevens, alle zes tabbladen; herstel met echte tikken: alleen het beschadigde element weghalen, met een lopende, geplande en ingelezen ronde erbij; idem voor clubs) |
| Wat het scherm wijzigt, geldt ook voor de lopende ronde in het geheugen: een nieuwe naam met 'Alles aanpassen' gaat mee, en jouw keuze voor qualifying komt terug zodra je na een lus weer een gewone baan kiest | `test-naam-en-lus-qualifying.py`, `test-tekst-en-herplan.py` (herplannen na een lus; echte tikken: naam wijzigen tijdens een ronde en doorspelen; lus gekozen door de app, lus zelf aangetikt, schakelaar omgezet op de lus) |
| Een onverwachte fout blijft niet stil: de algemene foutvanger meldt hem (één venster tegelijk), bewaart de laatste vijf onder Instellingen, negeert fouten van buiten de app en raakt zelf geen rondes of clubs aan | `test-foutvanger.py` (fout bij een tik, in een uitgestelde en in een asynchrone actie; extensie, vreemd script, afgebroken delen; gewone sessie met eigen gegevens geeft geen melding) |
| Een export die aantoonbaar mislukt, wordt gemeld en verschuift de backupstand niet; valt de export terug van de exportmap op Downloads, dan lees je dat | `test-export-mislukt.py` (alle rondes, alle clubs, één ronde, één club, dagresultaten; download geblokkeerd, exportmap onbereikbaar, exportmap werkt) |
| Kan de browser niets bewaren, dan zegt de app dat: bij het opstarten, vóór het starten van een ronde (met de keuze om toch te spelen) en op de scorekaart | `test-opslag-alleen-geheugen.py` (schrijven geweigerd, opslag niet toegankelijk; met gewone opslag blijft alles stil) |
| Het scherm en de gegevens lopen niet uiteen: een nieuwe club zonder naam komt niet in de opslag, en een knop op een rondekaart raakt de ronde van die kaart, ook na een wijziging in een ander tabblad | `test-kleine-koppelingen.py` (ook als controle: speler 2 na afronden, tee en geslacht bij de gebruikte CR/SR, datum en tijd zoals in beeld) |
| Een update die bij slecht bereik niet compleet binnenkomt, breekt de app offline niet: zonder golf-score.html wordt de update afgebroken en blijft de vorige versie; een ontbrekend pictogram komt uit de vorige kopie | `test-sw-update-offline.py` (echte webserver en service worker op een kopie van 'uit'; offline = server weg) |
| Golf Score ruimt alleen eigen caches op (golf-score-…), nooit die van andere apps op dezelfde origin; een update of de opruimknop tijdens een lopende ronde laat altijd een complete, werkende offline-kopie achter, en geen score gaat verloren | `test-sw-ronde-en-update.py` (zes scenario's rond offline, update en online; opruimknop zonder bereik, met wegvallende verbinding en geslaagd, steeds gevolgd door een offline start) |
| Een nieuwe versie is beschikbaar zonder actief te worden: ze wacht tot je op de melding tikt (of de app helemaal dicht is geweest); de app herlaadt nooit vanzelf; een tik ververst niet als de browser niets bewaart of de ronde niet kan worden opgeslagen, en draait een onbevestigde scoretik eerst terug | `test-sw-gecontroleerde-update.py` (lopende ronde op het invoerscherm, wachtende tik, geen opslag, offline tikken, wegvallende verbinding, zonder tik na sluiten) |
| De updatecontrole bekijkt precies de cache van de actieve service worker (die noemt hem zelf); een achtergebleven oudere cache geeft geen onterechte balk, een wachtende versie en een nieuwe app in de actieve cache worden gemeld | `test-sw-actieve-cache.py` (één cache, restcache vóór de actieve, wachtende versie, achtergrondverversing) |
| De service worker onderschept alleen de eigen appbestanden (ook navigaties) en leest alleen uit de eigen cache: nooit uit die van Events, Trends of een wachtende nieuwe versie; ontbrekende bijbestanden bij installeren komen alleen uit eerdere Golf Score-caches | `test-sw-afgeschermd.py` (drie apps op één origin, vreemde caches met /golf-score/-adressen, wachtende versie) |
| De cache bevat alleen de appbestanden, elk één keer (ook na adressen met een toevoeging); een vers verzoek (?verversen) gaat naar het netwerk en wordt niet bewaard; nergens eindeloos wachten (eigen pagina 3 s met bewaarde app, anders 10 s); zonder netwerk en cache altijd een geldig antwoord; de achtergrondverversing komt in de cache | `test-sw-eigen-bestanden.py` (slecht bereik: server die niet antwoordt; geen bereik; ontbrekende bestanden in de cache) |
| Een update installeert altijd haar eigen app, ook binnen de 10 minuten dat GitHub Pages een bestand laat bewaren; een mislukte update laat geen halve cache achter en de vorige kopie blijft werken | `test-sw-verse-installatie.py` (server met Cache-Control: max-age=600; update direct na openen; update waarbij golf-score.html niet binnenkomt; daarna offline) |
| Bij slecht of geen bereik opent de geïnstalleerde app direct uit de opslag, ook via een adres met een toevoeging achter het vraagteken en na verversen; een nieuwe versie ophalen blijft via het netwerk gaan | `test-sw-slecht-bereik.py` (server die niet antwoordt en server die weg is) |
| Golf Score, Trends en Events doen hetzelfde (apps-basis/conventies.md, §3): de cachenaam is een teller (`golf-score-v` + CACHE_VERSION) die omhoog gaat zodra de service worker wijzigt; staat er een verse kopie van de pagina, dan krijgt de app meteen het bericht `kopieVernieuwd` en toont ze de melding; de achtergrondverversing van de pagina gaat met no-cache, ook binnen de 10 minuten van GitHub Pages; een installatie op een verbinding die blijft hangen loopt binnen 45 s af en laat de vorige versie staan | `test-sw-gelijk-met-buren.py` (echte webserver; cachenaam en script, bericht en melding in een tweede venster, max-age=600, installatie op een server die niet antwoordt) |
| Een mislukte update raakt de draaiende versie niet: de service worker haalt eerst alle bestanden op en schrijft pas weg als golf-score.html binnen is, ook als CACHE_VERSION niet is verhoogd (dezelfde cache) | `test-sw-halve-update.py` (echte webserver; golf-score.html geeft 500, het icoon is gewijzigd) |
| Geen verborgen invoerveld dat de app alleen vult en nooit leest | `test-dode-velden.py` (statisch, op golf-score.html) |
| Wat je ziet, wordt uitgerekend uit de holes: het Stableford-totaal en de netto par per hole worden niet overgenomen uit een opgeslagen (mogelijk ontbrekend of verouderd) veld | `test-afgeleide-waarden.py` (rondekaart, Gem. Stb, CSV-export, netto dubbel bogey op een ronde zonder ppar) |
| Een mislukte import zegt waarom, in gewone taal: een onleesbaar bestand, of wat er aan de inhoud mankeert. Een fout in de app tijdens het inlezen wordt niet als 'ongeldig bestand' gemeld maar gaat naar de foutvanger | `test-importmeldingen.py` (11 rondebestanden en 4 clubbestanden via de knoppen; nagebootste fout in de keuring) |
| Mislukt het opslaan midden in een handeling, dan blijft alles zoals het was: geen nieuwe of andere ronde zolang de lopende niet is bewaard, geen nieuwe naam in het profiel, geen verwijzing naar een club die niet is opgeslagen | `test-mislukt-opslaan-terugdraaien.py` (nieuwe ronde starten, andere ronde laden, 'Alles aanpassen', club hernoemen; en een start die niet kan worden opgeslagen laat scherm, geheugen en opslag ongewijzigd bij één speler, twee spelers, corrigeren en herplannen) |
| saveActiveRound() geeft altijd expliciet true of false terug; een lege ronde overschrijft nooit een opgeslagen ronde met scores, en die weigering laat afronden en laden niet doorgaan | `test-lege-ronde-overschrijft-niet.py` (terugmelding, afronden en een andere ronde laden met een leeg spel) |
| Een naam is tekst: wat je intypt staat overal letterlijk zo in beeld, en wordt nergens als HTML of script uitgevoerd | `test-namen-per-negen-en-analyse.py` (negen-tabbladen, Per negen, aanbeveling in de spelanalyse), `test-namen-met-tekens.py` (tee- en holenamen, via de echte editor, alle schermen), `test-velden-als-tekst.py`, `test-tekst-en-herplan.py` (datum en SI rechtstreeks uit de opslag) (alle tekstvelden van rondes en clubs, in vijf vormen, via de opslag en via de echte import; knoppen met leestekens in de naam blijven werken) |
| Een naam blijft ook buiten het scherm tekst: in de startmelding, in de CSV (een naam die met = + - of @ begint krijgt een ' en wordt geen formule) en in de agenda (geen eigen regeleinden) | `test-veilige-tekst-export.py` (teenaam als HTML bij een onvolledige tee; speler, club, korte naam, baan, tee en holenaam met formuletekens; gewone namen en getallen blijven gelijk; clubnaam met losse \r in de agenda) |
| Een uitzonderlijke score (ESR) gaat uit van het verschil tussen het onafgeronde dagresultaat en de index, zonder rekenruis: precies 7,0 of 10,0 beter telt mee (regel 5.9, 2024) | `test-esr-onafgerond.js` (grensgevallen, 3000 reeksen nagerekend in hele getallen tegen de index na de cap, één doorloop gelijk aan per ronde opnieuw) |
| Een wedstrijdpercentage gaat over de onafgeronde course handicap en wordt daarna rekenkundig afgerond (regel 6.2, 2024); +, − en het percentage begrenzen de baanhandicap op −15 t/m 90, niet op 54 | `test-percentage-en-grenzen.py` (echte tikken op %, −, + en het keuzevenster, speler 1 en 2, plushandicap, CH 69) |
| Twee vensters tegelijk: na een wijziging elders neemt een venster de stand uit de opslag over (geen oude stand terugschrijven, een elders afgeronde ronde staat hier niet meer open), en open vensters houden vast aan de ronde, niet aan de plaats in de lijst. Clubs: zonder open editor neemt het venster ze over; met een open editor weigert het opslaan tot je ververst | `test-twee-vensters.py` (scores in beide vensters, afronden in het ene, verwijderen na een verschoven lijst met echte tikken), `test-review-oktober.py` (clubs) |
| In de laatste 20 (handicap nu, verloop per ronde, statistiek) tellen alleen rondes met een dagresultaat; een dagresultaat mag −20,0 t/m 100,0 zijn; een onbevestigde tik wordt teruggedraaid zodra de app naar de achtergrond gaat of de pagina wordt verlaten | `test-handicapvenster-en-grenzen.py` |
| Soft en hard cap grijpen pas in vanaf 20 acceptabele scores (regel 5.7/5.8, 2024), en overal hetzelfde: handicap nu, 'Whs oud → nieuw' op de rondekaart en de gecapte lijn in de grafiek; een handmatige Low HI geldt overal | `test-caps-pas-vanaf-20.py` |
| Een uitzonderlijke score vergelijkt met de index die gold toen de ronde gespeeld werd, dus na soft/hard cap (regel 5.9, 2024); de index wordt per speeldag bijgewerkt: bij twee rondes op één dag gold bij beide de index van het begin van die dag (regel 5.4); de Low HI is de laagste eindstand van een speeldag in de 365 kalenderdagen ervoor, zoals hij gold, dus mét ESR-verlagingen (regel 5.7); handicap nu, Low HI, rondekaart, grafiek, Instellingen en wat-als komen uit één doorrekening (whsStand, die whsVerloop één keer draait); twee rondes op hetzelfde tijdstip staan overal in dezelfde volgorde (oudsteEerst) | `test-een-rekenroute.py` (300 willekeurige reeksen, gelijke tijdstippen, één doorrekening per scherm), `test-esr-en-lowhi-geldende-index.py`, `test-per-speeldag.py`, `test-handicapverloop.js` (400 reeksen tot 150 rondes, ook op dezelfde dag, venster van 365 dagen), `test-esr-onafgerond.js` (3000 reeksen, met caps), `test-whs-rekenkern.js` (deel 8) |
| Baanhandicap: bij 9 holes de halve index NIET afgerond (R&A-tekst van regel 6.1b, zoals de NGF; de USGA-afronding op een tiende van 142 gaf bij een echte ronde van 30-11-2025 15 waar de NGF 14 geeft); bij een ander aantal dan 9 of 18 de index naar rato (n/18), ook onafgerond, met een melding op het startscherm dat het geen officiële regel is | `test-baanhandicap-9-en-lus.py`, `test-whs-rekenkern.js` (deel 1, ook in hele getallen), `test-ags-volledige-baanhandicap.js` |
| Dagresultaat bij 9 holes: van de PCC die de NGF-app toont telt de helft (NGF, Wegwijs in Handicapping 2024: "½*PCC"); alle 36 qualifying rondes van Testspeler geven het NGF-dagresultaat | `test-pcc-9-holes-ngf.js`, `test-whs-rekenkern.js` (deel 4 in hele getallen, deel 8) |
| Wedstrijdpercentage en playing handicap: de ronde bewaart chcpPct alleen als de baanhandicap echt dat percentage is (niet bij 100%, niet na − en +, niet na een wissel van index of tee, ook bij speler 2); de keuring accepteert 0 < pct < 100 of leeg. Bij een afwijkende baanhandicap staat er 'Phcp 29 (85%)' of zonder percentage het verschil 'Phcp 29 (−5)'; bij een afgeronde qualifying ronde ook 'Stb 33 · Chcp 34 (100%)' (kaart, overzicht, gedeelde tekst). Gem. Stb en de nullers rekenen met de volle baanhandicap. Per negen toont AGS altijd | `test-stableford-volle-chcp.py`, `test-per-negen.py` |
| Minimum aantal rondes voor statistieken (Instellingen, standaard 3) geldt voor alle gemiddelden op Statistiek: per tee en bij de banen een streepje met het aantal erbij; een club zonder één baan boven de drempel staat er niet, en een lege categorie of groep Clubs ook niet (037); per par en per SI telt de drempel rondes, niet holes; Gem. Sd, Gem. Stb en Gem. putts bovenaan een streepje; het verloop per drie holes en per negen verdwijnt; de trend vraagt dat ook het blok vóór de laatste 5 het minimum haalt (max. 5); de spreiding vraagt minstens 3 én het minimum. De baananalyse op het clubtabblad heeft bewust geen minimum | `test-drempel-statistiek.py`, `test-clubs-onder-drempel.py` |
| Een import overschrijft geen ronde die nog loopt of op het scorescherm staat | `test-import-overschrijft-geen-lopende-ronde.py` |
| De aangepaste bruto score (net double bogey) rekent met de volledige, onbeperkte course handicap, ook als met een wedstrijdpercentage of +/− is gespeeld; bij een course handicap boven 54 is de hoogste holescore par + 5 (Rules of Handicapping 2024, regel 3.1b). Stableford en netto blijven op de gespeelde handicap | `test-ags-volledige-baanhandicap.js` (voorbeelden met de hand, 40.000 rondes tegen een eigen berekening in hele getallen, 20.000 rondes zonder bijstelling gelijk aan voorheen), `test-ags-in-beeld.py` (kaart, overzicht, deeltekst, CSV) |
| De Handicap Index rondt af op één decimaal, een exacte ,x5 naar boven; de caps rekenen in tienden zonder rekenruis | `test-afronding.js` (80.000 gemiddelden over elk aantal rondes, 132.861 combinaties van handicap en Low HI, de staffel 1 t/m 20) |
| De baanhandicap en het dagresultaat ronden een exacte helft naar boven af, zonder rekenruis; slagenverdeling, Stableford, aangepaste bruto score, ESR en plushandicaps kloppen met een tweede berekening | `test-whs-rekenkern.js` (ruim 166.000 controles tegen een narekening in hele getallen; deel 8 legt drie bevestigde keuzes vast: index bij 1–2 rondes (NGF-tabel), ESR tegen de index na de cap (142), de halve PCC bij 9 holes (144)) |
| Wat uit een bestand komt wordt gekeurd en rechtgezet vóór het opslaan; wat niet kan kloppen komt er niet in | `test-importkeuring.py` (42 onmogelijke rondes, 7 slordige, 7 clubgevallen, elk langs beide routes; de eigen backups ongewijzigd), `controle-inlezen.js` |
| Corrigeren of herplannen verandert niet wie de app als speler ziet; een niet-bevestigde tik komt nooit op de kaart van een ander | `test-speler-wissel-corrigeren.py`, `test-wachtende-tik.py` (laden, verwijderen, nieuwe ronde, backup terugzetten; annuleren, afronden van de correctie, spelerwissel en afronden met een tik in de wacht, Stableford van speler 2) |
| De app meldt nooit succes als het wegschrijven mislukte; na een mislukt verwijderen of importeren toont het scherm wat er in de opslag staat | `test-opslagmelding.py` (dertien handelingen op clubs en rondes met een falende opslag) |
| Clubnamen zijn uniek, baannamen en wedstrijdlussen niet | `test-startscherm-clubs.py` (het startscherm), `test-zelfde-baannamen.py` (spelanalyse, baananalyse, Statistiek, Rondes, corrigeren, verwijderen; wedstrijdlussen met dezelfde naam, ook samenstellen en bijwerken) |
| Twee spelers: wat voor speler 1 werkt, werkt ook met speler 2 op het scherm, en de toestand klopt daarna in zichzelf | `test-speler2-op-scherm.py` (afronden, pauzeren, verwijderen, laden, herladen, corrigeren, nieuwe ronde), `test-notitie-tweespelers.py` (bewerkschermen) |
| Score en putts horen bij elkaar: geen score zonder putts (putts aan), geen putts zonder score, hooguit score − 1 putts | `test-score-en-putts.py` (elke knop, elke beginstand, putts aan en uit, speler 1 en 2) |
| Een voorlopige wijziging die verloopt zet alles terug zoals het was | `test-score-en-putts.py` |
| De backupmelding komt alleen als er iets niet in de laatste backup zit, en pas als de ronde is afgerond (een open ronde wacht; het backupbestand neemt een volle open ronde wel mee) | `test-backup-scenarios.py`, `test-backup-overstap.py`, `test-review-oktober.py` (rondes toevoegen uit een bestand zonder eerdere backup) |
| Alleen een helemaal ingevulde, opgeslagen ronde hoort in de backup | `test-backup-pauze.py`, `test-backup-afronden.py` |
| Een instelling uitzetten verbergt alleen en wist niets: uit en weer aan geeft alles terug | `test-instelling-wist-niets.py` (vindt zelf elke schakelaar in Instellingen; zes standen, ook met de eigen gegevens), `test-whsvolgen.py` (wat er verdwijnt en terugkomt) |
| De handicap komt nooit boven 54,0 en nooit meer dan 5,0 boven de Low HI | `test-handicap-grenzen.py` (raster, elke berekening onderweg, en elk getoond getal; acht reeksen, ook de eigen gegevens) |
| De handicap wordt alleen berekend voor de speler bovenin Start, nooit voor speler 2; ook het WHS-driehoekje en 'N zonder dagresultaat' gelden alleen zijn rondes, en pas als de ronde is opgeslagen (niet bij een open ronde, en bij een ingelezen ronde pas na 'Sla op'). Staat speler 2 zelf bovenin, dan tellen alleen zijn eigen rondes | `test-handicap-alleen-speler1.py` (volgt elke berekening in vier standen; schermen en rondekaarten; speler 2 bovenin) |
| Alleen afgeronde, qualifying rondes tellen mee voor handicap en statistiek. Afgerond is: alle holes ingevuld, niet meer open, en bij één ingelezen ronde pas na 'Sla op' (een bestand met meer rondes is een backup terugzetten: na 'Toevoegen' tellen die meteen mee; een ingelezen ronde die een bestaande overschrijft is na 'Opslaan' meteen opgeslagen). Enige uitzondering op qualifying: de baananalyse in het clubscherm | `test-meetellen.py` (ruis toevoegen verandert niets: Start, Statistiek, spelanalyse, export, rondekaarten; elke berekening onderweg; een opnieuw geladen oude ronde) |
| De slagen per hole tellen altijd op tot de baanhandicap | `test-slagen-per-hole.py` (elke verdeling van -10 t/m 60; een ronde starten op elke tee van de eigen clubs, twee spelers, ook aangepast en met percentage; Testspelers bestaande rondes) |
| Een baan, tee of club wijzigen of verwijderen verandert geen bestaande ronde, tenzij je bij hernoemen 'ja' zegt; dan verandert alleen de naam, alleen in de rondes die het betreft | `test-clubs-raken-rondes-niet.py` (elke wijziging in de editor, verwijderen, clubbestand inlezen, hernoemen met nee en ja; ook de eigen clubs en rondes), `controle-hernoemen.js` |
| Elk scherm opent zonder fout bij honderden rondes, en geen tik duurt bij 1.000 rondes langer dan één seconde | `test-honderden-rondes.py` (300, 1.000 en 2.500 rommelige rondes en de echte rondes × 10; ongeveer 90 echte tikken per doorloop). Bewust niet: een ronde zonder holeslijst, die weigert de app bij inlezen |
| De statistieken veranderen niet door een wijziging die er niets mee te maken heeft | `ijk-stats.py` (byte voor byte) |
| De schermen blijven snel | `meet-prestaties.py` (vergelijken met de vorige meting) |
| Een tik op de agenda in de kop (geplande rondes) toont in Rondes de eerstvolgende geplande ronde bovenaan: Deze week altijd open en verder tot en met de groep waarin die valt (de lege weken ervoor ook); de tik klapt alleen open, nooit dicht: wat al open stond blijft open (040); een zoekterm of meldingsfilter in Rondes wordt eerst gewist; de weekgrenzen zijn kalenderweken, ook over de zomertijd heen; de knop 'Geplande rondes' houdt de indeling die er staat (038) | `test-kop-agenda-indeling.py` (ronde deze week, volgende week en later; begin met alles open, alles dicht, gemengd en zonder indeling (ook met een vaste klok); vanuit de categorieweergave met een zoekterm, en met een meldingsfilter; de eerste kaart is de eerstvolgende ronde; nog een keer tikken; de knop uit en aan; de weekgrens op 17-03-2027 en 14-10-2026; het meldingsfilter met een echt duplicaat) |
| Wat in dagen gaat, telt hele kalenderdagen in lokale tijd, ook over de zomer- en wintertijd heen: 'Jaar' in Statistiek en Analyse (de dag van een jaar terug telt mee, zoals bij Low HI), 'Gebaseerd op N dagen', 'heel jaar' bij de seizoenskaarten; backupnamen dragen de lokale datum; een tijd '9:00' of met spaties wordt '09:00', uit een bestand én bij het lezen van de opslag, zodat een dubbele ronde herkend blijft (039) | `test-kalenderdagen.py` (nep-klok in Europe/Amsterdam, rond 29-03 en 25-10; 'heel jaar' op de kaart en in de analyse met echte rondes over precies een jaar; backup om 01:30; '9:00' naast '09:00' in de opslag) |

## Zo houd je de regeltests bij

- **Nieuwe bediening op het startscherm** (knop, veld, schakelaar): toevoegen aan
  `HANDELINGEN` in `test-startscherm-lopende-ronde.py`.
- **Nieuwe bediening op een ander scherm**: toevoegen aan `HANDELINGEN` in
  `test-lopende-ronde-andere-schermen.py`.
- **Nieuw veld in een ronde**: toevoegen aan `vol()` en aan `RONDEVELDEN` (of
  `HOLEVELDEN`) in `test-ronde-velden.py`.
- **Nieuwe knop of manier om een score of putts te zetten**: toevoegen aan `HANDELINGEN`
  en aan `model()` in `test-score-en-putts.py`.
- **Nieuwe handeling op een ronde** (een knop op een rondekaart of op het scorescherm):
  toevoegen aan `HANDELINGEN` in `test-speler2-op-scherm.py`.
- **Nieuwe route waarlangs een ronde wordt gelezen en weer weggeschreven**: toevoegen
  als `route(...)` in `test-ronde-velden.py`.
- **Nieuwe manier om van club te wisselen**: toevoegen aan `test-startscherm-clubs.py`.
- **Nieuw scherm, venster of uitklapblok**: toevoegen aan `STANDEN` in
  `test-een-tik-wist-niets.py`. Knoppen binnen een bestaande stand vindt de test zelf.
- **De clubs of de gekozen club wijzigen**: `rebuildCourseLookup()` bouwt alleen de banenlijst
  op en slaat niets op; wie CLUBS wijzigt, roept zelf `saveClubsToStorage()` aan. De gekozen
  club alleen via `zetGekozenClub(naam)`. `test-geen-stille-opslag.py` telt de schrijfacties.
- **Nieuwe inklapbare kop**: `${inklapKop(groep, sleutel, standaardDicht, teken)}` in de kop
  zetten, geen eigen code in onclick; 'alles openklappen' (klapAllesOpen) vindt hem dan vanzelf.
  Toevoegen aan `STANDEN` in `test-inklappen.py` als het een nieuw scherm is.
- **Nieuwe groepering van de rondelijst**: een naam in `GROEPEER_KNOP_VAN` en aanzetten met
  `zetGroepering(naam)`; niet zelf vlaggen of knopkleuren zetten. Toevoegen aan `KNOPPEN` in
  `test-groepering.py`.
- **Nieuwe kaart op Statistiek**: het rekenwerk in een `stat…`-functie (alleen gegevens, geen
  HTML of opslag), de HTML in een `html…`-functie, en aanroepen vanuit de groep waar hij in
  staat, zodat een dichte groep hem niet berekent. Een functie die alleen die kaart gebruikt,
  toevoegen aan `GROEPEN` in `test-dicht-niet-rekenen.py`.
- **Nieuw onderdeel in 'Analyseer mijn spel'**: een functie `analyse…(ctx)` die
  `{ secties, aanbev }` teruggeeft (lege lijsten als er te weinig gegevens zijn), en hem op
  zijn plek in `ANALYSE_ONDERDELEN` zetten. Niet zelf in `buildGameAnalysis` schrijven.
- **Nieuwe knop die een tweede tik vraagt**: `tweedeTik(btn, {…})` gebruiken, niet zelf
  nabouwen, en de knop toevoegen aan `GEVALLEN` in `test-tik-twee-keer.py`.
- **Nieuwe sleutel in localStorage**: in `OPSLAGSLEUTELS` zetten ('wissen', 'houden' of
  'oud') en in DATAMODEL.md. `test-opslagsleutels.py` faalt anders. "Alles wissen" en het
  opruimen bij de start lezen alleen dat register.
- **Nieuwe schakelaar in Instellingen**: niets doen, `test-instelling-wist-niets.py` vindt hem zelf.
  Schrijft hij meer weg dan zijn eigen instelling, dan faalt die test.
- **Nieuwe plek waar een berekende handicap getoond wordt**: toevoegen aan laag 3 in
  `test-handicap-grenzen.py`. De handicap zelf komt altijd uit `whsStand(speler)`: niet zelf
  de laatste 20 kiezen en `whsHandicap` aanroepen (dat is alleen voor een bewust vastgezet
  venster, zoals de Vooruitblik). Laag 2 vangt de berekening, zolang hij via `whsStand`,
  `whsHandicap` of `applyHandicapCaps` loopt.
- **Nieuwe rekenfunctie die een speler meekrijgt**: de naam toevoegen aan de lijst in `MEESCHRIJVEN` in
  `test-handicap-alleen-speler1.py`, anders volgt de test hem niet.
- **Nieuwe plek die rondes kiest voor handicap of statistiek**: `meetelFilter(speler)` gebruiken, niet zelf
  'qualifying en alle holes' uitschrijven. Toont de plek iets nieuws, dan toevoegen aan `BEELD` in `test-meetellen.py`.
- **Nieuwe manier om de baanhandicap van een ronde te zetten of te wijzigen**: toevoegen aan `VARIANTEN` of
  `STARTEN` in `test-slagen-per-hole.py`. Wijzigt iets de baanhandicap van een bestaande ronde, dan moeten de
  slagen per hole mee.
- **Nieuwe bewerking in de club- of baaneditor, of een nieuw veld dat hernoemd kan worden**: toevoegen aan
  `WIJZIGEN` of `HERNOEMEN` in `test-clubs-raken-rondes-niet.py`.
- **Nieuwe knop, groepering of uitklapblok op een scherm**: de functienaam uit `onclick` toevoegen aan `TIKKEN`
  in `test-honderden-rondes.py`. Alleen wat niets wist of start.
- **Nieuwe plek die per baan of per hole telt of groepeert**: de club meenemen in de sleutel (`holeSleutel`, of
  eerst per club en dan per baan) en de plek toevoegen aan `test-zelfde-baannamen.py`. Een baannaam alleen zegt niet welke baan het is.
- **Nieuwe handeling die `game` leegmaakt of vervangt**: eerst `saveActiveRound()` aanroepen en bij `false` stoppen met
  `meldNietOpgeslagen`; een geval toevoegen aan `test-opslagstoring-handelingen.py`.
- **Nieuwe tik op de scorekaart die een score of putts wijzigt**: opslaan met `bewaarNaTik()`, niet met
  `saveActiveRound()` (die bouwt de hele rondelijst op); de functie toevoegen aan `test-scoretik-lijst.py`.
- **Nieuwe lus over alle rondes binnen een lus over alle rondes**: datums en andere omzettingen vooraf één keer
  doen; een telling toevoegen aan `test-rekenwerk-per-handeling.py`. Wie alleen de weergave van de rondelijst
  verandert (zoeken, filteren), roept `tekenRondelijst(true)` aan.
- **Nieuwe plek waar een naam of ander ingevoerd of geïmporteerd veld in `innerHTML` komt**: door `escapeHtml()`;
  in een `onclick` bij voorkeur `data-…` plus `this.dataset.…`, anders `escapeJsString()`. Het scherm toevoegen aan
  `test-namen-met-tekens.py` of `test-velden-als-tekst.py`.
- **Nieuwe plek die een handicap uitrekent of vergelijkt**: afronden met `whsIndexRound()`, nooit met een losse
  `Math.round(x * 10) / 10`; grenzen vergelijken na afronden.
- **Nieuw veld in een ronde of club**: toevoegen aan `DATAMODEL.md`, aan `zetRondeRecht`/`keurRonde` (of
  `validateImportedClubData`) en als geval aan `test-importkeuring.py`.
- **Nieuwe handeling die `game` leegmaakt of vervangt** (aanvulling): eerst `handelWachtendeTikAf()`, dan pas opslaan.
- **Nieuwe handeling die rondes of clubs wegschrijft**: het resultaat van `setRoundsAndMark()` of `saveClubsToStorage()`
  controleren; bij `false` `meldSchrijvenMislukt()` (clubs: eerst `draaiClubsTerug()`) en geen succesmelding. Een geval
  toevoegen aan `test-opslagmelding.py`.
- **Nieuwe regel die over de hele app geldt**: een rij in de tabel hierboven, met een
  test die de regel over alle gevallen controleert, niet één geval.

## Het patroon achter de fouten van 3 oktober 2026

Bijna elke fout was: iets ging op één plek goed en op een andere niet. Een veld dat op
vier van de vijf plekken werd meegenomen. Een regel die voor speler 1 gold en niet voor
speler 2. Een baannaam die bij één club klopte. Een herberekening die op één plek was
verwijderd en op een andere was blijven staan.

Losse tests per geval vinden dat niet. Tests die een regel over alle gevallen heen
controleren wel. Daarom vraag 1.

## Bewuste keuzes

- **Stale-while-revalidate blijft** (12-10-2026, 13527DA-13C). Een nieuwe golf-score.html
  komt via de achtergrondverversing bij de volgende opening binnen, ook zonder tik op de
  updatemelding; 'jij bepaalt wanneer' geldt alleen voor de service worker. Geaccepteerd
  omdat scores in de opslag staan en elke versie die van de vorige leest
  (`test-backup-overstap.py`), de app nooit midden in gebruik herlaadt, alle logica in
  golf-score.html zit en een afgebroken download niet in de cache komt. Kosten: zo'n
  280 KB per opening met bereik. Het alternatief (alleen via de wachtende update) is
  besproken en niet gekozen; zie ook de toelichting bovenin sw-golf-score.js.

- **Drie pogingen bij het installeren** (16-10-2026). Golf Score probeert elk bestand bij een
  update tot drie keer, elk met een grens van 10 s; Trends en Events één keer. Op de baan
  wisselt het bereik, en een update die halverwege mislukt krijgt anders pas bij de
  volgende opening een nieuwe kans. Zie apps-basis/conventies.md, 'Bewust verschillend'.

## Wat hier niet te testen is

Aanraking op een telefoon (de tests gebruiken een muis), het oppikken van een update
door de telefoon, en de weergave op een echt toestel. Dat blijft bij de gebruiker: wat op de
telefoon afwijkt, komt alleen daar boven.
