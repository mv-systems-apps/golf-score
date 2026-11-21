"""Lichte modus: oranje tekst is goed leesbaar op het kaartvlak (poetsronde 13528FF-001). De
backupregel 'Backup rondes: nog nooit' haalde met #c86a00 maar 3.0:1; nu minstens 4.5:1. De
donkere modus houdt zijn oranje.
"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testdata import CLUBS, RONDES, app_url, SEED
from playwright.async_api import async_playwright

fouten = []
def check(naam, echt, verwacht):
    ok = echt == verwacht
    print(f"  {'ok  ' if ok else 'FOUT'} {naam}: {echt!r}" + ('' if ok else f" — verwacht {verwacht!r}"))
    if not ok: fouten.append(naam)

CONTRAST = """() => {
  const rgb = s => s.match(/[\\d.]+/g).slice(0, 4).map(Number);
  const L = ([r, g, b]) => { const f = x => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  /* achtergrond: de eerste niet-doorzichtige laag, met halfdoorzichtige lagen erop gemengd */
  const span = document.querySelector('#lastBackupInfoTop span'); if (!span) return null;
  const lagen = []; for (let e = span; e; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor); if (c.length === 4 ? c[3] > 0 : true) lagen.push(c); if (c.length === 3 || c[3] === 1) break; }
  let bg = [255, 255, 255]; for (const c of lagen.reverse()) { const a = c.length === 4 ? c[3] : 1; bg = bg.map((v, i) => v * (1 - a) + c[i] * a); }
  const fg = rgb(getComputedStyle(span).color), a = L(fg), b = L(bg);
  return Math.round((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05) * 100) / 100; }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': 740})
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        await pg.evaluate("() => { document.documentElement.classList.add('light-mode'); localStorage.removeItem('golf_last_backup_date'); nav('settings'); switchSettingsTab('main'); updateLastBackupDisplay(); }")
        await pg.wait_for_timeout(200)
        c = await pg.evaluate(CONTRAST)
        print('    contrast lichte modus:', c)
        check("lichte modus: oranje backupregel minstens 4.5:1", c is not None and c >= 4.5, True)
        donker = await pg.evaluate("() => { document.documentElement.classList.remove('light-mode'); return getComputedStyle(document.documentElement).getPropertyValue('--orange').trim(); }")
        check("donkere modus: het oranje zoals het was", donker.lower(), '#c86a00')
        await b.close()
    print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN): " + ', '.join(fouten)))
    sys.exit(1 if fouten else 0)

asyncio.run(main())
