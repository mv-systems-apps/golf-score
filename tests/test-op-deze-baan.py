"""Op deze baan: onder de eerste geplande ronde op het lege scorescherm (13528F8-001).

Onderin de kaart van de geplande ronde een inklapbare kop "Op deze baan" met het aantal
rondes; standaard dicht, en Golf onthoudt open of dicht. Alleen je afgeronde qualifying
rondes op dezelfde club, baan en tee (met geslacht), en daarvan alleen die met elk hole van
de geplande ronde (score, par en phcp), al vanaf één ronde en los van het minimum aantal
rondes van de statistieken (13528F8-002). Beide rondekaarten (gepland en gepauzeerd) hebben
een regel 'H [BLAUW] 9h · Par 36' (13528F8-002). Open: "27.0 Gem. Stb" en "bereik 21–34" (laagste–hoogste Stb over de holes
van de geplande ronde), daaronder per hole de slagen t.o.v. je persoonlijke par, getekend
zoals de baananalyse (rood erboven, groen eronder). Een tik op een hole geeft de details.
Geen blok bij een wedstrijdlus of te weinig rondes.
"""
import asyncio, datetime, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

def dag(n):
    return (datetime.date.today() + datetime.timedelta(days=n)).isoformat()

# Een geplande ronde op een baan en tee van een bestaande afgeronde ronde, alle holes leeg.
PLAN = """([id, club, baan, tee, speler]) => {
  const s = loadSavedRounds().filter(r => r.id !== id);
  const b = s.find(r => isRondeAf(r) && r.club === club && r.track === baan && r.tee === tee);
  s.push({ ...b, id, date: '%s', time: '10:51', player: speler || b.player, tee, note: undefined, qualifying: true, lus: undefined,
           holes: b.holes.map(h => ({ ...h, score: null, putts: undefined })) });
  setRoundsAndMark(JSON.stringify(s)); nav('score'); verversLegeScoreKnoppen && verversLegeScoreKnoppen();
}""" % dag(2)

# Los nagerekend, buiten de app: dezelfde rondes, per hole score − (par + phcp) en de Stb.
NAGEREKEND = """(id) => {
  const s = loadSavedRounds(), p = s.find(r => r.id === id);
  const ids = p.holes.map(h => String(h.id)), open = openRondeIds();
  const vol = r => ids.every(i => r.holes.some(x => String(x.id) === i && x.score != null && x.par != null && x.phcp != null));
  const rs = s.filter(r => r.id !== id && r.player === p.player && r.qualifying && r.club === p.club && r.track === p.track && r.tee === p.tee
                      && (r.gender || 'Heren') === (p.gender || 'Heren') && r.holes.length && r.holes.every(h => h.score != null)
                      && !r._justImported && r.lus !== true && !open.has(String(r.id)) && vol(r));
  const per = p.holes.map(h => { let d = 0, n = 0, st = 0; rs.forEach(r => r.holes.forEach(x => { if (String(x.id) === String(h.id) && x.score != null) {
      d += x.score - (x.par + x.phcp); st += Math.max(0, x.par + x.phcp + 2 - x.score); n++; } })); return { id: h.id, diff: d / n, stb: st / n, n }; });
  const tot = rs.map(r => p.holes.reduce((t, h) => { const x = r.holes.find(y => String(y.id) === String(h.id)); return t + Math.max(0, x.par + x.phcp + 2 - x.score); }, 0));
  return { n: rs.length, stb: Math.round(tot.reduce((a, x) => a + x, 0) / tot.length * 10) / 10, per, bereik: [Math.min(...tot), Math.max(...tot)] };
}"""
BLOK = """() => { const kop = [...document.querySelectorAll('#scoreEmptyMsg .lege-kop')].map(e => e.textContent.trim());
  const k = document.querySelector('#scoreEmptyMsg .met-baan .odb-kop'), kaart = document.querySelector('#scoreEmptyMsg .met-baan');
  const b = document.querySelector('#scoreEmptyMsg .met-baan .odb-inhoud');
  const basis = { koppen: kop, blok: !!k, kop: k ? k.innerText.split(String.fromCharCode(10)).map(x => x.trim()).filter(Boolean).join(' ') : null, open: k ? k.getAttribute('aria-expanded') : null,
                  inKaart: !!kaart && !!kaart.querySelector('.lege-knop[data-soort="gepland"]') };
  if (!b) return basis;
  const rects = [...b.querySelectorAll('svg rect')].filter(r => r.getAttribute('fill') !== 'transparent');
  return { ...basis, tekst: b.textContent.replace(/\\s+/g, ' ').trim(),
           staafjes: rects.length, rood: rects.filter(r => /red/.test(r.getAttribute('fill') || '')).length,
           groen: rects.filter(r => /green/.test(r.getAttribute('fill') || '')).length,
           tikvlakken: b.querySelectorAll('svg rect[fill="transparent"]').length,
           detail: (document.getElementById('caDetail_opDezeBaan') || {}).textContent || '' }; }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': 800}, device_scale_factor=2)
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        speler = await pg.evaluate("() => startPlayerName()")
        # de baan met de meeste qualifying rondes van de speler, en een met te weinig
        banen = await pg.evaluate("""(sp) => { const t = {}; loadSavedRounds().filter(r => r.player === sp && r.qualifying && isRondeAf(r)).forEach(r => {
            const k = [r.club, r.track, r.tee].join('|'); t[k] = (t[k] || 0) + 1; }); return Object.entries(t).sort((a, b) => b[1] - a[1]); }""", speler)
        veel = banen[0][0].split('|')
        print('  (baan met de meeste rondes:', banen[0], ')')

        # De testdata heeft op elke hole dezelfde afwijking en nooit boven ppar. Op deze baan per
        # hole verschillende scores, op hole 4 en 7 boven ppar, zodat rood en groen voorkomen en
        # een verkeerde koppeling van holes opvalt.
        await pg.evaluate("""([club, baan, tee, sp]) => { const s = loadSavedRounds(); let i = 0;
            s.filter(r => r.player === sp && r.club === club && r.track === baan && r.tee === tee && isRondeAf(r)).forEach(r => { i++;
              r.holes.forEach((h, k) => { const ppar = h.par + h.phcp; h.score = ppar + ((k === 3 || k === 6) ? 1 + (i % 2) : (k % 3) - 1); if (h.putts != null) h.putts = Math.min(h.putts, h.score); }); });
            setRoundsAndMark(JSON.stringify(s)); }""", [*veel, speler])

        print("\n=== 1. HET BLOK ONDER DE GEPLANDE RONDE ===\n")
        await pg.evaluate(PLAN, [990101, *veel, None]); await pg.wait_for_timeout(300)
        k = await pg.evaluate(BLOK)
        v = await pg.evaluate(NAGEREKEND, 990101)
        check("onderin de kaart van de geplande ronde een kop 'Op deze baan' met het aantal rondes (13528F8-001)",
              (k['inKaart'], (k['kop'] or '').upper(), (k['koppen'] or [''])[0], 'Op deze baan' in k['koppen']), (True, f"OP DEZE BAAN {v['n']}×", 'Eerste geplande ronde', False))
        check("standaard dicht: geen grafiek", (k['open'], 'tekst' in k), ('false', False))
        await pg.evaluate("() => { const k = document.querySelector('#scoreEmptyMsg .odb-kop'); if (k) k.click(); }"); await pg.wait_for_timeout(150)
        k = await pg.evaluate(BLOK)
        check("een tik op de kop: open", k['open'], 'true')
        await pg.reload(); await pg.wait_for_timeout(500); await pg.evaluate("() => nav('score')"); await pg.wait_for_timeout(200)
        k = await pg.evaluate(BLOK)
        check("Golf onthoudt dat hij open staat", (k['open'], 'tekst' in k), ('true', True))
        fk = await pg.evaluate("""() => { const k = document.querySelector('#scoreEmptyMsg .odb-kop'); if (!k) return null; k.focus(); k.click(); const a = document.activeElement;
            const r = [a && a.classList.contains('odb-kop'), a && a.getAttribute('aria-expanded')]; a && a.click(); return r; }""")
        check("met het toetsenbord: na open of dicht blijft de focus op de kop", fk, [True, 'false'])
        await pg.evaluate("() => { const k = document.querySelector('#scoreEmptyMsg .odb-kop'); if (k && k.getAttribute('aria-expanded') === 'false') k.click(); }")
        kleur = await pg.evaluate("""() => { const k = document.querySelector('#scoreEmptyMsg .met-baan'); if (!k) return null;
            const c = e => getComputedStyle(e).backgroundColor; const knop = k.querySelector('.lege-knop'), odb = k.querySelector('.odb-inhoud');
            return [c(knop), odb ? c(odb) : null, getComputedStyle(k).borderTopColor === getComputedStyle(document.querySelector('#scoreEmptyMsg .lege-knop[data-soort="gepauzeerd"]') || k).borderTopColor]; }""")
        check("twee tinten: de knop in zijn eigen kleur, de inhoud zonder eigen achtergrond (in die van de kaart)", (kleur[0] != 'rgba(0, 0, 0, 0)', kleur[1]) if kleur else None, (True, 'rgba(0, 0, 0, 0)'))
        rand = await pg.evaluate("() => { const k = document.querySelector('#scoreEmptyMsg .odb-kop'); if (!k) return null; k.focus(); return getComputedStyle(k).outlineStyle; }")
        check("geen rand om de kop, ook niet met de focus erop", rand, 'none')
        if 'tekst' in k:
            check("gemiddelde ('27.0 Gem. Stb') en bereik, los nagerekend", (f"{v['stb']:.1f} Gem. Stb" in k['tekst'], f"bereik {v['bereik'][0]}–{v['bereik'][1]}" in k['tekst']), (True, True))
            check("per hole één staafje, met een tikvlak", (k['tikvlakken'], k['staafjes'] >= len(v['per'])), (len(v['per']), True))
            check("rood bij slagen boven ppar, groen eronder (aantallen los nagerekend)",
                  (k['rood'], k['groen']), (sum(1 for x in v['per'] if x['diff'] >= 0.05), sum(1 for x in v['per'] if x['diff'] <= -0.05)))
            check("er zijn rode en groene staafjes (anders test dit niets)", (k['rood'] >= 2, k['groen'] >= 1), (True, True))
            kl = await pg.evaluate("""() => [...document.querySelectorAll('#scoreEmptyMsg .odb-inhoud svg')].flatMap(svg => [...svg.querySelectorAll('rect')]
                .filter(r => r.getAttribute('fill') !== 'transparent').map(r => /red/.test(r.getAttribute('fill')) ? 'r' : /green/.test(r.getAttribute('fill')) ? 'g' : '0')).join('')""")
            verwacht = ''.join('r' if x['diff'] >= 0.05 else 'g' if x['diff'] <= -0.05 else '0' for x in v['per'])
            check("per hole de juiste kleur, in de volgorde van de holes", kl, verwacht)
            check("de regel eronder", k['detail'], 'Slagen t.o.v. ppar')
            await pg.evaluate("() => { const t = document.querySelectorAll('#scoreEmptyMsg .odb-inhoud svg rect[fill=\"transparent\"]')[0]; if (t) t.dispatchEvent(new MouseEvent('click', {bubbles: true})); }")
            d = (await pg.evaluate(BLOK)).get('detail') or ''
            h0 = v['per'][0]; t = round(h0['diff'], 1)
            teken = f"+{t:.1f}" if t > 0 else f"\u2212{abs(t):.1f}" if t < 0 else "0.0"
            check("een tik op hole 1: kort, met een echt plus- of minteken", (d.startswith(str(h0['id']) + ' (par'), d.endswith(' · ' + teken), 'gem.' in d, 'ppar' in d), (True, True, False, False))
            past = await pg.evaluate("() => { const e = document.getElementById('caDetail_opDezeBaan'); return e.getBoundingClientRect().height <= parseFloat(getComputedStyle(e).lineHeight || '20') * 1.5 || e.getBoundingClientRect().height <= 24; }")
            check("de regel past op 360 px op één regel", past, True)

        print("\n=== 2. ALLEEN QUALIFYING, ALLEEN DEZE TEE ===\n")
        await pg.evaluate("""(id) => { const s = loadSavedRounds(); const p = s.find(r => r.id === id);
            s.filter(r => r.id !== id && r.club === p.club && r.track === p.track && r.tee === p.tee && isRondeAf(r)).slice(0, 2).forEach(r => { r.qualifying = false; });
            setRoundsAndMark(JSON.stringify(s)); verversLegeScoreKnoppen(); }""", 990101)
        v2 = await pg.evaluate(NAGEREKEND, 990101); k2 = await pg.evaluate(BLOK)
        check("twee rondes niet meer qualifying: die tellen niet mee", (v2['n'], (k2['kop'] or '').upper()), (v['n'] - 2, f"OP DEZE BAAN {v2['n']}×"))
        await pg.evaluate("""(id) => { const s = loadSavedRounds(); s.find(r => r.id === id).tee = 'Bestaat niet'; setRoundsAndMark(JSON.stringify(s)); verversLegeScoreKnoppen(); }""", 990101)
        check("een tee zonder rondes: geen blok", (await pg.evaluate(BLOK))['blok'], False)

        print("\n=== 3. DREMPEL EN WEDSTRIJDLUS ===\n")
        # Eén qualifying ronde over op deze baan en tee: het blok staat er, ook met het hoogste
        # minimum van de statistieken; zonder qualifying ronde niet (13528F8-002)
        await pg.evaluate(PLAN, [990101, *veel, None]); await pg.wait_for_timeout(200)
        await pg.evaluate("""(id) => { const s = loadSavedRounds(); const p = s.find(r => r.id === id);
            s.filter(r => r.id !== id && r.club === p.club && r.track === p.track && r.tee === p.tee && isRondeAf(r) && r.qualifying).slice(1).forEach(r => { r.qualifying = false; });
            setRoundsAndMark(JSON.stringify(s)); storage.setItem('golf_min_rounds_stat', '10'); verversLegeScoreKnoppen(); }""", 990101)
        n = (await pg.evaluate(NAGEREKEND, 990101))['n']
        k1 = await pg.evaluate(BLOK)
        check("één qualifying ronde, minimum van de statistieken op 10: het blok staat er, met 1× (13528F8-002)", (n, k1['blok'], (k1.get('kop') or '').upper()), (1, True, 'OP DEZE BAAN 1×'))
        await pg.evaluate("""(id) => { const s = loadSavedRounds(); const p = s.find(r => r.id === id);
            s.filter(r => r.id !== id && r.club === p.club && r.track === p.track && r.tee === p.tee).forEach(r => { r.qualifying = false; });
            setRoundsAndMark(JSON.stringify(s)); verversLegeScoreKnoppen(); }""", 990101)
        check("geen qualifying ronde op deze baan en tee: geen blok", (await pg.evaluate(BLOK))['blok'], False)
        await pg.evaluate("() => { storage.removeItem('golf_min_rounds_stat'); }")
        # de testdata weer zoals hij was
        await pg.evaluate(SEED, [CLUBS, RONDES])
        await pg.evaluate(PLAN, [990101, *veel, None]); await pg.wait_for_timeout(200)
        await pg.evaluate("""(id) => { const s = loadSavedRounds(); s.find(r => r.id === id).lus = true; setRoundsAndMark(JSON.stringify(s)); verversLegeScoreKnoppen(); }""", 990101)
        check("een geplande ronde op een wedstrijdlus: geen blok", (await pg.evaluate(BLOK))['blok'], False)

        print("\n=== 4. RANDGEVALLEN ===\n")
        await pg.evaluate(PLAN, [990101, *veel, None]); await pg.wait_for_timeout(200)
        basis = (await pg.evaluate(NAGEREKEND, 990101))['n']
        async def aantal_na(js):
            await pg.evaluate(js); await pg.evaluate("() => verversLegeScoreKnoppen()")
            k = await pg.evaluate(BLOK); return int(k['kop'].split()[-1].rstrip('×')) if k.get('kop') else None
        # één ronde zonder phcp op een hole: die ronde telt niet mee, geen NaN
        n1 = await aantal_na("""(() => { const s = loadSavedRounds(); const p = s.find(r => r.id === 990101);
            const r = s.find(r => r.id !== 990101 && r.qualifying && r.club === p.club && r.track === p.track && r.tee === p.tee && isRondeAf(r)); delete r.holes[2].phcp;
            setRoundsAndMark(JSON.stringify(s)); })()""")
        txt = (await pg.evaluate(BLOK)).get('tekst', '')
        check("een ronde zonder phcp op een hole telt niet mee, en nergens NaN", (n1, 'NaN' in txt), (basis - 1, False))
        n2 = await aantal_na("""(() => { const s = loadSavedRounds(); const p = s.find(r => r.id === 990101);
            const r = s.find(r => r.id !== 990101 && r.qualifying && r.club === p.club && r.track === p.track && r.tee === p.tee && isRondeAf(r) && r.holes.every(h => h.phcp != null)); r._justImported = true;
            setRoundsAndMark(JSON.stringify(s)); })()""")
        check("een net geïmporteerde ronde telt niet mee", n2, basis - 2)
        n3 = await aantal_na("""(() => { const s = loadSavedRounds(); const p = s.find(r => r.id === 990101);
            const r = s.find(r => r.id !== 990101 && r.qualifying && !r._justImported && r.club === p.club && r.track === p.track && r.tee === p.tee && isRondeAf(r) && r.holes.every(h => h.phcp != null)); r.lus = true;
            setRoundsAndMark(JSON.stringify(s)); })()""")
        check("een ronde op een wedstrijdlus in de historie telt niet mee", n3, basis - 3)
        n4 = await aantal_na("""(() => { const s = loadSavedRounds(); const p = s.find(r => r.id === 990101);
            const r = s.find(r => r.id !== 990101 && r.qualifying && !r._justImported && !r.lus && r.club === p.club && r.track === p.track && r.tee === p.tee && isRondeAf(r) && r.holes.every(h => h.phcp != null)); r.gender = (p.gender || 'Heren') === 'Heren' ? 'Dames' : 'Heren';
            setRoundsAndMark(JSON.stringify(s)); })()""")
        check("dezelfde tee met een ander geslacht telt niet mee", n4, basis - 4)
        n5 = await aantal_na("""(() => { const s = loadSavedRounds(); const p = s.find(r => r.id === 990101);
            const r = s.find(r => r.id !== 990101 && r.qualifying && !r._justImported && !r.lus && (r.gender || 'Heren') === (p.gender || 'Heren') && r.club === p.club && r.track === p.track && r.tee === p.tee && isRondeAf(r) && r.holes.every(h => h.phcp != null)); r.player = 'Iemand anders';
            setRoundsAndMark(JSON.stringify(s)); })()""")
        check("een ronde van een andere speler telt niet mee", n5, basis - 5)
        # een geplande ronde van 18 holes op een baan waar alleen 9 holes gespeeld zijn: geen blok
        await pg.evaluate("""() => { const s = loadSavedRounds(); const p = s.find(r => r.id === 990101);
            p.holes = p.holes.concat(p.holes.map(h => ({ ...h, id: String(h.id) + 'b' }))); setRoundsAndMark(JSON.stringify(s)); verversLegeScoreKnoppen(); }""")
        check("18 holes gepland, maar geen ronde met al die holes: geen blok", (await pg.evaluate(BLOK))['blok'], False)
        # twee spelers op hetzelfde moment: het blok van de speler van Start
        await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.evaluate(PLAN, [990101, *veel, None])
        await pg.evaluate("""() => { const s = loadSavedRounds(); const p = s.find(r => r.id === 990101);
            s.push({ ...p, id: 990103, player: 'Medespeler' }); setRoundsAndMark(JSON.stringify(s)); verversLegeScoreKnoppen(); }""")
        tw = await pg.evaluate(BLOK)
        check("twee spelers op één moment: het blok van de speler van Start", (tw['blok'], (tw.get('kop') or '').endswith(f"{(await pg.evaluate(NAGEREKEND, 990101))['n']}×")), (True, True))

        print("\n=== 5. DE TEEREGEL IN BEIDE KAARTEN ===\n")
        await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.evaluate(PLAN, [990101, *veel, None]); await pg.wait_for_timeout(200)
        tr = await pg.evaluate("""() => [...document.querySelectorAll('#scoreEmptyMsg .lege-knop')].map(k => { const t = k.querySelector('.lege-knop-tee');
            const id = k.dataset.ids.split(',')[0], r = loadSavedRounds().find(x => String(x.id) === id);
            const verwacht = (r.gender || 'Heren').charAt(0) + ' ' + r.tee + ' ' + r.holes.length + 'h · Par ' + r.holes.reduce((a, h) => a + h.par, 0);
            return [k.dataset.soort, t ? t.textContent.replace(/[ ]+/g, ' ').trim() === verwacht.replace(' ' + r.tee + ' ', r.tee) || [...t.children].map(c => c.textContent).join(' ') === verwacht : false,
                    !!(t && t.querySelector('.tee-badge.tee-' + r.tee)), t ? t.getBoundingClientRect().height < 34 : false]; })""")
        check("geplande en gepauzeerde kaart: 'H [BLAUW] 9h · Par 36', met de gekleurde badge, op één regel (13528F8-002)",
              tr, [['gepland', True, True, True], ['gepauzeerd', True, True, True]])

        print("\n=== 6. EEN KEER REKENEN ===\n")
        await pg.evaluate(PLAN, [990101, *veel, None]); await pg.wait_for_timeout(200)
        tel = await pg.evaluate("""() => { const echt = pparVan; let n = 0; window.pparVan = h => { n++; return echt(h); };
            try { verversLegeScoreKnoppen(); verversLegeScoreKnoppen(); } finally { window.pparVan = echt; } return n; }""")
        check("het blok staat er (anders test dit niets)", (await pg.evaluate(BLOK))['blok'], True)
        check("opnieuw tekenen zonder nieuwe rondes rekent niet opnieuw", tel, 0)
        tel2 = await pg.evaluate("""() => { const echt = pparVan; let n = 0; window.pparVan = h => { n++; return echt(h); };
            try { const s = loadSavedRounds(); s[0].note = 'gewijzigd'; setRoundsAndMark(JSON.stringify(s)); verversLegeScoreKnoppen(); } finally { window.pparVan = echt; } return n > 0; }""")
        check("een gewijzigde rondelijst rekent wel opnieuw", tel2, True)
        check("geen paginafouten", pf, [])
        await b.close()
    print(f"\n{len(fouten)} FOUT(EN): {', '.join(fouten)}" if fouten else "\nGEEN FOUTEN")
    sys.exit(1 if fouten else 0)

asyncio.run(main())
