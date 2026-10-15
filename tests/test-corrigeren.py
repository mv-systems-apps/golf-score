"""Een gespeelde ronde corrigeren zonder alle scores opnieuw in te tikken.

Je speelt een ronde, en achteraf blijkt dat je hem verkeerd hebt opgezet: de verkeerde
tee gekozen, of de verkeerde baan. Tot nu toe kon je dan alleen de ronde weggooien en
alles opnieuw invoeren — negen of achttien scores plus de putts.

'Corrigeren' doet hetzelfde als 'Herplannen', maar neemt je scores mee. Alles wat van de
omstandigheden afhangt (baanhandicap, persoonlijke par, stableford, dagresultaat) wordt
opnieuw berekend, en een eerder VASTGESTELD dagresultaat vervalt — dat hoorde bij de oude
opzet. De oude ronde verdwijnt pas als de nieuwe is vastgelegd, dus afbreken kan altijd.

Eén knop met twee namen: zonder scores 'Herplannen', met scores 'Corrigeren'. Ze staan
nooit samen, want de situaties sluiten elkaar uit.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from testdata import CLUBS, APP, app_url

fouten = []


def check(naam, gekregen, verwacht):
    if gekregen != verwacht:
        fouten.append(naam)
        print(f" FOUT  {naam}: {gekregen!r} — verwacht {verwacht!r}")
    else:
        print(f"  ok   {naam}: {gekregen!r}")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 390, "height": 844})
        paginafouten = []
        page.on('pageerror', lambda e: paginafouten.append(str(e)))
        await page.goto(app_url())
        await page.evaluate("""(clubs) => {
            localStorage.clear();
            localStorage.setItem('golf_clubs', JSON.stringify(clubs));
            localStorage.setItem('golf_rounds', '[]');
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_profile_name', 'Mark');
            localStorage.setItem('golf_kenmerk_gevraagd', '1');
        }""", CLUBS)
        await page.reload()
        await page.wait_for_timeout(800)

        async def speelRonde(tee='Blauw', vastgesteld=None):
            await page.evaluate("""([tee, sd]) => {
                nav('setup');
                sel.track = 'Airborne'; sel.tee = tee; sel.qualifying = true;
                document.getElementById('iName').value = 'Mark';
                document.getElementById('iHcp').value = '30.7';
                onHcpBlur(document.getElementById('iHcp'));
                startRound();
                const cb = document.getElementById('confirmModalBtn');
                if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
                nav('score');
                for (let h = 0; h < 9; h++) {
                    setCurrentHole(h); selectHole(h);
                    armScoreChange(h, 4 + h % 3); clearScoreTap(false);
                }
                if (sd != null) game.sdFinal = sd;
                saveActiveRound(true);
                storage.removeItem('golf_active_id');
                game.started = false;
                loadSaved();
            }""", [tee, vastgesteld])
            await page.wait_for_timeout(400)

        print("=== DE KNOP HEET NAAR DE SITUATIE ===\n")
        await speelRonde()
        gespeeld = await page.evaluate("""() => {
            nav('archive');
            openRoundEditChoice(0);
            const uit = [...document.querySelectorAll('#roundEditChoiceModal button')]
                .filter(b => b.id).map(b => ({ tekst: b.textContent.trim(), uit: !!b.disabled }));
            sluitRoundEditChoice();
            return uit;
        }""")
        check("bij een gespeelde ronde: Corrigeren",
              [k["tekst"] for k in gespeeld], ['Corrigeren', 'Bewerken', 'Vaststellen'])
        check("en geen enkele keuze staat uit",
              [k["uit"] for k in gespeeld], [False, False, False])

        leeg = await page.evaluate("""() => {
            const lijst = loadSavedRounds();
            const b = lijst[0];
            lijst.push({ ...b, id: 7777, date: '2027-03-03', playedCount: 0, started: false,
                         sd: null, sdFinal: null,
                         holes: b.holes.map(h => ({ ...h, score: null, putts: null })) });
            setRoundsAndMark(JSON.stringify(lijst));
            loadSaved();
            const i = loadSavedRounds().findIndex(r => r.id === 7777);
            openRoundEditChoice(i);
            const uit = document.getElementById('roundEditChoiceHerplan').textContent.trim();
            sluitRoundEditChoice();
            // Weer opruimen: de rest van de test rekent op één ronde.
            metVerwijderen(() => setRoundsAndMark(JSON.stringify(
                loadSavedRounds().filter(r => r.id !== 7777))));
            return uit;
        }""")
        check("bij een lege ronde: Herplannen", leeg, 'Herplannen')

        print("\n=== DE SCORES GAAN MEE ===\n")
        voor = await page.evaluate("""() => {
            const r = loadSavedRounds()[0];
            return { tee: r.tee, chcp: r.chcp, scores: r.holes.map(h => h.score) };
        }""")
        na = await page.evaluate("""() => {
            corrigeerRonde(String(loadSavedRounds()[0].id));
            document.getElementById('keuzeModalKnop2').click();     // Corrigeren
            const bannerTekst = document.getElementById('herplanBanner').innerText;
            sel.tee = 'Geel';                                        // andere tee kiezen
            startRound();
            const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
            return {
                banner: bannerTekst,
                tee: game.tee,
                chcp: game.chcp,
                scores: game.holes.map(h => h.score),
                aantalRondes: loadSavedRounds().length,
            };
        }""")
        check("de scores zijn behouden", na["scores"], voor["scores"])
        check("op de nieuwe tee", na["tee"], 'Geel')
        check("de baanhandicap is opnieuw berekend", na["chcp"] != voor["chcp"], True)
        check("en er staat nog één ronde", na["aantalRondes"], 1)
        check("de banner meldde de scores", 'scores gaan mee' in na["banner"], True)

        print("\n=== EEN VASTGESTELD DAGRESULTAAT VERVALT ===\n")
        # De vastgestelde waarde hoorde bij de oude tee; hem meenemen zou een verkeerd
        # getal in je handicap houden.
        await page.evaluate("""() => {
            storage.removeItem('golf_active_id'); game.started = false;
            metVerwijderen(() => setRoundsAndMark('[]'));
            loadSaved();
        }""")
        await speelRonde(vastgesteld=29.9)
        vastgesteld = await page.evaluate("""() => {
            const voor = loadSavedRounds()[0].sdFinal;
            corrigeerRonde(String(loadSavedRounds()[0].id));
            const gemeld = document.getElementById('keuzeModalTekst').textContent
                .includes('vastgestelde dagresultaat vervalt');
            document.getElementById('keuzeModalKnop2').click();
            sel.tee = 'Geel';
            startRound();
            const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
            return { voor, gemeld, na: game.sdFinal ?? null };
        }""")
        check("stond er een vastgesteld resultaat", vastgesteld["voor"], 29.9)
        check("het venster meldt dat het vervalt", vastgesteld["gemeld"], True)
        check("en het is vervallen", vastgesteld["na"], None)

        print("\n=== ANNULEREN LAAT ALLES STAAN ===\n")
        annuleren = await page.evaluate("""() => {
            storage.removeItem('golf_active_id'); game.started = false; loadSaved();
            const voor = loadSavedRounds().length;
            corrigeerRonde(String(loadSavedRounds()[0].id));
            document.getElementById('keuzeModalKnop1').click();      // Annuleren
            return { voor, na: loadSavedRounds().length,
                     scoresLosgelaten: !window._corrigeerScores };
        }""")
        check("de ronde staat er nog", annuleren["na"], annuleren["voor"])
        check("en er blijft niets hangen", annuleren["scoresLosgelaten"], True)

        print("\n=== MEER SCORES DAN HOLES ===\n")
        # Corrigeer je naar een baan met minder holes, dan passen niet alle scores. De
        # eerste zoveel gaan mee; de rest vervalt met de holes waar ze bij hoorden.
        # De testbanen hebben allemaal negen holes, dus de oude ronde wordt hier
        # rechtstreeks in de opslag gezet met achttien.
        await page.evaluate("""() => {
            const basis = loadSavedRounds()[0];
            const holes = [];
            for (let i = 0; i < 18; i++) {
                const bron = basis.holes[i % 9];
                holes.push({ ...bron, id: 'H' + (i + 1), si: i + 1, score: 4 + i % 3 });
            }
            metVerwijderen(() => setRoundsAndMark(JSON.stringify([
                { ...basis, id: 7700, holes, holesCount: 18, playedCount: 18,
                  sd: null, sdFinal: null },
            ])));
            nav('archive'); loadSaved();
        }""")
        await page.wait_for_timeout(300)
        korter = await page.evaluate("""() => {
            const oud = loadSavedRounds()[0];
            const aantalOud = oud.holes.length;
            const eersteNegen = oud.holes.slice(0, 9).map(h => h.score);
            corrigeerRonde(String(oud.id));
            document.getElementById('keuzeModalKnop2').click();      // Corrigeren
            startRound();
            const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
            return { aantalOud, eersteNegen,
                     holes: game.holes.length,
                     scores: game.holes.map(h => h.score),
                     rondes: loadSavedRounds().length };
        }""")
        check("de oude ronde had achttien scores", korter["aantalOud"], 18)
        check("de nieuwe baan heeft negen holes", korter["holes"], 9)
        check("de eerste negen scores gaan mee", korter["scores"], korter["eersteNegen"])
        check("en er is geen duplicaat", korter["rondes"], 1)

        print("\n=== MET TWEE SPELERS ===\n")
        # Er worden TWEE sets scores bewaard, gekoppeld aan de SPELER en niet aan de kaart
        # waarop je tikte. Eerder ging dat twee keer mis: tikte je op je eigen kaart, dan
        # kwam de medespeler leeg terug; tikte je op de zijne, dan kregen jouw holes zijn
        # scores.
        async def tweeSpelers():
            await page.evaluate("""() => {
                metVerwijderen(() => setRoundsAndMark('[]'));
                localStorage.removeItem('golf_active_id');
                localStorage.removeItem('golf_game2_id');
                nav('setup');
                sel.track = 'Airborne'; sel.tee = 'Blauw'; sel._teeUserSelected = true;
                sel.qualifying = true;
                document.getElementById('iName').value = 'Mark';
                document.getElementById('iHcp').value = '30.7';
                onHcpBlur(document.getElementById('iHcp'));
                if (!player2Visible) togglePlayer2();
            }""")
            await page.wait_for_timeout(300)
            await page.evaluate("""() => {
                document.getElementById('iName2').value = 'Partner';
                document.getElementById('iHcp2').value = '18';
                sel2.tee = 'Geel'; sel2._teeUserSelected = true; sel2.qualifying = true;
                startRound();
                const cb = document.getElementById('confirmModalBtn');
                if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
                nav('score');
                // Verschillende scores, zodat verwisseling meteen opvalt.
                for (let h = 0; h < 9; h++) { setCurrentHole(h); selectHole(h);
                    armScoreChange(h, 4); clearScoreTap(false); }
                switchToPlayer(2);
                for (let h = 0; h < 9; h++) { setCurrentHole(h); selectHole(h);
                    armScoreChange(h, 6); clearScoreTap(false); }
                switchToPlayer(1);
                localStorage.removeItem('golf_active_id');
                game.started = false;
                loadSaved();
            }""")
            await page.wait_for_timeout(500)

        def scoresVan(lijst, speler):
            r = next((x for x in lijst if x["speler"] == speler), None)
            return r["scores"] if r else None

        await tweeSpelers()
        eigen = await page.evaluate("""() => {
            const mijn = loadSavedRounds().find(r => r.player === 'Mark');
            corrigeerRonde(String(mijn.id));
            document.getElementById('keuzeModalKnop2').click();
            // Geel is de andere herentee in de testgegevens; Rood is een damestee en
            // wordt bij geslacht Heren teruggezet.
            sel.tee = 'Geel'; sel._teeUserSelected = true;
            rebuildAll();
            startRound();
            const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
            return loadSavedRounds().map(r => ({ speler: r.player, tee: r.tee,
                scores: r.holes.map(h => h.score == null ? '-' : h.score).join('') }));
        }""")
        check("via de eigen kaart: jouw scores blijven",
              scoresVan(eigen, 'Mark'), '444444444')
        check("en die van de medespeler ook",
              scoresVan(eigen, 'Partner'), '666666666')
        check("met de nieuwe tee voor jou",
              next(x["tee"] for x in eigen if x["speler"] == 'Mark'), 'Geel')

        await tweeSpelers()
        viaMaat = await page.evaluate("""() => {
            const maat = loadSavedRounds().find(r => r.player === 'Partner');
            corrigeerRonde(String(maat.id));
            document.getElementById('keuzeModalKnop2').click();
            startRound();
            const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
            return loadSavedRounds().map(r => ({ speler: r.player,
                scores: r.holes.map(h => h.score == null ? '-' : h.score).join('') }));
        }""")
        check("via de kaart van de medespeler: geen verwisseling",
              scoresVan(viaMaat, 'Mark'), '444444444')
        check("en zijn eigen scores staan er nog",
              scoresVan(viaMaat, 'Partner'), '666666666')

        await tweeSpelers()
        zonder = await page.evaluate("""() => {
            const mijn = loadSavedRounds().find(r => r.player === 'Mark');
            corrigeerRonde(String(mijn.id));
            document.getElementById('keuzeModalKnop2').click();
            if (player2Visible) togglePlayer2();     // speler 2 bewust uitzetten
            startRound();
            const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
            return loadSavedRounds().map(r => ({ speler: r.player,
                scores: r.holes.map(h => h.score == null ? '-' : h.score).join('') }));
        }""")
        # Beide oude rondes verdwijnen en er komt er één terug: alsof je ze weggooit en
        # opnieuw invoert.
        check("speler 2 uitzetten laat één ronde over", len(zonder), 1)
        check("die van jou, met je scores", scoresVan(zonder, 'Mark'), '444444444')

        print("\n=== RANDGEVALLEN ===\n")

        async def eenRonde(tee='Blauw'):
            await page.evaluate("""(t) => {
                metVerwijderen(() => setRoundsAndMark('[]'));
                localStorage.removeItem('golf_active_id');
                localStorage.removeItem('golf_game2_id');
                nav('setup');
                sel.track = 'Airborne'; sel.tee = t; sel._teeUserSelected = true;
                sel.qualifying = true;
                document.getElementById('iName').value = 'Mark';
                document.getElementById('iHcp').value = '30.7';
                onHcpBlur(document.getElementById('iHcp'));
                if (player2Visible) togglePlayer2();
                startRound();
                const cb = document.getElementById('confirmModalBtn');
                if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
                nav('score');
                for (let h = 0; h < 9; h++) {
                    setCurrentHole(h); selectHole(h);
                    armScoreChange(h, 4 + h % 3); clearScoreTap(false);
                }
                localStorage.removeItem('golf_active_id');
                game.started = false;
                loadSaved();
                // Putts via de OPSLAG zetten: rechtstreeks op het game-object werkt niet,
                // want de laatste wijziging wordt dan niet meer weggeschreven.
                const lijst = loadSavedRounds();
                lijst[0].holes.forEach(h => { h.putts = 2; });
                metVerwijderen(() => setRoundsAndMark(JSON.stringify(lijst)));
            }""", tee)
            await page.wait_for_timeout(450)

        await eenRonde()
        mee = await page.evaluate("""() => {
            const lijst = loadSavedRounds();
            lijst[0].note = 'Mooie ronde';
            metVerwijderen(() => setRoundsAndMark(JSON.stringify(lijst)));
            corrigeerRonde(String(lijst[0].id));
            document.getElementById('keuzeModalKnop2').click();
            sel.tee = 'Geel'; sel._teeUserSelected = true;
            sel.qualifying = false;                       // qualifying uitzetten
            rebuildAll();
            startRound();
            const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
            const r = loadSavedRounds()[0];
            return { putts: r.holes.map(h => h.putts), notitie: r.note,
                     qualifying: r.qualifying, tee: r.tee };
        }""")
        check("putts gaan mee", mee["putts"], [2] * 9)
        check("de notitie ook", mee["notitie"], 'Mooie ronde')
        check("en de qualifying-vlag volgt de nieuwe opzet", mee["qualifying"], False)

        # Twee keer achter elkaar corrigeren mag geen stapel rondes opleveren.
        await eenRonde()
        tweemaal = await page.evaluate("""() => {
            for (const tee of ['Geel', 'Blauw']) {
                corrigeerRonde(String(loadSavedRounds()[0].id));
                document.getElementById('keuzeModalKnop2').click();
                sel.tee = tee; sel._teeUserSelected = true;
                rebuildAll();
                startRound();
                const cb = document.getElementById('confirmModalBtn');
                if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
            }
            const l = loadSavedRounds();
            return { rondes: l.length, tee: l[0].tee,
                     scores: l[0].holes.map(h => h.score).join(''),
                     idsUniek: new Set(l.map(r => r.id)).size === l.length };
        }""")
        check("twee keer corrigeren geeft één ronde", tweemaal["rondes"], 1)
        check("met de laatste tee", tweemaal["tee"], 'Blauw')
        check("de scores staan er nog", tweemaal["scores"], '456456456')
        check("en de id's blijven uniek", tweemaal["idsUniek"], True)

        # Half gespeelde ronde: alleen de ingevulde holes komen terug.
        await eenRonde()
        half = await page.evaluate("""() => {
            const lijst = loadSavedRounds();
            lijst[0].holes.forEach((h, i) => { if (i >= 4) h.score = null; });
            metVerwijderen(() => setRoundsAndMark(JSON.stringify(lijst)));
            corrigeerRonde(String(lijst[0].id));
            document.getElementById('keuzeModalKnop2').click();
            startRound();
            const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
            return loadSavedRounds()[0].holes.map(h => h.score);
        }""")
        check("een half gespeelde ronde houdt zijn lege holes",
              half, [4, 5, 6, 4, None, None, None, None, None])

        # Mislukt het opslaan, dan blijft de OUDE ronde staan: anders sta je met lege
        # handen omdat de nieuwe nergens terechtkwam.
        await eenRonde()
        volleOpslag = await page.evaluate("""() => {
            corrigeerRonde(String(loadSavedRounds()[0].id));
            document.getElementById('keuzeModalKnop2').click();
            const echt = Storage.prototype.setItem;
            Storage.prototype.setItem = function (k, v) {
                if (k === 'golf_rounds') {
                    const e = new Error('vol'); e.name = 'QuotaExceededError'; throw e;
                }
                return echt.call(this, k, v);
            };
            sel.tee = 'Geel'; sel._teeUserSelected = true;
            rebuildAll();
            startRound();
            const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
            Storage.prototype.setItem = echt;
            const l = loadSavedRounds();
            return { rondes: l.length,
                     oudeCompleet: !!l.find(r => r.tee === 'Blauw'
                        && r.holes.filter(h => h.score !== null).length === 9) };
        }""")
        check("bij volle opslag blijft er één ronde", volleOpslag["rondes"], 1)
        check("en dat is de oude, compleet", volleOpslag["oudeCompleet"], True)

        # Annuleren via de banner mag geen scores laten doorlekken naar de volgende ronde.
        await eenRonde()
        geenLek = await page.evaluate("""() => {
            corrigeerRonde(String(loadSavedRounds()[0].id));
            document.getElementById('keuzeModalKnop2').click();
            annuleerHerplan();                       // banner wegklikken
            document.getElementById('iDate').value = '2025-06-06';
            document.getElementById('iTime').value = '07:00';
            onDateTimeChange();
            sel.tee = 'Geel'; sel._teeUserSelected = true;
            rebuildAll();
            startRound();
            const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
            const l = loadSavedRounds();
            const nieuw = l.find(r => r.date === '2025-06-06');
            return { rondes: l.length,
                     nieuweIsLeeg: nieuw ? nieuw.holes.every(h => h.score === null) : null,
                     oudeCompleet: !!l.find(r => r.tee === 'Blauw'
                        && r.holes.filter(h => h.score !== null).length === 9) };
        }""")
        check("na annuleren staan er twee losse rondes", geenLek["rondes"], 2)
        check("de nieuwe is leeg (geen doorgelekte scores)", geenLek["nieuweIsLeeg"], True)
        check("en de oude is onaangeroerd", geenLek["oudeCompleet"], True)

        if paginafouten:
            fouten.append('paginafouten')
            print("\nFOUTEN IN DE PAGINA:")
            for f in paginafouten[:5]:
                print("   " + f[:150])

        await browser.close()

    print()
    if fouten:
        print(f"{len(fouten)} FOUT(EN)")
        sys.exit(1)
    print("GEEN FOUTEN")


asyncio.run(main())
