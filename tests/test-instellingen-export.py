"""Instellingen exporteren en inlezen (13528FA-003).

Instellingen > Gegevens: Exporteren > Instellingen maakt een JSON-bestand met de echte
instellingen en de twee standaardspelers; geen rondes, clubs, backupstand, open/dicht,
Start-toestand of de code van deze installatie. Importeren > Instellingen… keurt elke
waarde, toont wat er verandert en bewaart pas na Toepassen. Wat niet deugt wordt genoemd en
overgeslagen; een bestand dat niet deugt verandert niets. Rondes en clubs blijven gelijk.

Via de echte bediening: de knoppen, het bestandsvenster, Toepassen en Annuleren.
"""
import asyncio, os, sys, json, tempfile
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

TOEGESTAAN = {'golf_theme', 'golf_whs_volgen', 'golf_scorecard_symbols', 'golf_progress_indicator', 'golf_scherm_aan', 'golf_bad_weather',
              'golf_auto_next', 'golf_start_ppar', 'golf_qual_standaard', 'golf_track_putts', 'golf_putts_stats', 'golf_lowhi_graph',
              'golf_actions_always_visible', 'golf_min_rounds_stat', 'golf_low_hi', 'golf_agenda_link', 'golf_std_player1_name',
              'golf_std_player1_hcp', 'golf_default_player2_name', 'golf_default_player2_hcp', 'golf_home_club', 'golf_fav_clubs'}
MAP = tempfile.mkdtemp()

async def gegevens(pg):
    await ev(pg, "() => { nav('settings'); switchSettingsTab('data'); openSectie('settingsTabData|Exporteren'); openSectie('settingsTabData|Importeren'); }")
    await pg.wait_for_timeout(200)

async def lees_in(pg, inhoud, naam='instellingen-test.json'):
    """Kiest het bestand via de knop Instellingen…; geeft de tekst van het venster terug."""
    pad = os.path.join(MAP, naam)
    with open(pad, 'w', encoding='utf-8') as f:
        f.write(inhoud if isinstance(inhoud, str) else json.dumps(inhoud))
    await gegevens(pg)
    try:
        async with pg.expect_file_chooser(timeout=3000) as fc:
            await pg.get_by_role('button', name='Instellingen…').click(timeout=2000)
        await (await fc.value).set_files(pad)
    except Exception as e:
        return 'FOUT: ' + str(e)[:80]
    await pg.wait_for_timeout(400)
    return await ev(pg, "() => document.getElementById('keuzeModal').classList.contains('hidden') ? null : [keuzeModalTitel.textContent, keuzeModalTekst.textContent]")

async def knop(pg, naam):
    try: await pg.locator('#keuzeModal').get_by_role('button', name=naam).click(timeout=2000); await pg.wait_for_timeout(300); return True
    except Exception: return False

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': 800}, accept_downloads=True)
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES])
        await pg.evaluate("""() => { localStorage.setItem('golf_theme', 'light'); localStorage.setItem('golf_track_putts', 'on'); localStorage.setItem('golf_min_rounds_stat', '4');
            localStorage.setItem('golf_agenda_link', 'ms-outlook://events'); localStorage.setItem('golf_std_player1_name', 'Testspeler');
            localStorage.setItem('golf_default_player2_name', 'Medespeler'); localStorage.setItem('golf_default_player2_hcp', '24'); }""")
        await pg.reload(); await pg.wait_for_timeout(500)
        club = await ev(pg, "() => Object.keys(CLUBS)[0]")
        await ev(pg, "(c) => { localStorage.setItem('golf_home_club', c); localStorage.setItem('golf_fav_clubs', JSON.stringify([c])); }", club)

        print("\n=== 0. DE LIJST ===\n")
        # Een nieuwe instelling komt bewust in INSTELLINGEN_EXPORT én hier (CONTROLELIJST.md).
        check("de instellingen in het bestand zijn precies deze", await ev(pg, "() => INSTELLINGEN_EXPORT.map(d => d.k).sort()"), sorted(TOEGESTAAN))
        check("en elk staat in het register", await ev(pg, "() => INSTELLINGEN_EXPORT.filter(d => OPSLAGSLEUTELS[d.k] !== 'wissen').map(d => d.k)"), [])
        check("een plushandicap als '+5' wordt geweigerd (de app schrijft -5)", await ev(pg, "() => [normaliseerHcpTekst('+5'), normaliseerHcpTekst('-5'), normaliseerHcpTekst('5,25')]"), [None, '-5', '5.3'])

        print("\n=== 1. EXPORTEREN ===\n")
        await gegevens(pg)
        bestand = None
        try:
            async with pg.expect_download(timeout=5000) as dl:
                await pg.locator('#exportCard').get_by_role('button', name='Instellingen', exact=True).click(timeout=2000)
            d = await dl.value; naam = d.suggested_filename
            bestand = json.load(open(await d.path(), encoding='utf-8'))
        except Exception as e:
            naam = 'FOUT: ' + str(e)[:80]
        check("bestandsnaam instellingen_<datum>_…(<code>).json", isinstance(naam, str) and naam.startswith('instellingen_') and naam.endswith(').json'), True)
        check("een instellingenbestand van Golf Score", bestand and [bestand.get('app'), bestand.get('soort'), bool(bestand.get('versie')), bool(bestand.get('gemaakt'))], ['golf-score', 'instellingen', True, True])
        inst = (bestand or {}).get('instellingen', {})
        check("alleen instellingen en standaardspelers: geen rondes, clubs, Start of backupstand", sorted(set(inst) - TOEGESTAAN), [])
        nu = await ev(pg, "(ks) => Object.fromEntries(ks.map(k => [k, localStorage.getItem(k)]).filter(([, v]) => v != null))", sorted(TOEGESTAAN))
        check("precies wat er bewaard staat", inst, nu)
        check("melding in groen", await ev(pg, "() => document.querySelector('.export-settings-success')?.textContent"), f"{len(inst)} instellingen geëxporteerd")

        print("\n=== 2. TERUG INLEZEN NA WIJZIGEN ===\n")
        voor = await ev(pg, "() => [localStorage.getItem('golf_rounds'), localStorage.getItem('golf_clubs'), iName.value, localStorage.getItem('golf_profile_name')]")
        await ev(pg, "() => { localStorage.setItem('golf_theme', 'dark'); document.documentElement.classList.remove('light-mode'); localStorage.setItem('golf_track_putts', 'off'); localStorage.removeItem('golf_agenda_link'); localStorage.setItem('golf_default_player2_hcp', '30'); }")
        venster = await lees_in(pg, bestand or {})
        check("het venster Instellingen inlezen", venster and venster[0], 'Instellingen inlezen')
        tekst = venster[1] if isinstance(venster, list) else ''
        for regel in ('• Donkere modus: aan → uit', '• Putts bijhouden: uit → aan', '• Agenda openen: standaard → ms-outlook://events', '• Standaard speler 2 (hcp): 30 → 24', 'Rondes en clubs blijven zoals ze zijn.'):
            check(f"het venster noemt {regel!r}", regel in tekst, True)
        await knop(pg, 'Annuleren')
        check("Annuleren: niets veranderd", await ev(pg, "() => [localStorage.getItem('golf_theme'), localStorage.getItem('golf_track_putts'), localStorage.getItem('golf_agenda_link'), localStorage.getItem('golf_default_player2_hcp')]"), ['dark', 'off', None, '30'])
        await lees_in(pg, bestand or {})
        await knop(pg, 'Toepassen')
        na = await ev(pg, "(ks) => Object.fromEntries(ks.map(k => [k, localStorage.getItem(k)]).filter(([, v]) => v != null))", sorted(TOEGESTAAN))
        check("Toepassen: alles zoals in het bestand", na, inst)
        check("meteen zichtbaar: licht thema, schakelaars en het veld met de link", await ev(pg, "() => { nav('settings'); return [document.documentElement.classList.contains('light-mode'), themeToggle.checked, trackPuttsToggle.checked, agendaLinkInput.value, stdPlayer2Summary.textContent]; }"),
              [True, False, True, 'ms-outlook://events', 'Medespeler · hcp 24'])
        check("rondes, clubs en Start ongewijzigd", await ev(pg, "() => [localStorage.getItem('golf_rounds'), localStorage.getItem('golf_clubs'), iName.value, localStorage.getItem('golf_profile_name')]"), voor)

        print("\n=== 3. WAT NIET DEUGT ===\n")
        v = await lees_in(pg, '{ dit is geen json', 'kapot.json')
        check("onleesbaar bestand: melding, niets veranderd", isinstance(v, list) or v is None, True)
        check("  (melding)", await ev(pg, "() => [confirmModalTitle.textContent, !confirmModal.classList.contains('hidden')]"), ['Import mislukt', True])
        await ev(pg, "() => closeConfirmModal()")
        v = await lees_in(pg, json.dumps([{'date': '2026-01-01', 'holes': []}]), 'rondes.json')
        check("een rondebestand: geweigerd met uitleg", await ev(pg, "() => document.querySelector('#confirmModal').textContent.includes('geen instellingenbestand')"), True)
        await ev(pg, "() => closeConfirmModal()")
        stand0 = await ev(pg, "() => JSON.stringify(Object.keys(localStorage).sort().map(k => [k, localStorage.getItem(k)]))")
        slecht = {'app': 'golf-score', 'soort': 'instellingen', 'instellingen': {
            'golf_theme': 'paars', 'golf_min_rounds_stat': '-4', 'golf_agenda_link': 'javascript:alert(1)', 'golf_low_hi': 99,
            'golf_std_player1_name': '<img src=x onerror=window.__x=1>', 'golf_default_player2_hcp': 'veel', 'golf_home_club': 'Bestaat Niet',
            'golf_fav_clubs': 'geen lijst', 'golf_rounds': '[]', 'golf_storage_id': 'X'}}
        v = await lees_in(pg, slecht, '<b>slecht<b>.json')
        check("alles fout: 'Import mislukt' met de lijst", v and v[0], 'Import mislukt')
        tekst = v[1] if isinstance(v, list) else ''
        for regel in ('Donkere modus: “paars” is geen geldige waarde', 'Minimum aantal rondes: “-4” is geen geldige waarde', 'Agenda openen: een link die begint met javascript: mag niet',
                      'Low HI: “99” is geen geldige waarde', 'Thuisclub: die club staat niet in deze app'):
            check(f"genoemd: {regel!r}", regel in tekst, True)
        check("niets uitgevoerd, niets als HTML (ook de bestandsnaam)", await ev(pg, "() => [window.__x === undefined, document.querySelectorAll('#keuzeModal img, #keuzeModal b').length]"), [True, 0])
        await knop(pg, 'Sluiten')
        check("en niets veranderd in de opslag", await ev(pg, "() => JSON.stringify(Object.keys(localStorage).sort().map(k => [k, localStorage.getItem(k)]))") == stand0, True)

        gemengd = {'app': 'golf-score', 'soort': 'instellingen', 'instellingen': {
            'golf_min_rounds_stat': 6, 'golf_low_hi': '12.34', 'golf_default_player2_hcp': '18,5', 'golf_track_putts': 'aan',
            'golf_fav_clubs': json.dumps([club, 'Bestaat Niet', club]), 'golf_onbekend': 'x', 'golf_rounds': '[]'}}
        v = await lees_in(pg, gemengd)
        tekst = v[1] if isinstance(v, list) else ''
        check("gemengd: het goede gaat door, het foute wordt genoemd", ['Putts bijhouden: “aan” is geen geldige waarde' in tekst, '1 club niet in deze app' in tekst, '2 onbekende instellingen overgeslagen.' in tekst], [True, True, True])
        await knop(pg, 'Toepassen')
        check("bewaard: getal als tekst, Low HI op één decimaal, hcp met komma, dubbele en onbekende club eruit",
              await ev(pg, "() => [localStorage.getItem('golf_min_rounds_stat'), localStorage.getItem('golf_low_hi'), localStorage.getItem('golf_default_player2_hcp'), localStorage.getItem('golf_fav_clubs'), localStorage.getItem('golf_track_putts')]"),
              ['6', '12.3', '18.5', json.dumps([club], separators=(',', ':')), 'on'])
        check("golf_rounds uit een instellingenbestand komt nooit binnen", await ev(pg, "() => localStorage.getItem('golf_rounds') === '[]'"), False)
        check("geen paginafouten", pf, [])
        await b.close()
    print(f"\n{len(fouten)} FOUT(EN): {', '.join(fouten)}" if fouten else "\nGEEN FOUTEN")
    sys.exit(1 if fouten else 0)

asyncio.run(main())
