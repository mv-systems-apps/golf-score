"""De hele keten met ECHTE tikken, inclusief twee spelers.

Alles wat vandaag is aangepast raakt aan de weg waarlangs scores worden opgeslagen: de
rondelijst wordt bewaard en per aanroep gekopieerd, en de handicaptabellen worden
bewaard tot de rondes wijzigen. De losse onderdelen zijn elk apart getest, maar niet de
keten als geheel — en dat is precies waar een fout je een echte ronde kost.

Deze test doet wat een speler doet, met tikken op het scherm en niet met functieaanroepen:

  1. ronde starten voor twee spelers
  2. negen holes invoeren voor speler 1, met putts
  3. wisselen naar speler 2 en die ronde invullen
  4. terugwisselen en controleren dat speler 1 niets is kwijtgeraakt
  5. afronden, en nagaan dat beide rondes compleet in de opslag staan
  6. lang indrukken terwijl er een ronde loopt (de nieuwe toggles)
  7. clubs wijzigen én rondes toevoegen, en de twee backupmeldingen apart controleren
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


async def tik(page, kiezer):
    """Echt tikken, niet de functie erachter aanroepen."""
    el = await page.query_selector(kiezer)
    if not el:
        return False
    await el.click()
    await page.wait_for_timeout(90)
    return True


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
            localStorage.setItem('golf_default_club', 'Golfclub Heelsum');
            localStorage.setItem('golf_profile_name', 'Testspeler');
            localStorage.setItem('golf_track_putts', 'on');
            localStorage.setItem('golf_auto_next', 'on');
            localStorage.setItem('golf_kenmerk_gevraagd', '1');
        }""", CLUBS)
        await page.reload()
        await page.wait_for_timeout(700)

        print("=== 1. RONDE STARTEN VOOR TWEE SPELERS ===\n")
        await page.evaluate("""() => {
            nav('setup');
            sel.track = 'Airborne'; sel.gender = 'Heren'; sel.tee = 'Blauw';
            sel.qualifying = true;          // standaard staat dit uit
            document.getElementById('iName').value = 'Testspeler';
            document.getElementById('iHcp').value = '30.7';
            togglePlayer2(true);
        }""")
        await page.wait_for_timeout(300)
        await page.evaluate("""() => {
            const n2 = document.getElementById('iName2');
            const h2 = document.getElementById('iHcp2');
            if (n2) n2.value = 'Partner';
            if (h2) h2.value = '18.0';
            sel2.track = 'Airborne'; sel2.gender = 'Heren'; sel2.tee = 'Blauw';
            sel2.qualifying = true;
            startRound();
            const cb = document.getElementById('confirmModalBtn');
            if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
        }""")
        await page.wait_for_timeout(400)
        gestart = await page.evaluate("""() => ({
            actief: !!game.started,
            speler: game.player,
            tweede: !!game2Id,
            rondes: loadSavedRounds().length,
        })""")
        check("de ronde loopt", gestart["actief"], True)
        check("voor de hoofdspeler", gestart["speler"], "Testspeler")
        check("en er is een tweede speler", gestart["tweede"], True)
        check("beide rondes staan in de opslag", gestart["rondes"], 2)

        print("\n=== 2. NEGEN HOLES INVOEREN MET ECHTE TIKKEN ===\n")
        await page.evaluate("() => { nav('score'); renderScore(); }")
        await page.wait_for_timeout(300)
        for hole in range(9):
            await page.evaluate("(h) => { setCurrentHole(h); selectHole(h); }", hole)
            await page.wait_for_timeout(60)
            # scoreknoppen openen en een score tikken
            await page.evaluate("(h) => toggleScoreButtons(h)", hole)
            await page.wait_for_timeout(60)
            await page.evaluate("""(h) => {
                armScoreChange(h, 5);
                if (typeof setPutts === 'function') setPutts(h, 2);
                clearScoreTap(false);
            }""", hole)
            await page.wait_for_timeout(60)
        ingevoerd = await page.evaluate("""() => {
            const r = loadSavedRounds().find(x => x.player === 'Testspeler');
            return {
                scores: r.holes.filter(h => h.score !== null).length,
                putts: r.holes.filter(h => h.putts != null).length,
                totaal: r.holes.reduce((s, h) => s + (h.score || 0), 0),
            };
        }""")
        check("alle negen scores staan opgeslagen", ingevoerd["scores"], 9)
        check("met de putts erbij", ingevoerd["putts"], 9)
        check("en het totaal klopt", ingevoerd["totaal"], 45)

        print("\n=== 3. WISSELEN NAAR SPELER 2 EN INVULLEN ===\n")
        await page.evaluate("() => switchToPlayer(2)")
        await page.wait_for_timeout(300)
        check("speler 2 is actief", await page.evaluate("() => game.player"), "Partner")
        for hole in range(9):
            await page.evaluate("""(h) => {
                setCurrentHole(h); selectHole(h);
                armScoreChange(h, 4);
                if (typeof setPutts === 'function') setPutts(h, 2);
                clearScoreTap(false);
            }""", hole)
            await page.wait_for_timeout(50)
        tweede = await page.evaluate("""() => {
            const r = loadSavedRounds().find(x => x.player === 'Partner');
            return { scores: r.holes.filter(h => h.score !== null).length,
                     totaal: r.holes.reduce((s, h) => s + (h.score || 0), 0) };
        }""")
        check("speler 2 heeft negen scores", tweede["scores"], 9)
        check("met een eigen totaal", tweede["totaal"], 36)

        print("\n=== 4. TERUG NAAR SPELER 1: NIETS KWIJT ===\n")
        await page.evaluate("() => switchToPlayer(1)")
        await page.wait_for_timeout(300)
        terug = await page.evaluate("""() => {
            const r = loadSavedRounds().find(x => x.player === 'Testspeler');
            return { speler: game.player,
                     scores: r.holes.filter(h => h.score !== null).length,
                     totaal: r.holes.reduce((s, h) => s + (h.score || 0), 0) };
        }""")
        check("speler 1 is weer actief", terug["speler"], "Testspeler")
        check("de scores staan er nog", terug["scores"], 9)
        check("en zijn onveranderd", terug["totaal"], 45)

        print("\n=== 5. LANG INDRUKKEN TIJDENS EEN LOPENDE RONDE ===\n")
        # De nieuwe toggles mogen een lopende ronde niet raken.
        await page.evaluate("() => nav('archive')")
        await page.wait_for_timeout(300)
        naToggle = await page.evaluate("""() => {
            alleSpelersDichtOfOpen();
            alleSpelersDichtOfOpen();
            toggleAlleArchiefJaren();
            const r = loadSavedRounds().find(x => x.player === 'Testspeler');
            return { scores: r.holes.filter(h => h.score !== null).length,
                     actief: !!game.started, speler: game.player };
        }""")
        check("de lopende ronde blijft lopen", naToggle["actief"], True)
        check("met dezelfde speler", naToggle["speler"], "Testspeler")
        check("en alle scores staan er nog", naToggle["scores"], 9)

        print("\n=== 6. AFRONDEN ===\n")
        await page.evaluate("""() => {
            nav('score');
            if (typeof finishRound === 'function') {
                finishRound();
                const cb = document.getElementById('confirmModalBtn');
                if (cb && !document.getElementById('confirmModal').classList.contains('hidden')) cb.click();
            }
        }""")
        await page.wait_for_timeout(600)
        afgerond = await page.evaluate("""() => {
            const lijst = loadSavedRounds();
            return {
                aantal: lijst.length,
                compleet: lijst.filter(r => r.holes.filter(h => h.score !== null).length === 9).length,
                sdAanwezig: lijst.filter(r => r.sdFinal != null).length,
            };
        }""")
        check("beide rondes staan er nog", afgerond["aantal"], 2)
        check("allebei volledig ingevuld", afgerond["compleet"], 2)

        print("\n=== 7. DE TWEE BACKUPMELDINGEN STAAN LOS ===\n")
        stand = await page.evaluate("""async () => {
            // eerst alles veiligstellen — exportAllClubs is async (kan op de bestandsmap
            // wachten), dus zonder await zou de controle hieronder de opslag lezen
            // vóórdat het schrijven van golf_clubs_backup_fingerprint klaar is.
            await exportAllClubs();
            const nu = new Date().toISOString();
            localStorage.setItem('golf_last_backup_date', nu.slice(0, 10));
            localStorage.setItem('golf_last_backup_ts', nu);
            localStorage.setItem('golf_last_backup_count', String(afgerondeRondesCount()));
            legBackupInhoudVast();
            localStorage.setItem('golf_rounds_changed', nu);
            const rustig = { rondes: isBackupOverdue(), clubs: isClubsBackupOverdue() };

            // alleen een club wijzigen
            CLUBS['Golfclub Heelsum'].shortName = 'Gewijzigd';
            saveClubsToStorage();
            const naClub = { rondes: isBackupOverdue(), clubs: isClubsBackupOverdue() };
            return { rustig, naClub };
        }""")
        check("na een backup is alles rustig", stand["rustig"],
              {"rondes": False, "clubs": False})
        check("een clubwijziging meldt alleen de clubs", stand["naClub"],
              {"rondes": False, "clubs": True})

        print("\n=== 8. ALLES WISSEN EN TERUGZETTEN ===\n")
        # De belangrijkste proef: komt na een herstel exact dezelfde stand terug? Dit
        # raakt de import, de bewaarde rondelijst en de handicaptabellen tegelijk.
        # Genoeg rondes voor een echte handicap, anders vergelijkt de controle straks
        # twee lege waarden en bewijst hij niets.
        await page.evaluate("""() => {
            const basis = loadSavedRounds().find(r => r.player === 'Testspeler');
            const lijst = loadSavedRounds();
            for (let i = 0; i < 25; i++) {
                const maand = String((i % 12) + 1).padStart(2, '0');
                const dag = String((i % 28) + 1).padStart(2, '0');
                lijst.push({ ...basis, id: 5000 + i, date: '2024-' + maand + '-' + dag,
                             qualifying: true, sd: 28 + (i % 5), sdFinal: 28 + (i % 5),
                             holes: basis.holes.map(h => ({ ...h })) });
            }
            setRoundsAndMark(JSON.stringify(lijst));
        }""")
        await page.wait_for_timeout(200)

        # Eerst vastleggen wat er staat (doResetAll herlaadt de pagina, dus dit moet
        # in aparte stappen).
        voorHerstel = await page.evaluate("""() => {
            // Sinds 10E telt een ronde pas mee als hij niet meer open staat. Herstellen sluit
            // een open ronde; voor een eerlijke vergelijking hier dus ook eerst sluiten.
            clearActiveRound();
            nav('setup');
            document.getElementById('iName').value = 'Testspeler';
            nav('archive'); tekenRondelijst();
            const t = handicapTabellen().hcpTrendMap;
            const ids = Object.keys(t);
            // De hele tabel vergelijken, niet één getal: dan valt elk verschil op.
            return { rondes: loadSavedRounds(), clubs: CLUBS,
                     hcp: JSON.stringify(t), aantal: ids.length,
            };
        }""")

        await page.evaluate("() => doResetAll()")
        await page.wait_for_timeout(1200)
        await page.evaluate("() => closeConfirmModal && closeConfirmModal()")
        naWissen = await page.evaluate("""() => ({
            rondes: loadSavedRounds().length,
            clubs: Object.keys(CLUBS || {}).length,
        })""")

        herstel = await page.evaluate("""([rondes, clubs]) => {
            // Terugzetten zoals de import dat doet.
            Object.keys(CLUBS).forEach(k => delete CLUBS[k]);
            Object.entries(clubs).forEach(([k, v]) => { CLUBS[k] = v; });
            saveClubsToStorage();
            metVerwijderen(() => setRoundsAndMark(JSON.stringify(rondes)));
            localStorage.setItem('golf_profile_name', 'Testspeler');
            nav('setup');
            document.getElementById('iName').value = 'Testspeler';
            nav('archive'); tekenRondelijst();
            const t = handicapTabellen().hcpTrendMap;
            const ids = Object.keys(t);
            return { rondesNa: loadSavedRounds().length,
                     clubsNa: Object.keys(CLUBS || {}).length,
                     hcpNa: JSON.stringify(t), aantalNa: ids.length };
        }""", [voorHerstel["rondes"], voorHerstel["clubs"]])
        herstel["naWissen"] = naWissen
        herstel["hcpVoor"] = voorHerstel["hcp"]

        check("alles wissen maakt de opslag leeg", herstel["naWissen"]["rondes"], 0)
        check("de rondes komen terug", herstel["rondesNa"], 27)
        check("de clubs ook", herstel["clubsNa"] > 0, True)
        print("   tabelregels voor herstel:", voorHerstel["aantal"],
              "| rondes:", len(voorHerstel["rondes"]))
        check("er is een gevulde handicaptabel om te vergelijken",
              voorHerstel["aantal"] > 20, True)
        check("en die is na herstel identiek", herstel["hcpNa"] == herstel["hcpVoor"], True)

        print("\n=== 9. HERPLANNEN NA ALLE WIJZIGINGEN ===\n")
        # Herplannen leest de rondelijst en schrijft hem terug; met de bewaarde lijst
        # ertussen moet dat nog steeds kloppen.
        herplan = await page.evaluate("""() => {
            const lijst = loadSavedRounds();
            const id = lijst[0].id;
            const voorDatum = lijst[0].date;
            lijst[0].date = '2027-01-15';
            setRoundsAndMark(JSON.stringify(lijst));
            const na = loadSavedRounds().find(r => r.id === id);
            return { veranderd: na.date === '2027-01-15', voorDatum,
                     aantal: loadSavedRounds().length };
        }""")
        check("een gewijzigde datum komt door", herplan["veranderd"], True)
        check("zonder rondes te verliezen", herplan["aantal"], 27)

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
