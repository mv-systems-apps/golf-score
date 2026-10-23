"""Eén rekenroute voor de handicap (1352898-012).

'Handicap nu', de kaarten op Rondes (handicapTabellen), de grafiek op Statistiek en
wat-als rekenen allemaal via whsStand: één keer de reeks maken, één keer het verloop
doorrekenen. 'Handicap nu' is de laatste stap van dat verloop.

  1. Twee rondes op hetzelfde tijdstip op de grens van de laatste 20: de kaart op Rondes
     toonde een andere handicap dan 'handicap nu' (handicapTabellen sorteerde zonder vaste
     volgorde bij een gelijk tijdstip).
  2. Honderden willekeurige reeksen (gelijke tijdstippen, uitschieters voor ESR, caps,
     handmatige Low HI, niet-qualifying rondes, een andere speler): 'handicap nu', de
     kaart van de nieuwste ronde en de losse formule (whsHandicap over de laatste 20)
     geven overal hetzelfde.
  3. Wat-als verandert de bewaarde stand niet; een gewijzigde ronde of Low HI telt meteen.
  4. Statistiek openen rekent het verloop één keer door, en nog een keer openen niet
     opnieuw.
"""
import asyncio, os, sys
from playwright.async_api import async_playwright
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import CLUBS, SEED, app_url, ronde

fouten = []
def check(naam, gekregen, verwacht):
    ok = gekregen == verwacht
    print(f" {' ok ' if ok else 'FOUT'}  {naam}: {gekregen!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

DICHT = "() => document.querySelectorAll('[id$=Modal]').forEach(m => m.classList.add('hidden'))"

async def nieuw(ctx, rondes, extra=None):
    pg = await ctx.new_page()
    pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:160]))
    pg._pf = pf
    await pg.goto(app_url())
    await pg.evaluate(SEED, [CLUBS, rondes])
    await pg.evaluate("() => localStorage.setItem('golf_kenmerk_gevraagd', '1')")
    if extra: await pg.evaluate(extra)
    await pg.reload(); await pg.wait_for_timeout(600)
    await pg.evaluate(DICHT)
    return pg

# De drie routes naast elkaar voor de rondes die nu bewaard zijn.
DRIE = """() => {
  const R = leesRondes();
  const nu = currentOfficialHcp('Testspeler', R);
  const f = whsHandicap(last20Qualifying('Testspeler', R), effectiveLowHi('Testspeler', R), esrMapFor('Testspeler', R));
  const qual = R.filter(meetelVoorHandicap('Testspeler'));
  let nieuwste = null;
  qual.forEach(r => { const t = new Date(`${r.date}T${r.time || '00:00'}`).getTime();
    if (!nieuwste || t > nieuwste.t || (t === nieuwste.t && String(r.id) > String(nieuwste.id))) nieuwste = { t, id: r.id }; });
  const kaart = nieuwste ? handicapTabellen().hcpTrendMap[nieuwste.id].newHcp : null;
  return [nu, f ? f.value : null, kaart];
}"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()

        print("\n=== 1. TWEE RONDES OP HETZELFDE TIJDSTIP: DE KAART OP RONDES ===\n")
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        rs = []
        for i in range(21):
            r = ronde(500 + i, f'2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}')
            r['sdFinal'] = 20.0
            rs.append(r)
        rs[1]['date'] = rs[0]['date']; rs[0]['time'] = ''; rs[1]['time'] = ''
        rs[0]['sdFinal'] = 14.0; rs[1]['sdFinal'] = 26.0
        rs.reverse()
        pg = await nieuw(ctx, rs, "() => localStorage.setItem('golf_low_hi', '40')")
        nu, formule, kaart = await pg.evaluate(DRIE)
        check("'handicap nu' en de formule over de laatste 20", formule, nu)
        check("de kaart van de nieuwste ronde op Rondes toont 'handicap nu'", kaart, nu)
        await ctx.close()

        print("\n=== 2. WILLEKEURIGE REEKSEN: OVERAL DEZELFDE HANDICAP ===\n")
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await nieuw(ctx, [ronde(1, '2026-01-01')])
        uit = await pg.evaluate("""([basis, DRIE]) => {
          const drie = eval(DRIE);
          let s = 12345;
          const rnd = () => { s = (s * 1103515245 + 12345) % 2147483648; return s / 2147483648; };
          const verschil = []; let metGelijk = 0, metCap = 0, metEsr = 0;
          for (let h = 0; h < 300; h++) {
            const n = 1 + Math.floor(rnd() * 45);
            const rondes = [];
            let dag = Date.UTC(2024, 0, 1);
            for (let i = 0; i < n; i++) {
              if (rnd() > 0.15) dag += Math.floor(rnd() * 40) * 86400000;     // soms dezelfde dag
              const d = new Date(dag).toISOString().slice(0, 10);
              const r = JSON.parse(JSON.stringify(basis));
              r.id = 1000 + Math.floor(rnd() * 9000) * 10 + i;   // ids niet op volgorde
              r.date = d;
              r.time = rnd() < 0.3 ? '' : (rnd() < 0.5 ? '09:30' : '14:00');
              r.sdFinal = Math.round((rnd() < 0.1 ? rnd() * 8 : 12 + rnd() * 25) * 10) / 10;
              r.qualifying = rnd() > 0.1;
              if (rnd() < 0.05) r.player = 'Ander';
              rondes.push(r);
            }
            rondes.reverse();
            storage.setItem('golf_rounds', JSON.stringify(rondes));
            if (rnd() < 0.3) storage.setItem('golf_low_hi', String(Math.round(rnd() * 300) / 10));
            else storage.removeItem('golf_low_hi');
            const [nu, f, kaart] = drie();
            const tijden = rondes.map(r => r.date + r.time);
            if (new Set(tijden).size < tijden.length) metGelijk++;
            const st = typeof whsStand === 'function' ? whsStand('Testspeler', leesRondes()) : {};
            if (st.nu && st.nu.capType) metCap++;
            if (st.nu && st.nu.esrApplied) metEsr++;
            if (!(nu === f && nu === kaart)) verschil.push([h, nu, f, kaart]);
          }
          return { verschil: verschil.slice(0, 5), aantal: verschil.length, metGelijk, metCap, metEsr };
        }""", [ronde(1, '2026-01-01'), DRIE])
        print(f"        (reeksen met gelijke tijdstippen: {uit['metGelijk']}, met een cap: {uit['metCap']}, met ESR: {uit['metEsr']})")
        check("reeksen waarin 'handicap nu', de formule en de kaart verschillen", uit['aantal'], 0)
        check("de reeksen raken ook gelijke tijdstippen, caps en ESR",
              uit['metGelijk'] > 20 and uit['metCap'] > 5 and uit['metEsr'] > 5, True)
        if uit['verschil']: print('        eerste verschillen:', uit['verschil'])
        await ctx.close()

        print("\n=== 3. WAT-ALS EN WIJZIGINGEN ===\n")
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        rs = []
        for i in range(25):
            r = ronde(700 + i, f'2026-02-{i + 1:02d}'); r['sdFinal'] = 18.0 + (i % 7); rs.append(r)
        rs.reverse()
        pg = await nieuw(ctx, rs)
        uit = await pg.evaluate("""() => {
          const voor = currentOfficialHcp('Testspeler', leesRondes());
          const w = computeWhatIf('Testspeler', 2.0);
          const na = currentOfficialHcp('Testspeler', leesRondes());
          const R = loadSavedRounds();
          R[0].sdFinal = 1.0;
          storage.setItem('golf_rounds', JSON.stringify(R));
          const gewijzigd = currentOfficialHcp('Testspeler', leesRondes());
          const formule = whsHandicap(last20Qualifying('Testspeler', leesRondes()), effectiveLowHi('Testspeler', leesRondes()), esrMapFor('Testspeler', leesRondes())).value;
          storage.setItem('golf_low_hi', '5');
          const metLowHi = currentOfficialHcp('Testspeler', leesRondes());
          return { voor, na, wNu: w.current.value, hypoLager: w.hypo.value < w.current.value, gewijzigd, formule, metLowHi };
        }""")
        check("wat-als laat 'handicap nu' staan", uit['na'], uit['voor'])
        check("wat-als rekent met dezelfde 'handicap nu'", uit['wNu'], uit['voor'])
        check("wat-als met een heel goede ronde geeft een lagere handicap", uit['hypoLager'], True)
        check("een gewijzigde ronde telt meteen", uit['gewijzigd'] != uit['voor'] and uit['gewijzigd'] == uit['formule'], True)
        check("een gewijzigde Low HI telt meteen (hard cap op 10,0)", uit['metLowHi'], 10.0)
        await ctx.close()

        print("\n=== 4. STATISTIEK REKENT HET VERLOOP ÉÉN KEER DOOR ===\n")
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await nieuw(ctx, rs)
        uit = await pg.evaluate("""() => {
          let n = 0; const echt = whsVerloop;
          window.whsVerloop = (...a) => { n++; return echt(...a); };
          leesRondes(); storage.setItem('golf_rounds', storage.getItem('golf_rounds') + ' ');   // nieuwe tekst: niets bewaard
          renderPlayerStats(); const eerste = n;
          renderPlayerStats(); const tweede = n - eerste;
          window.whsVerloop = echt;
          return [eerste, tweede];
        }""")
        check("Statistiek openen: het verloop één keer doorgerekend", uit[0], 1)
        check("nog een keer openen: niet opnieuw", uit[1], 0)
        await ctx.close()

        pf = []
        await b.close()
    print('\n' + (f'{len(fouten)} FOUT(EN)' if fouten else 'GEEN FOUTEN'))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
