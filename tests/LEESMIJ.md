# Tests voor golf-score.html

Deze map draait de **echte app** in een browser en meet wat eruit komt. Geen
losse rekenmodules: de tests seeden de opslag, klikken door de app en
vergelijken het resultaat. Dat is precies het soort fout dat statische
controles missen — fouten in het samenspel tussen functies.

## Draaien

```bash
python3 tests/run-alles.py --snel                   # na elke wijziging: zonder de zware tests
python3 tests/run-alles.py                          # vóór elke push: alles (~50 min)
APP=/pad/naar/golf-score.html python3 tests/run-alles.py
```

De zware tests (lijst ZWAAR in run-alles.py) proberen alles in elke stand: alles
aantikken, elke knop, honderden rondes. Ze nemen samen meer dan de helft van de tijd.
Ze slaan over in de snelle run, maar gaan altijd mee vóór een push.

Eén onderdeel apart:

```bash
node tests/controle-diep.js
python3 tests/ijk-stats.py ../golf-score.html tests/ijkmeting.json
```

**Nodig:** node en python3 met playwright (`pip install playwright && playwright install chromium`).

## Wat er getest wordt

**Statische controles** (node, snel) — syntax, dode code, losse verwijzingen,
de samenhang tussen plekken die hetzelfde begrip gebruiken, en de regels rond
opnieuw plannen, filters, hernoemen en duplicaten.

`controle-baanmodel.js` bewaakt één afspraak: **par en SI horen bij de tee, niet bij
de baan.** Een baan bewaart alleen `holeIds`; elke tee heeft een eigen
`holes: [{par, si}]`, en het teetotaal `PAR` bestaat niet meer als opgeslagen veld.
Duikt `course.holes` of `teeData.PAR` weer op, dan valt deze controle om — ook als
geen enkele browsertest die tak raakt. Let op: een RONDE bewaart zijn par-totaal wél;
dat is een bewuste kopie, zodat statistieken niet meebewegen als de baan later
verandert.

**Browsertests** (playwright, trager) — de echte gebruikersstromen:

| test | wat het bewijst |
|---|---|
| `ijk-stats.py` | het statistiekenscherm is byte-voor-byte onveranderd |
| `test-herplan-browser.py` | twaalf scenario's rond opnieuw plannen, incl. speler 2 |
| `test-modals.py` | de twee bewerkvensters gedragen zich gelijk |
| `test-corrupt.py` | corrupte gegevens worden gemeld en NIET overschreven |
| `test-backupteller.py` | de backupwaarschuwing telt alleen afgeronde rondes |
| `test-tellerlag.py` | de holetelling klopt tijdens het invoeren |
| `test-paden.py` | alle schermen, ook bij een verse installatie |
| `test-labels.py` | labels horen bij hun invoerveld |
| `test-herstel.py` | een backup komt volledig terug (alleen met eigen backup) |
| `test-par-per-tee.py` | par en SI horen bij de tee: editor, ronde, import, baananalyse |
| `test-levenscyclus.py` | baan maken → spelen → backuppen → wissen → herstellen |
| `test-editor-stress.py` | 60 bewerkingen door elkaar; hole-lijsten blijven in de pas |

**Metingen** (geen slaag/faal) — snelheid per scherm, foutafvang bij inlezen,
en de manieren waarop "afgerond" wordt bepaald.

## De ijkmeting

`ijk-stats.py` vergelijkt de opgebouwde statistiekenpagina met een vastgelegde
vingerafdruk in `ijkmeting.json`. Dat is het vangnet bij het herschikken van
code: elke onbedoelde wijziging valt meteen op.

**Na een bedoelde wijziging** moet de ijkmeting opnieuw worden vastgelegd:

```bash
python3 tests/ijk-stats.py            # zonder tweede argument = opnieuw vastleggen
```

Doe dat pas als je zeker weet dat het verschil klopt — anders leg je een fout vast.

## Testen tegen je eigen gegevens

Zet een backup als `tests/rondes_backup.json`. Dan draait `test-herstel.py`
mee: die vult de app, wist alles, herstelt uit de backup en vergelijkt rondes,
handicap, dagresultaten, putts en notities.

`ijk-echt.py` doet hetzelfde als de gewone ijkmeting maar dan met je echte
rondes — het scherpste vangnet dat er is, omdat het je werkelijke gegevens
gebruikt.

## Bij het herschikken van code

De volgorde die werkt:

1. Leg eerst de ijkmeting vast (vóór de wijziging).
2. Wijzig in kleine stappen, met na élke stap een syntaxcontrole.
3. Draai de ijkmeting: byte-voor-byte gelijk of niet.
4. Test daarnaast de standen die de ijkmeting niet bereikt (ingeklapte
   groepen, andere weergaven) — die worden makkelijk gemist.

## Twee valkuilen die eerder misgingen

**Namen die binnen én buiten een blok bestaan.** Bij het uitplaatsen van code
kan een parameter een eigen declaratie afschermen. De browsertest ving dat op;
een syntaxcontrole niet.

**Testgegevens die niet kunnen bestaan.** Rondes zonder holes maar mét een
teller gaven jarenlang "geslaagd" terwijl ze niets bewezen. Houd de
testrondes realistisch: zoals de app ze zelf zou wegschrijven.

## In de GitHub-repository

Deze map staat ook als `tests/` naast de app in de repository golf-score. Alles werkt
daar op dezelfde manier: `../golf-score.html` is de app ernaast. De service-workertests
(`test-sw-*.py`) nemen de app-bestanden uit de werkmap `uit/` als die er is, en anders
de losse bestanden naast deze map; met `UIT=/pad` kies je zelf.

De echte rondes hier (`echte-rondes.json`, `rondes-lowhi.json`, `overstap-standen.json`)
zijn op 15-10-2026 geanonimiseerd: speler "Testspeler", medespeler "Medespeler". De
repository is openbaar: zet hier nooit een backup met namen neer (`rondes_backup.json`
alleen lokaal).
