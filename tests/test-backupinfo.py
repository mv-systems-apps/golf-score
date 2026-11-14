import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(viewport={'width': 390, 'height': 780})
        fouten = []
        page.on('pageerror', lambda e: fouten.append(str(e)[:120]))
        await page.goto(app_url())
        await page.evaluate(SEED, [CLUBS, RONDES])
        await page.reload(); await page.wait_for_timeout(700)
        res = {}

        async def stand():
            return await page.evaluate("""() => {
                const top = document.getElementById('lastBackupInfoTop');
                const org = document.getElementById('lastBackupInfo');
                const topN = document.getElementById('newRoundsInfoTop');
                const orgN = document.getElementById('newRoundsInfo');
                return { top: top ? top.innerHTML : null, org: org ? org.innerHTML : null,
                         topN: topN ? topN.innerHTML : null, orgN: orgN ? orgN.innerHTML : null,
                         topTekst: top ? top.textContent.trim() : '',
                         topNTekst: topN ? topN.textContent.trim() : '',
                         topNVerborgen: topN ? topN.classList.contains('hidden') : null };
            }""")

        print('1. GELIJK NA ELKE AANROEP DIE DE STAND VERVERST\n')
        gevallen = [
            ("openen van Instellingen", "nav('settings')"),
            ("openen van Rondes (buiten Instellingen)", "nav('archive')"),
            ("na een backup", "naBackupBijwerken()"),
            ("na een import (toevoegen)", "updateLastBackupDisplay()"),
        ]
        for naam, code in gevallen:
            await page.evaluate("(c) => { nav('settings'); eval(c); }", code)
            await page.wait_for_timeout(150)
            s = await stand()
            gelijk = s['top'] == s['org'] and s['topN'] == s['orgN']
            res[naam] = gelijk
            print(f"   {naam:<40} gelijk: {str(gelijk):<6} \"{s['topTekst'][:34]}\"")

        print('\n2. RANDGEVALLEN VAN DE TWEEDE REGEL')
        randen = [
            ("nooit geback-upt", "localStorage.removeItem('golf_last_backup_date'); localStorage.removeItem('golf_last_backup_count');"),
            ("backup net gemaakt, niets nieuw", "localStorage.setItem('golf_last_backup_date', todayISO()); legBackupInhoudVast();"),
            ("wel gewijzigd, niets nieuw", "const l = loadSavedRounds(); const a = l.find(r => isRondeAf(r)); a.note = 'bewerkt ' + Date.now(); setRoundsAndMark(JSON.stringify(l));"),
            ("oude backup, veel nieuw", "localStorage.setItem('golf_last_backup_date', '2020-01-01'); localStorage.setItem('golf_backup_inhoud', '{}');"),
        ]
        for naam, code in randen:
            await page.evaluate("(c) => { eval(c); nav('settings'); updateLastBackupDisplay(); }", code)
            await page.wait_for_timeout(120)
            s = await stand()
            gelijk = s['top'] == s['org'] and s['topN'] == s['orgN']
            res['rand: ' + naam] = gelijk
            print(f"   {naam:<28} gelijk: {str(gelijk):<6} \"{s['topTekst'][:26]}\" | \"{s['topNTekst'][:22]}\" verborgen: {s['topNVerborgen']}")

        print('\n3. AFHANKELIJKHEID: werkt het ook zonder de Gegevens-tab te openen?')
        await page.reload(); await page.wait_for_timeout(600)
        s3 = await page.evaluate("""() => {
            nav('settings'); switchSettingsTab('main');
            const top = document.getElementById('lastBackupInfoTop');
            return { tekst: top.textContent.trim(), gevuld: top.textContent.trim().length > 0,
                     tabData: !document.getElementById('settingsTabData').classList.contains('hidden') };
        }""")
        print(f"   op tab Algemeen: \"{s3['tekst'][:40]}\" (Gegevens-tab open: {s3['tabData']})")
        res['zonderGegevensTab'] = s3['gevuld']

        print('\n4. AFHANKELIJKHEID: eerste start, nog nooit Instellingen geopend')
        await page.evaluate("() => localStorage.removeItem('golf_last_backup_date')")
        await page.reload(); await page.wait_for_timeout(800)
        s4 = await page.evaluate("""() => {
            const top = document.getElementById('lastBackupInfoTop');
            return { voorNav: top.textContent.trim() };
        }""")
        await page.evaluate("() => nav('settings')"); await page.wait_for_timeout(200)
        s4b = await page.evaluate("""() => document.getElementById('lastBackupInfoTop').textContent.trim()""")
        print(f"   vóór openen: \"{s4['voorNav'][:40]}\"")
        print(f"   ná openen  : \"{s4b[:40]}\"")
        res['naOpenenGevuld'] = len(s4b) > 0

        print('\n5. AFHANKELIJKHEID: exporteren vult beide regels bij')
        s5 = await page.evaluate("""() => {
            const voor = document.getElementById('lastBackupInfoTop').textContent.trim();
            localStorage.setItem('golf_last_backup_date', todayISO());
            localStorage.setItem('golf_last_backup_count', String(afgerondeRondesCount()));
            localStorage.setItem('golf_last_backup_ts', new Date().toISOString());
            legBackupInhoudVast();
            naBackupBijwerken();
            const na = document.getElementById('lastBackupInfoTop').textContent.trim();
            const org = document.getElementById('lastBackupInfo').textContent.trim();
            return { voor, na, org, gelijk: na === org, veranderd: voor !== na };
        }""")
        print(f"   vóór: \"{s5['voor'][:30]}\"  →  ná: \"{s5['na'][:30]}\"")
        print(f"   gelijk aan het origineel: {s5['gelijk']}, bijgewerkt: {s5['veranderd']}")
        res['naBackupBijgewerkt'] = s5['gelijk'] and s5['veranderd']

        # ── De kleur zit op de REDEN, niet op de datum ────────────────────
        # 'Gisteren' is op zichzelf geen probleem; het wordt er pas een doordat er
        # sindsdien iets is veranderd. De oranje kleur en de stip hingen eerder aan de
        # dagendrempel, en dat liet twee gevallen door: een backup van vanochtend met een
        # ronde van vanmiddag, en een bewerkte ronde — die telt in geen van beide
        # drempels mee, terwijl dat werk wél nergens anders staat.
        print("\n6. DE KLEUR VOLGT DE REDEN")
        s6 = await page.evaluate("""() => {
            const backupNu = () => {
                const nu = new Date().toISOString();
                localStorage.setItem('golf_last_backup_date', nu.slice(0, 10));
                localStorage.setItem('golf_last_backup_ts', nu);
                localStorage.setItem('golf_last_backup_count', String(afgerondeRondesCount()));
                legBackupInhoudVast();
                // Ook de clubs veilig zetten, anders kleurt die de stip. Rechtstreeks in
                // de opslag: exportAllClubs() legt de stand pas vast NA het wegschrijven
                // (bewust — anders zou een mislukte download toch 'veilig' melden), en
                // dat is asynchroon.
                localStorage.setItem('golf_clubs_backup_date', nu.slice(0, 10));
                localStorage.setItem('golf_clubs_backup_fingerprint', clubsVingerafdruk());
                updateLastBackupDisplay();
            };
            const lees = () => {
                updateLastBackupDisplay();
                const oranje = el => {
                    const sp = el && el.querySelector('span');
                    return !!(sp && sp.style.color.includes('orange'));
                };
                const datum = document.getElementById('lastBackupInfoTop');
                const reden = document.getElementById('newRoundsInfoTop');
                return {
                    datumOranje: oranje(datum),
                    redenZichtbaar: !!reden && !reden.classList.contains('hidden'),
                    redenOranje: oranje(reden),
                    redenTekst: reden && !reden.classList.contains('hidden')
                        ? reden.textContent.trim() : '',
                    stip: document.getElementById('tab-settings').classList.contains('has-dot'),
                };
            };

            // Drempels op hun scherpst, zodat elke wijziging meteen dringend is.
            storage.setItem('golf_backup_reminder_days', '1');
            storage.setItem('golf_backup_reminder_rounds', '1');
            backupNu();
            const rustig = lees();

            // Een ronde erbij, ná de backup van vandaag.
            const basis = loadSavedRounds()[0];
            const lijst = loadSavedRounds();
            lijst.push({ ...basis, id: 8801, date: '2026-07-07',
                         holes: basis.holes.map(h => ({ ...h })) });
            setRoundsAndMark(JSON.stringify(lijst));
            const naNieuwe = lees();

            // Nu alleen een BESTAANDE ronde bewerken.
            backupNu();
            const l2 = loadSavedRounds();
            l2[0].note = 'bewerkt';
            setRoundsAndMark(JSON.stringify(l2));
            const naBewerken = lees();

            return { rustig, naNieuwe, naBewerken };
        }""")
        print(f"   rustig       : reden zichtbaar {s6['rustig']['redenZichtbaar']}, stip {s6['rustig']['stip']}")
        print(f"   nieuwe ronde : {s6['naNieuwe']['redenTekst'][:40]!r}, stip {s6['naNieuwe']['stip']}")
        print(f"   bewerkt      : {s6['naBewerken']['redenTekst'][:40]!r}, stip {s6['naBewerken']['stip']}")

        res['rustigGeenReden'] = (not s6['rustig']['redenZichtbaar']
                                  and not s6['rustig']['stip']
                                  and not s6['rustig']['datumOranje'])
        # Bij nieuwe rondes staat het woord 'gewijzigd' er NIET bij: een nieuwe ronde ís
        # de wijziging. Het moment blijft wel staan, want dat is het enige wat verandert
        # als je daarna nog iets bewerkt — en die twee kan de app niet onderscheiden.
        # Eén tekst voor alle gevallen: geen aantal en geen tijdstip. De handeling is
        # hetzelfde of er nu één ronde bij is of drie plus wat bewerkingen.
        # De TOON verschilt wel: grijs zolang je drempel niet gehaald is, oranje daarna.
        # In deze proef staat de backup op vandaag en is er één ronde bij, dus met de
        # standaarddrempels (1 dag / 1 ronde) is dat meteen dringend.
        res['nieuweRondeOranje'] = (s6['naNieuwe']['redenOranje']
                                    and s6['naNieuwe']['stip']
                                    and not s6['naNieuwe']['datumOranje']
                                    and s6['naNieuwe']['redenTekst']
                                        == 'Wijzigingen sinds laatste backup')
        # Het geval dat eerder helemaal geen signaal gaf.
        # Alleen een bewerking, op dezelfde dag als de backup. Met de drempels op hun
        # scherpst (1 dag / 1 wijziging) telt die bewerking mee: een vastgesteld
        # dagresultaat of een gecorrigeerde score is net zo goed werk dat je kwijt kunt
        # raken. Dus ORANJE met een stip.
        res['bewerktOranje'] = (s6['naBewerken']['redenOranje']
                                and s6['naBewerken']['stip']
                                and s6['naBewerken']['redenTekst']
                                    == 'Wijzigingen sinds laatste backup')

        # ── De drempels bepalen de toon ─────────────────────────────────────
        # Grijs zolang je drempel niet gehaald is, oranje daarna. Eerder was alles
        # oranje zodra er iets veranderde, en daarmee deden de drempels niets meer.
        print("\n7. VASTE REGEL: OOK MET OUDE DREMPELWAARDEN IN DE OPSLAG ORANJE")
        s7 = await page.evaluate("""() => {
            const stel = (dagen, rondes, nieuw, dagenOud) => {
                storage.setItem('golf_backup_reminder_days', String(dagen));
                storage.setItem('golf_backup_reminder_rounds', String(rondes));
                const t = new Date();
                t.setDate(t.getDate() - dagenOud);
                const ts = t.toISOString();
                localStorage.setItem('golf_last_backup_date', ts.slice(0, 10));
                localStorage.setItem('golf_last_backup_ts', ts);
                // Backup vastleggen, en daarna doen alsof de laatste 'nieuw' rondes er
                // toen nog niet in zaten.
                legBackupInhoudVast();
                const inh = JSON.parse(localStorage.getItem('golf_backup_inhoud'));
                Object.keys(inh).slice(0, nieuw).forEach(k => delete inh[k]);
                localStorage.setItem('golf_backup_inhoud', JSON.stringify(inh));
                exportAllClubs();
                updateLastBackupDisplay();
                const el = document.getElementById('newRoundsInfo');
                const sp = el && !el.classList.contains('hidden') ? el.querySelector('span') : null;
                return {
                    oranje: !!(sp && sp.style.color.includes('orange')),
                    regel: !!sp,
                    stip: document.getElementById('tab-settings').classList.contains('has-dot'),
                };
            };
            return {
                // Drempels 7 dagen / 2 rondes:
                eenRondeVandaag: stel(7, 2, 1, 0),
                tweeRondes:      stel(7, 2, 2, 0),
                dagenGehaald:    stel(7, 2, 1, 8),
                // Drempels 1 dag / 1 ronde: alles meteen dringend.
                scherp:          stel(1, 1, 1, 0),
            };
        }""")
        print(f"   1 ronde binnen de drempel : {s7['eenRondeVandaag']}")
        print(f"   2 rondes (drempel gehaald): {s7['tweeRondes']}")
        print(f"   8 dagen oud               : {s7['dagenGehaald']}")
        print(f"   drempels op 1/1           : {s7['scherp']}")

        # Sinds de drempels vervallen zijn (vaste regel): elke situatie met iets buiten de
        # backup is oranje met een stip, ook als er nog oude drempelwaarden in de opslag staan.
        res['vasteRegelAllesOranje'] = all(v['oranje'] and v['stip'] for v in s7.values())

        # ── 8. De clubregel verdwijnt METEEN na een clubbackup ───────────────
        # De datum werd wel opgeslagen, maar de regel bleef "Backup clubs: nog nooit"
        # tonen tot je van scherm wisselde — alsof de export was mislukt. De backup van
        # de rondes ververste die regels al; de clubexport deed dat niet.
        print("\n8. DE CLUBREGEL NA EEN CLUBBACKUP")
        s8voor = await page.evaluate("""() => {
            localStorage.removeItem('golf_clubs_backup_date');
            localStorage.removeItem('golf_clubs_backup_fingerprint');
            nav('settings');
            switchSettingsTab('data');
            toonClubBackupRegel();
            refreshTabDot();
            const e = document.getElementById('clubBackupInfoTop');
            const regel = e && !e.classList.contains('hidden') ? e.textContent.trim() : '(weg)';
            // Op de ECHTE knop tikken: het gaat om wat je op het scherm ziet gebeuren.
            const knop = [...document.querySelectorAll('#settingsTabData button')]
                .find(b => (b.getAttribute('onclick') || '') === 'exportAllClubs()');
            if (knop) knop.click();
            return { regel, knopGevonden: !!knop };
        }""")
        await page.wait_for_timeout(700)
        s8na = await page.evaluate("""() => {
            const e = document.getElementById('clubBackupInfoTop');
            return {
                regel: e && !e.classList.contains('hidden') ? e.textContent.trim() : '(weg)',
                stip: document.getElementById('tab-settings').classList.contains('has-dot'),
                datum: localStorage.getItem('golf_clubs_backup_date'),
            };
        }""")
        print(f"   vóór : {s8voor['regel']!r}")
        print(f"   ná   : {s8na['regel']!r}, stip {s8na['stip']}")
        res['clubknopGevonden'] = s8voor['knopGevonden']
        res['clubregelVooraf'] = s8voor['regel'] == 'Backup clubs: nog nooit'
        res['clubregelMeteenWeg'] = s8na['regel'] == '(weg)'
        res['clubdatumVastgelegd'] = s8na['datum'] is not None
        # De STIP wordt hier niet getoetst: die hangt ook aan de rondes, en die staan in
        # deze proef nog niet veilig. De stip hoort dus aan te blijven.

        # ── 9. Een BEWERKING telt als wijziging ──────────────────────────────
        # De tweede drempel telde alleen NIEUWE rondes. Een dagresultaat vaststellen of
        # een score corrigeren telde nergens mee: met de drempels op 1 dag en 1 bleef
        # zo'n bewerking grijs tot de volgende dag, terwijl dat de scherpste stand is.
        print("\n9. EEN BEWERKING TELT ALS WIJZIGING")
        s9 = await page.evaluate("""() => {
            const meet = (dagen, drempel) => {
                storage.setItem('golf_backup_reminder_days', String(dagen));
                storage.setItem('golf_backup_reminder_rounds', String(drempel));
                // Verse backup van vandaag, met de huidige rondes geteld.
                const nu = new Date();
                localStorage.setItem('golf_last_backup_date', new Date(nu.getTime() - nu.getTimezoneOffset() * 60000).toISOString().slice(0, 10));
                localStorage.setItem('golf_last_backup_ts', nu.toISOString());
                legBackupInhoudVast();
                // Eén BEWERKING: geen ronde erbij, wel één ronde met andere inhoud.
                const inh = JSON.parse(localStorage.getItem('golf_backup_inhoud'));
                inh[Object.keys(inh)[0]] = 'anders';
                localStorage.setItem('golf_backup_inhoud', JSON.stringify(inh));
                return { onveilig: isErIetsOnveiligs(), dringend: isBackupOverdue() };
            };
            return { scherp: meet(1, 1), ruim: meet(7, 2) };
        }""")
        print(f"   drempels 1/1 : {s9['scherp']}")
        print(f"   drempels 7/2 : {s9['ruim']}")
        # Bij 1 wijziging en drempel 1 is het dringend; bij drempel 2 nog niet.
        res['bewerkingTeltMee'] = s9['scherp']['dringend'] is True
        res['bewerkingOokMetOudeDrempelDringend'] = (s9['ruim']['onveilig'] is True
                                                     and s9['ruim']['dringend'] is True)

        # ── 9. Een BEWERKING telt als wijziging ──────────────────────────────
        # De tweede drempel telde alleen nieuwe rondes. Een dagresultaat vaststellen of
        # een score corrigeren is net zo goed werk dat je kwijt kunt raken, maar bleef
        # daardoor grijs tot de dagendrempel verstreek — ook met de drempels op 1.
        print("\n9. EEN BEWERKING TELT ALS WIJZIGING")
        s9 = await page.evaluate("""() => {
            const lees = () => {
                const e = document.getElementById('newRoundsInfoTop');
                const sp = e && !e.classList.contains('hidden') ? e.querySelector('span') : null;
                return {
                    oranje: !!(sp && sp.style.color.includes('orange')),
                    regel: !!sp,
                    stip: document.getElementById('tab-settings').classList.contains('has-dot'),
                };
            };
            // Verse backup: niets te bewaren.
            storage.setItem('golf_backup_reminder_days', '7');
            storage.setItem('golf_backup_reminder_rounds', '1');
            const nu = new Date().toISOString();
            localStorage.setItem('golf_last_backup_date', nu.slice(0, 10));
            localStorage.setItem('golf_last_backup_ts', nu);
            legBackupInhoudVast();
            updateLastBackupDisplay();
            refreshTabDot();
            const rustig = lees();

            // Eén bewerking: geen nieuwe ronde, wel werk. Ruim ná de backup, anders
            // vallen de tijdstempels in dezelfde milliseconde.
            const l = loadSavedRounds();
            const af = l.find(r => isRondeAf(r));
            if (af) { af.sdFinal = 29.4; setRoundsAndMark(JSON.stringify(l)); }
            updateLastBackupDisplay();
            refreshTabDot();
            const naBewerking = lees();

            // Met de drempel op 3 is één bewerking niet genoeg: grijs, geen stip.
            storage.setItem('golf_backup_reminder_rounds', '3');
            updateLastBackupDisplay();
            refreshTabDot();
            const drempelDrie = lees();

            return { rustig, naBewerking, drempelDrie };
        }""")
        print(f"   verse backup      : {s9['rustig']}")
        print(f"   na één bewerking  : {s9['naBewerking']}")
        print(f"   drempel op 3      : {s9['drempelDrie']}")
        # Een verse backup hoort stil te zijn: zonder deze controle telde de bewerking er
        # ook één als er nooit iets gewijzigd was.
        res['verseBackupStil'] = not s9['rustig']['regel'] and not s9['rustig']['stip']
        res['bewerkingIsWijziging'] = s9['naBewerking']['oranje'] and s9['naBewerking']['stip']
        res['ookMetOudeDrempelDrieOranje'] = (s9['drempelDrie']['oranje']
                                              and s9['drempelDrie']['stip'])

        alles = all(res.values())
        print('\n' + ('GEEN FOUTEN' if alles and not fouten else
                      '1 FOUT(EN): ' + ', '.join(k for k, v in res.items() if not v)))
        if fouten: print('browserfouten:', fouten)
        await b.close()

asyncio.run(main())
