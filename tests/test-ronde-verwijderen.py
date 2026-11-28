"""Een ronde verwijderen (13528FB-002).

Verwijderen zit in Bewerken (de prullenbak naast Annuleren en Opslaan): twee tikken, dan het
rode bevestigvenster. Het menu van het potlood heeft geen Verwijderen. Nieuw: het rode
bevestigvenster past ook op een smal scherm ('Verwijderen' stak bij 300 px breed over de
rand; nu 340 breed, en op een heel smal scherm de knoppen onder elkaar), en de datum in de
tekst breekt niet af (vaste koppeltekens). Na verwijderen vanaf het scorescherm is dat scherm
bijgewerkt. Het gewone bevestigvenster (confirmModal) kreeg dezelfde breedte en knoppen. Datums
midden in een zin (datumInZin): de datum, met (vandaag) of (morgen) erachter; ook in 'Ronde
vervangen?' (dat nu 'herpland' zegt) en bij Oude rondes verwijderen.

Vanaf de kaart op het scorescherm met twee spelers verdwijnen beide rondes van dat moment
(13528FC-006), met de gespeelde holes per speler in de tekst; in Rondes blijft het één ronde.
Bewerken vanaf zo'n kaart opent een eigen venster Ronde bewerken (één ronde, twee spelers): datum en tijd één keer
voor beide, per speler naam, qualifying (Q) en notitie.

Via de echte bediening: het potlood op het scorescherm, Bewerken, de prullenbak en het venster.
"""
import asyncio, os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

async def ev(pg, js, arg=None):
    try:
        return await pg.evaluate(js, arg)
    except Exception as e:
        return 'FOUT: ' + str(e).split('\n')[0][:120]

async def klik(pg, sel):
    try: await pg.locator(sel).first.click(timeout=2000); await pg.wait_for_timeout(250); return True
    except Exception: return False

HIER = os.path.dirname(os.path.abspath(__file__))
PLAN = open(os.path.join(HIER, 'test-op-deze-baan.py')).read().split('PLAN = """')[1].split('"""')[0]
def dag(n): return (datetime.date.today() + datetime.timedelta(days=n)).isoformat()

MENU = """() => { const m = document.getElementById('roundEditChoiceModal'); if (!m || m.classList.contains('hidden')) return null;
  return [...m.querySelectorAll('button')].filter(b => !b.classList.contains('hidden')).map(b => b.textContent.trim()); }"""
GEVAAR = """() => { const m = document.getElementById('resetAllModal'); if (!m || m.classList.contains('hidden')) return null;
  return [document.getElementById('dangerModalTitle').textContent, document.getElementById('dangerModalMessage').textContent]; }"""
BESTAAT = "(id) => loadSavedRounds().some(r => String(r.id) === String(id))"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 390, 'height': 844})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        for i, d in enumerate((6, 9)):
            await ev(pg, PLAN % dag(d), [990101 + i, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', None])
        await ev(pg, "() => { nav('score'); verversLegeScoreKnoppen(); }"); await pg.wait_for_timeout(300)

        print("\n=== 1. HET MENU: GEEN VERWIJDEREN ===\n")
        await klik(pg, '#scoreEmptyMsg .lege-open[data-regel="gepland:990101"] .lege-knop-bewerk')
        menu = await ev(pg, MENU)
        check("het menu staat open, zonder Verwijderen", isinstance(menu, list) and 'Verwijderen' not in menu, True)

        print("\n=== 2. BEWERKEN: PRULLENBAK, TWEE TIKKEN, DAN HET RODE VENSTER ===\n")
        await klik(pg, '#roundEditChoiceInfo')
        prul = '#roundInfoModal button[onclick="deleteRoundFromInfoModal(this)"]'
        check("Bewerken heeft de prullenbak", await ev(pg, f"() => !!document.querySelector('{prul}')"), True)
        await klik(pg, prul)
        check("één tik: nog geen rood venster", await ev(pg, GEVAAR), None)
        await klik(pg, prul)
        g = await ev(pg, GEVAAR)
        check("tweede tik: het rode venster", g and g[0], 'Ronde verwijderen')
        check("met de datum van de ronde, die niet afbreekt (vaste koppeltekens)", bool(g) and isinstance(g, list) and dag(6)[8:10].lstrip('0') + '\u2011' in g[1], True)
        # Midden in de zin altijd de datum, met (vandaag) of (morgen) erachter; niet 'op Vandaag'
        tekst = await ev(pg, """() => { const z = iso => { const n = d => { const x = new Date(); x.setDate(x.getDate() + d); return x.getFullYear() + '-' + String(x.getMonth() + 1).padStart(2, '0') + '-' + String(x.getDate()).padStart(2, '0'); };
            return typeof datumInZin === 'function' ? [datumInZin(n(0)), datumInZin(n(1)), datumInZin(n(-1)), datumInZin(n(6))].map(t => t.replace(/\\d+\\u2011\\d+\\u2011\\d{4}/, 'D')) : null; }; return z(); }""")
        check("datum in de zin: vandaag, morgen, gisteren, later", tekst, ['D (vandaag)', 'D (morgen)', 'D', 'D'])
        await klik(pg, '#dangerModalCancelBtn')
        check("Annuleren: de ronde staat er nog", await ev(pg, BESTAAT, 990101), True)
        await klik(pg, prul); await klik(pg, prul)
        await klik(pg, '#dangerModalConfirmBtn')
        check("Verwijderen: de ronde is weg", await ev(pg, BESTAAT, 990101), False)
        check("het scorescherm is bijgewerkt: de volgende staat open",
              await ev(pg, "() => [...document.querySelectorAll('#scoreEmptyMsg [data-regel^=gepland]')].map(e => e.dataset.regel)"), ['gepland:990102'])

        print("\n=== 3. HET BEVESTIGVENSTER PAST ===\n")
        for w in (320, 360, 390):
            await pg.set_viewport_size({'width': w, 'height': 800})
            past = await ev(pg, """() => { showDangerModal('Ronde verwijderen', 'x', 'Verwijderen', () => {}); const v = document.querySelector('#resetAllModal > div'), box = v.getBoundingClientRect(), c = getComputedStyle(v);
                // de binnenkant: zonder rand en padding (anders past een knop die in de padding steekt ook)
                const links = box.left + parseFloat(c.borderLeftWidth) + parseFloat(c.paddingLeft), rechts = box.right - parseFloat(c.borderRightWidth) - parseFloat(c.paddingRight);
                const ok = [...document.querySelectorAll('#resetAllModal button')].every(k => { const r = k.getBoundingClientRect(); return r.left >= links - 0.5 && r.right <= rechts + 0.5 && k.scrollWidth <= k.clientWidth; });
                document.getElementById('resetAllModal').classList.add('hidden'); return ok; }""")
            check(f"{w} px: Annuleren en Verwijderen binnen de binnenkant van het venster", past, True)

        print("\n=== 4. HET GEWONE BEVESTIGVENSTER PAST OOK ===\n")
        # Zelfde aanpak in confirmModal: bij 300 breed stak 'Overschrijven' over de rand.
        for w in (320, 360, 390):
            await pg.set_viewport_size({'width': w, 'height': 800})
            past = await ev(pg, """() => { const paren = [['Annuleren', 'Overschrijven'], ['Overslaan', 'Overschrijven'], ['Annuleren', 'Toch starten'], ['Annuleren', 'Toch opslaan'], ['Annuleren', 'Aanpassen']];
                return paren.every(([n, j]) => { showConfirmModal('Club bestaat al', 'x', () => {}, n, null, j);
                  const v = document.querySelector('#confirmModal > div'), box = v.getBoundingClientRect(), c = getComputedStyle(v);
                  const links = box.left + parseFloat(c.borderLeftWidth) + parseFloat(c.paddingLeft), rechts = box.right - parseFloat(c.borderRightWidth) - parseFloat(c.paddingRight);
                  const ok = [...document.querySelectorAll('#confirmModal button')].filter(k => k.offsetParent).every(k => { const r = k.getBoundingClientRect(); return r.left >= links - 0.5 && r.right <= rechts + 0.5 && k.scrollWidth <= k.clientWidth; });
                  closeConfirmModal(); return ok; }); }""")
            check(f"{w} px: alle knopparen binnen de binnenkant van het venster", past, True)

        print("\n=== 5. DATUMS IN ANDERE ZINNEN ===\n")
        # 'Ronde vervangen?' na een uitstapje tijdens herplannen: datum met (vandaag)/(morgen), 'herpland'
        await ev(pg, "() => { nav('score'); }")
        r = await ev(pg, """() => { const id = String(loadSavedRounds().find(x => x.id === 990102)?.id || ''); if (!id) return null;
            herplanRonde(id); nav('score'); nav('setup'); startRound();
            const t = document.getElementById('keuzeModalTekst')?.textContent || ''; document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); annuleerHerplan(); return t; }""")
        check("'Ronde vervangen?': 'herpland', datum met vaste koppeltekens", isinstance(r, str) and 'wordt herpland' in r and '\u2011' in r and 'opnieuw gepland' not in r, True)
        print("\n=== 6. TWEE SPELERS OP ÉÉN KAART (SCORESCHERM): BEIDE WEG ===\n")
        # Sinds 13528FC-006: verwijderen vanaf de kaart op het scorescherm haalt beide rondes van
        # dat moment weg (ze staan daar op één kaart); in Rondes blijft het één ronde.
        await pg.set_viewport_size({'width': 390, 'height': 844})
        hoofd = await ev(pg, "() => startPlayerName()")
        await ev(pg, PLAN % dag(8), [990201, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', hoofd])
        await ev(pg, PLAN % dag(8), [990202, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', 'Medespeler'])
        await ev(pg, "() => { _legeOpen.gepland = '990201,990202'; nav('score'); verversLegeScoreKnoppen(); }"); await pg.wait_for_timeout(250)
        async def via_kaart(sel_kaart):
            await klik(pg, sel_kaart + ' .lege-knop-bewerk'); await klik(pg, '#roundEditChoiceInfo')
            prul = '#rondesBewerkenModal button[onclick="verwijderRondesBewerken(this)"]'
            await klik(pg, prul); await klik(pg, prul)
            return await ev(pg, GEVAAR)
        g = await via_kaart('#scoreEmptyMsg .lege-open[data-regel="gepland:990201,990202"]')
        check("geplande kaart met twee spelers: 'Ronde verwijderen', beide namen, zonder holes",
              isinstance(g, list) and [g[0], g[1].startswith(f'De ronde van {hoofd} en Medespeler op '), 'holes' not in g[1], g[1].endswith('wordt definitief verwijderd. Dit kan niet ongedaan worden gemaakt.')], ['Ronde verwijderen', True, True, True])
        await klik(pg, '#dangerModalConfirmBtn')
        check("na één bevestiging: beide rondes weg", await ev(pg, "() => loadSavedRounds().filter(r => r.id === 990201 || r.id === 990202).length"), 0)
        check("en de kaart van het scorescherm", await ev(pg, "() => !!document.querySelector('#scoreEmptyMsg [data-regel*=\"990201\"]')"), False)

        # gepauzeerd, verschillend aantal holes: per speler
        await ev(pg, PLAN % dag(-3), [990301, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', hoofd])
        await ev(pg, PLAN % dag(-3), [990302, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', 'Medespeler'])
        await ev(pg, """() => { const s = loadSavedRounds(); s.forEach(r => { if (r.id === 990301) r.holes.forEach((h, i) => { if (i < 5) h.score = 5; });
            if (r.id === 990302) r.holes.forEach((h, i) => { if (i < 4) h.score = 6; }); }); setRoundsAndMark(JSON.stringify(s));
            _legeOpen.gepauzeerd = '990301,990302'; localStorage.removeItem('golf_lege_verkort'); nav('score'); verversLegeScoreKnoppen(); }"""); await pg.wait_for_timeout(250)
        tot = await ev(pg, "() => loadSavedRounds().find(r => r.id === 990301).holes.length")
        g = await via_kaart('#scoreEmptyMsg .lege-open[data-regel="gepauzeerd:990301,990302"]')
        check("gepauzeerd, verschillend: holes per speler", isinstance(g, list) and f'{hoofd} (5 van {tot} holes) en Medespeler (4 van {tot} holes)' in g[1].replace(chr(160), ' ') and f'5{chr(160)}van{chr(160)}{tot}{chr(160)}holes' in g[1], True)
        await klik(pg, '#dangerModalCancelBtn')
        check("annuleren: beide staan er nog", await ev(pg, "() => loadSavedRounds().filter(r => r.id === 990301 || r.id === 990302).length"), 2)
        await ev(pg, "() => { const s = loadSavedRounds(); s.find(r => r.id === 990302).holes.forEach((h, i) => { h.score = i < 5 ? 6 : null; }); setRoundsAndMark(JSON.stringify(s)); sluitRondesBewerken(); nav('score'); verversLegeScoreKnoppen(); }"); await pg.wait_for_timeout(200)
        g = await via_kaart('#scoreEmptyMsg .lege-open[data-regel="gepauzeerd:990301,990302"]')
        check("gepauzeerd, gelijk: één keer achter de tijd", isinstance(g, list) and f'(5 van {tot} holes gespeeld) wordt' in g[1].replace(chr(160), ' '), True)
        await klik(pg, '#dangerModalConfirmBtn')
        check("bevestigd: beide gepauzeerde rondes weg", await ev(pg, "() => loadSavedRounds().filter(r => r.id === 990301 || r.id === 990302).length"), 0)

        # in Rondes: alleen de ene ronde
        await ev(pg, PLAN % dag(9), [990401, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', hoofd])
        await ev(pg, PLAN % dag(9), [990402, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', 'Medespeler'])
        await ev(pg, "() => { nav('archive'); const i = loadSavedRounds().findIndex(r => r.id === 990401); openRoundEditChoice(i); }"); await pg.wait_for_timeout(200)
        await klik(pg, '#roundEditChoiceInfo')
        prul = '#roundInfoModal button[onclick="deleteRoundFromInfoModal(this)"]'
        await klik(pg, prul); await klik(pg, prul)
        g = await ev(pg, GEVAAR)
        check("in Rondes: 'Ronde verwijderen', één speler", isinstance(g, list) and [g[0], 'Medespeler' in g[1]], ['Ronde verwijderen', False])
        await klik(pg, '#dangerModalConfirmBtn')
        check("in Rondes: alleen die ronde weg, de medespeler blijft", await ev(pg, "() => [loadSavedRounds().some(r => r.id === 990401), loadSavedRounds().some(r => r.id === 990402)]"), [False, True])
        print("\n=== 7. RONDE BEWERKEN MET TWEE SPELERS (EIGEN VENSTER) ===\n")
        # Een eigen venster: datum en tijd één keer voor beide, per speler naam, Q en notitie.
        await ev(pg, PLAN % dag(10), [990501, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', hoofd])
        await ev(pg, PLAN % dag(10), [990502, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', 'Medespeler'])
        await ev(pg, "() => { const s = loadSavedRounds(); s.find(r => r.id === 990502).qualifying = false; setRoundsAndMark(JSON.stringify(s)); _legeOpen.gepland = '990501,990502'; localStorage.removeItem('golf_lege_verkort'); localStorage.setItem('golf_lege_lijst_n', '10'); nav('score'); verversLegeScoreKnoppen(); }"); await pg.wait_for_timeout(250)
        await klik(pg, '#scoreEmptyMsg .lege-open[data-regel="gepland:990501,990502"] .lege-knop-bewerk')
        check("menu: 'Ronde bewerken' (één ronde, twee spelers)", await ev(pg, "() => document.getElementById('roundEditChoiceInfo')?.textContent.trim()"), 'Ronde bewerken')
        await klik(pg, '#roundEditChoiceInfo')
        v = await ev(pg, """() => { const m = document.getElementById('rondesBewerkenModal'); if (!m || m.classList.contains('hidden')) return null;
            return [m.querySelector('h2').textContent, rbNaam1.value, rbNaam2.value, rbQ1.checked, rbQ2.checked, !!rbDatum.value, document.getElementById('roundInfoModal').classList.contains('hidden')]; }""")
        check("eigen venster met beide spelers, hun Q, en één datum", v, ['Ronde bewerken', hoofd, 'Medespeler', True, False, True, True])
        await ev(pg, f"() => {{ rbDatum.value = '{dag(11)}'; rbTijd.value = '09:12'; rbNaam2.value = 'Medespeelster'; rbQ2.checked = true; rbNotitie1.value = 'Clubcompetitie'; }}")
        await klik(pg, '#rondesBewerkenModal .btn-primary'); await pg.wait_for_timeout(150)
        r = await ev(pg, "() => loadSavedRounds().filter(r => r.id === 990501 || r.id === 990502).sort((a, b) => a.id - b.id).map(r => [r.date + ' ' + r.time, r.player, !!r.qualifying, r.note || null])")
        check("Opslaan: datum en tijd voor beide, naam/Q/notitie per speler", r, [[f'{dag(11)} 09:12', hoofd, True, 'Clubcompetitie'], [f'{dag(11)} 09:12', 'Medespeelster', True, None]])
        await ev(pg, "() => { nav('score'); verversLegeScoreKnoppen(); }")
        check("op het scorescherm nog één kaart met beide", await ev(pg, "() => [...document.querySelectorAll('#scoreEmptyMsg [data-regel*=\"990501\"]')].map(e => e.dataset.regel)"), ['gepland:990501,990502'])
        # twee keer dezelfde naam, en een ronde van een speler al op het doelmoment: niets opgeslagen
        await ev(pg, "() => openRondesBewerken(['990501', '990502'])")
        await ev(pg, f"() => {{ rbNaam2.value = '{hoofd}'; }}"); await klik(pg, '#rondesBewerkenModal .btn-primary'); await pg.wait_for_timeout(150)
        check("twee keer dezelfde naam: melding, niets opgeslagen", [await ev(pg, "() => document.getElementById('confirmModalTitle')?.textContent"), await ev(pg, "() => loadSavedRounds().find(r => r.id === 990502).player")], ['Twee keer dezelfde speler', 'Medespeelster'])
        await ev(pg, "() => document.querySelectorAll('#confirmModal').forEach(m => m.classList.add('hidden'))")
        await ev(pg, PLAN % dag(12), [990503, 'Golfclub De Hoeve', 'Akkerweg', 'Blauw', 'Medespeelster'])
        await ev(pg, f"() => {{ openRondesBewerken(['990501', '990502']); rbDatum.value = '{dag(12)}'; rbTijd.value = '10:51'; }}")
        await klik(pg, '#rondesBewerkenModal .btn-primary'); await pg.wait_for_timeout(150)
        check("speler 2 heeft al een ronde op dat moment: 'Ronde bestaat al', niets verhuisd",
              [await ev(pg, "() => document.getElementById('confirmModalTitle')?.textContent"), await ev(pg, "() => loadSavedRounds().filter(r => r.id === 990501 || r.id === 990502).map(r => r.time)")], ['Ronde bestaat al', ['09:12', '09:12']])
        await ev(pg, "() => { document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); sluitRondesBewerken(); }")
        # in Rondes: het gewone venster, alleen die ene ronde
        await ev(pg, "() => { nav('archive'); const i = loadSavedRounds().findIndex(r => r.id === 990501); openRoundEditChoice(i); }"); await pg.wait_for_timeout(200)
        check("in Rondes heet het 'Bewerken'", await ev(pg, "() => document.getElementById('roundEditChoiceInfo')?.textContent.trim()"), 'Bewerken')
        await klik(pg, '#roundEditChoiceInfo')
        await ev(pg, "() => { document.getElementById('editTimeInput').value = '08:00'; }")
        await klik(pg, '#roundInfoModal .btn-primary'); await pg.wait_for_timeout(150)
        check("in Rondes verhuist alleen die ene ronde", await ev(pg, "() => loadSavedRounds().filter(r => r.id === 990501 || r.id === 990502).sort((a, b) => a.id - b.id).map(r => r.time)"), ['08:00', '09:12'])
        # (Rondes verplaatste net één ronde: eerst weer samen op één moment, zoals op een kaart)
        await ev(pg, f"() => {{ const s = loadSavedRounds(); s.filter(r => r.id === 990501 || r.id === 990502).forEach(r => {{ r.date = '{dag(11)}'; r.time = '09:12'; }}); setRoundsAndMark(JSON.stringify(s)); }}")
        # speler 2 mag niet jouw naam krijgen (zoals op Start); alleen een notitie wijzigen mag ook
        # als er nog een ronde op hetzelfde moment staat; "Dubbele datum & tijd" bij een nieuw moment
        await ev(pg, f"() => {{ openRondesBewerken(['990501', '990502']); rbNaam1.value = 'Anders'; rbNaam2.value = '{hoofd}'; }}")
        await klik(pg, '#rondesBewerkenModal .btn-primary'); await pg.wait_for_timeout(150)
        check("speler 2 jouw naam: melding, niets opgeslagen", [await ev(pg, "() => document.getElementById('confirmModalTitle')?.textContent"), await ev(pg, "() => loadSavedRounds().filter(r => r.id === 990501 || r.id === 990502).sort((a, b) => a.id - b.id).map(r => r.player)")], ['Speler 2', [hoofd, 'Medespeelster']])
        await ev(pg, "() => { document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); sluitRondesBewerken(); }")
        await ev(pg, f"() => {{ const s = loadSavedRounds(); const b = s.find(r => r.id === 990501); s.push({{ ...b, id: 990504, player: 'Derde', date: '{dag(11)}', time: '09:12' }}); setRoundsAndMark(JSON.stringify(s)); }}")
        await ev(pg, "() => { openRondesBewerken(['990501', '990502']); rbNotitie2.value = 'Alleen een notitie'; }")
        await klik(pg, '#rondesBewerkenModal .btn-primary'); await pg.wait_for_timeout(150)
        check("alleen een notitie, met een derde ronde op hetzelfde moment: opgeslagen", await ev(pg, "() => loadSavedRounds().find(r => r.id === 990502).note"), 'Alleen een notitie')
        await ev(pg, f"() => {{ document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); const s = loadSavedRounds(); const b = s.find(r => r.id === 990504); b.date = '{dag(13)}'; b.time = '11:00'; setRoundsAndMark(JSON.stringify(s)); openRondesBewerken(['990501', '990502']); rbDatum.value = '{dag(13)}'; rbTijd.value = '11:00'; }}")
        await klik(pg, '#rondesBewerkenModal .btn-primary'); await pg.wait_for_timeout(150)
        check("naar een moment met al een andere ronde: 'Dubbele datum & tijd', niets verhuisd", [await ev(pg, "() => document.getElementById('confirmModalTitle')?.textContent"), await ev(pg, "() => loadSavedRounds().find(r => r.id === 990501).time")], ['Dubbele datum & tijd', '09:12'])
        await ev(pg, "() => { document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden')); sluitRondesBewerken(); }")
        # de notitie groeit mee met de tekst (geen half afgesneden regel)
        await ev(pg, "() => { openRondesBewerken(['990501', '990502']); rbNotitie1.value = 'Clubcompetitie op de eerste zaterdag van de maand, met lunch en prijsuitreiking'; groeiMee(rbNotitie1); }")
        check("notitie groeit mee: de hele tekst zichtbaar", await ev(pg, "() => rbNotitie1.scrollHeight <= rbNotitie1.clientHeight + 1 && rbNotitie1.clientHeight > rbNotitie2.clientHeight"), True)
        await ev(pg, "() => sluitRondesBewerken()")
        # Q alleen met Handicap bijhouden
        await ev(pg, "() => { storage.setItem('golf_whs_volgen', 'off'); pasWhsWeergaveToe(); openRondesBewerken(['990501', '990502']); }")
        check("zonder Handicap bijhouden geen Q", await ev(pg, "() => getComputedStyle(rbQ1.closest('.whs-only')).display"), 'none')
        await ev(pg, "() => { storage.setItem('golf_whs_volgen', 'on'); pasWhsWeergaveToe(); sluitRondesBewerken(); }")
        print("\n=== 8. DE KNOPPEN PASSEN IN BEIDE BEWERKVENSTERS ===\n")
        # Op een smal scherm (320) de prullenbak erboven; op 360 krap naast elkaar, vanaf 390 gewoon naast elkaar
        MEET = """(id) => { const v = document.querySelector('#' + id + ' > div'); if (!v) return null; const box = v.getBoundingClientRect(), c = getComputedStyle(v);
            const l = box.left + parseFloat(c.borderLeftWidth) + parseFloat(c.paddingLeft), r = box.right - parseFloat(c.borderRightWidth) - parseFloat(c.paddingRight);
            return [...v.querySelectorAll('button')].filter(k => k.offsetParent).every(k => { const q = k.getBoundingClientRect(); return q.left >= l - 0.5 && q.right <= r + 0.5 && k.scrollWidth <= k.clientWidth; }); }"""
        for w in (300, 320, 360, 390):
            await pg.set_viewport_size({'width': w, 'height': 800})
            await ev(pg, "() => openRondesBewerken(['990501', '990502'])")
            a1 = await ev(pg, MEET, 'rondesBewerkenModal')
            await ev(pg, "() => { sluitRondesBewerken(); doOpenRoundInfoModal(0); }")
            a2 = await ev(pg, MEET, 'roundInfoModal')
            await ev(pg, "() => closeRoundInfoModal()")
            # sinds review 2 (13528FE-001): altijd alle drie op een regel; past Annuleren niet, dan als icoon
            rij = await ev(pg, "() => { openRondesBewerken(['990501', '990502']); const k = [...document.querySelectorAll('#rondesBewerkenModal .venster-knoppen > button')]; const t = k.map(x => Math.round(x.getBoundingClientRect().top)); const a = k[1]; const uit = [t, a.classList.contains('als-icoon'), a.getAttribute('aria-label') || a.textContent.trim()]; sluitRondesBewerken(); return uit; }")
            check(f"{w} px: alle drie op één regel" + (', Annuleren als icoon' if w < 390 else ''), isinstance(rij, list) and [len(set(rij[0])), rij[1], rij[2]], [1, w < 390, 'Annuleren'])
            for mid, open_js, dicht_js in (('rondesBewerkenModal', "openRondesBewerken(['990501', '990502'])", 'sluitRondesBewerken()'), ('roundInfoModal', 'doOpenRoundInfoModal(0)', 'closeRoundInfoModal()')):
                links = await ev(pg, "([id, o, d]) => { eval(o); const rij = document.querySelector('#' + id + ' .venster-knoppen'); const k = rij && rij.querySelector('button'); const r = k ? Math.round(k.getBoundingClientRect().left - rij.getBoundingClientRect().left) : null; eval(d); return r; }", [mid, open_js, dicht_js])
                check(f"{w} px: prullenbak links in {mid}", links, 0)
            check(f"{w} px: alle knoppen binnen beide vensters Ronde bewerken (twee spelers en één speler)", [a1, a2], [True, True])
        # Een breder lettertype (zoals op de telefoon): de prullenbak moet links onderaan blijven
        await pg.set_viewport_size({'width': 360, 'height': 800})
        breed = await ev(pg, """() => { const st = document.createElement('style'); st.id = 'breedFont'; st.textContent = '.venster-knoppen button { letter-spacing: 5px; }'; document.head.appendChild(st);
            openRondesBewerken(['990501', '990502']); const rij = document.querySelector('#rondesBewerkenModal .venster-knoppen'); const k = [...rij.querySelectorAll('button')].map(x => x.getBoundingClientRect()), r0 = rij.getBoundingClientRect();
            const uit = [Math.round(k[0].left - r0.left), k[0].top < k[1].top, Math.round(k[1].top) === Math.round(k[2].top)]; sluitRondesBewerken(); st.remove(); return uit; }""")
        check("breder lettertype op 360 px: met Annuleren als icoon nog alle drie op een regel", breed, [0, False, True])
        # Breed lettertype op een breed scherm: past het niet naast elkaar, dan ook gestapeld (gemeten, geen vaste breedte)
        await pg.set_viewport_size({'width': 430, 'height': 900})
        breed430 = await ev(pg, """() => { const st = document.createElement('style'); st.textContent = '.venster-knoppen button { letter-spacing: 40px; }'; document.head.appendChild(st);
            openRondesBewerken(['990501', '990502']); const rij = document.querySelector('#rondesBewerkenModal .venster-knoppen'); const k = [...rij.querySelectorAll('button')].map(x => x.getBoundingClientRect());
            const uit = [k[0].top < k[1].top, Math.round(k[1].top) === Math.round(k[2].top), [...rij.querySelectorAll('button')].every(x => x.getBoundingClientRect().right <= rij.getBoundingClientRect().right + 0.5)]; sluitRondesBewerken(); st.remove(); return uit; }""")
        check("heel breed lettertype op 430 px: past ook met het icoon niet, dan gestapeld en binnen het venster", breed430, [True, True, True])
        # Draaien of breder venster terwijl het open is: weer naast elkaar
        await pg.set_viewport_size({'width': 340, 'height': 800})
        await ev(pg, "() => openRondesBewerken(['990501', '990502'])")
        await pg.set_viewport_size({'width': 430, 'height': 800}); await pg.wait_for_timeout(150)
        naast = await ev(pg, "() => { const t = [...document.querySelectorAll('#rondesBewerkenModal .venster-knoppen > button')].map(k => Math.round(k.getBoundingClientRect().top)); sluitRondesBewerken(); return t; }")
        check("van smal naar breed terwijl het venster open is: weer alle drie naast elkaar", isinstance(naast, list) and len(set(naast)) == 1, True)
        check("geen paginafouten", pf, [])
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ', '.join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
