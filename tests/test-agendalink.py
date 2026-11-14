"""De agenda-link in Instellingen (13528FA-003).

Instellingen > Algemeen > Agenda: de link achter het icoon rechts in de lege kop. Standaard
ms-outlook://calendar; leeg: geen icoon. Probeer opent de link, Standaard zet hem terug.

Veilig: een link kan code uitvoeren of een bestand openen. Bewaard wordt alleen een link
met een schema vooraan, zonder witruimte of onzichtbare tekens, hooguit 500 tekens, niet
javascript:, data:, vbscript:, file:, blob:, about: en dergelijke, en http alleen als https.
Een geweigerde link wordt gemeld, niet bewaard, en de vorige blijft gelden. Ook wat al in de
opslag staat wordt bij elk gebruik opnieuw gekeurd. De link komt nooit als HTML in de pagina:
tekens als " < > & # ; blijven gewoon tekens.

Via de echte bediening: typen in het veld, het veld verlaten (Tab en Enter), en de knoppen.
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

async def ev(pg, js, arg=None):
    try:
        return await pg.evaluate(js, arg)
    except Exception as e:
        return 'FOUT: ' + str(e).split('\n')[0][:120]

GOED = [
    ('ms-outlook://calendar', 'ms-outlook://calendar'),
    ('  ms-outlook://events  ', 'ms-outlook://events'),                       # plakken met spaties eromheen
    ('intent:#Intent;package=com.microsoft.office.outlook;action=android.intent.action.MAIN;category=android.intent.category.LAUNCHER;end',
     'intent:#Intent;package=com.microsoft.office.outlook;action=android.intent.action.MAIN;category=android.intent.category.LAUNCHER;end'),
    ('https://outlook.live.com/calendar/0/view/day', 'https://outlook.live.com/calendar/0/view/day'),
    ('MS-Outlook://calendar', 'MS-Outlook://calendar'),
    ('ms-outlook://x?a=1&b=<b>"q"#f;g', 'ms-outlook://x?a=1&b=<b>"q"#f;g'),     # speciale tekens blijven tekens
    ('', ''),                                                                  # leeg: geen icoon
    ('\ufeffms-outlook://calendar', 'ms-outlook://calendar'),                 # een onzichtbaar teken vooraan valt met de spaties weg
]
FOUT = [
    'javascript:alert(1)', 'JavaScript:alert(1)', '  javascript:alert(1)', 'JAVASCRIPT:void(0)',
    'java\tscript:alert(1)', 'java\nscript:alert(1)', 'data:text/html,<script>alert(1)</script>',
    'vbscript:msgbox(1)', 'file:///etc/passwd', 'blob:https://x/1', 'about:blank', 'view-source:https://x',
    'filesystem:https://x/y', 'http://outlook.live.com', 'ms outlook://calendar', 'ms-outlook://cal endar',
    'ms-outlook://\u200bcalendar', '\u202ejavascript:alert(1)', 'ms-outlook://cal\u00adendar', 'ms-outlook://cal\u2060endar',
    '//calendar', 'calendar', '1abc:x', ':x', 'ms-outlook://' + 'a' * 500,
]

SECTIE = "() => { switchSettingsTab('main'); openSectie('settingsTabMain|Agenda'); }"

async def verlaat(pg, toets='Tab'):
    try: await pg.locator('#agendaLinkInput').press(toets, timeout=2000)
    except Exception: pass
    await pg.wait_for_timeout(100)

async def klik(pg, naam):
    try: await pg.get_by_role('button', name=naam).click(timeout=2000)
    except Exception: pass
    await pg.wait_for_timeout(100)

async def vul(pg, tekst):
    try: await pg.locator('#agendaLinkInput').fill(tekst, timeout=2000)
    except Exception: pass

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 360, 'height': 800})
        pf = []; pg.on('pageerror', lambda e: pf.append(str(e)[:150]))
        dialogen = []; pg.on('dialog', lambda d: (dialogen.append(d.message), asyncio.ensure_future(d.dismiss())))
        await pg.goto(app_url()); await pg.evaluate(SEED, [CLUBS, RONDES]); await pg.reload(); await pg.wait_for_timeout(500)
        # openAgendaLink vangen: geen echte navigatie in de test
        VANG = "() => { window.__geopend = []; window.openAgendaLink = (l = agendaLink()) => { window.__geopend.push(l); }; }"

        print("\n=== 1. DE KEURING ===\n")
        for invoer, verwacht in GOED:
            check(f"goed: {invoer[:50]!r}", await ev(pg, "(t) => { const k = keurAgendaLink(t); return k.ok ? k.link : 'geweigerd: ' + k.reden; }", invoer), verwacht)
        for invoer in FOUT:
            r = await ev(pg, "(t) => { const k = keurAgendaLink(t); return k.ok ? 'GOEDGEKEURD' : (typeof k.reden === 'string' && k.reden.length > 5); }", invoer)
            check(f"geweigerd, met reden: {invoer[:40]!r}", r, True)

        print("\n=== 2. STANDAARD ===\n")
        await ev(pg, "() => nav('settings')"); await ev(pg, SECTIE); await pg.wait_for_timeout(200)
        check("zonder instelling: het veld toont ms-outlook://calendar", await ev(pg, "() => document.getElementById('agendaLinkInput')?.value"), 'ms-outlook://calendar')
        check("en het icoon staat in de kop", await ev(pg, "() => { nav('score'); return !!document.querySelector('#hdrHoleCount .kop-agenda'); }"), True)
        await ev(pg, VANG)
        await ev(pg, "() => document.querySelector('#hdrHoleCount .kop-agenda')?.click()")
        check("een tik opent de standaardlink", await ev(pg, "() => window.__geopend"), ['ms-outlook://calendar'])

        print("\n=== 3. TYPEN EN BEWAREN ===\n")
        await ev(pg, "() => nav('settings')"); await ev(pg, SECTIE); await pg.wait_for_timeout(200)
        veld = pg.locator('#agendaLinkInput')
        nieuw = 'intent:#Intent;package=com.microsoft.office.outlook;action=android.intent.action.MAIN;category=android.intent.category.LAUNCHER;end'
        try:
            await vul(pg, nieuw); await verlaat(pg)
        except Exception as e:
            check("typen in het veld", str(e)[:80], 'gelukt')
        check("goede link: bewaard", await ev(pg, "() => localStorage.getItem('golf_agenda_link')"), nieuw)
        check("geen melding", await ev(pg, "() => document.getElementById('agendaLinkFout')?.classList.contains('hidden')"), True)
        await ev(pg, VANG)
        await ev(pg, "() => { nav('score'); document.querySelector('#hdrHoleCount .kop-agenda')?.click(); }")
        check("het icoon in de kop opent de nieuwe link", await ev(pg, "() => window.__geopend"), [nieuw])

        await ev(pg, "() => nav('settings')"); await ev(pg, SECTIE); await pg.wait_for_timeout(200)
        await vul(pg, 'javascript:alert(document.cookie)'); await verlaat(pg)
        m = await ev(pg, "() => { const f = document.getElementById('agendaLinkFout'); return [!f.classList.contains('hidden'), f.textContent, document.getElementById('agendaLinkInput').classList.contains('veld-fout')]; }")
        check("javascript: geweigerd, in oranje met de reden", m, [True, 'Niet bewaard: een link die begint met javascript: mag niet', True])
        check("niet bewaard: de vorige link blijft", await ev(pg, "() => localStorage.getItem('golf_agenda_link')"), nieuw)
        check("wat je typte blijft staan, zodat je het kunt verbeteren", await ev(pg, "() => document.getElementById('agendaLinkInput').value"), 'javascript:alert(document.cookie)')
        await ev(pg, VANG)
        await klik(pg, 'Probeer')
        check("Probeer met een geweigerde link opent niets", await ev(pg, "() => window.__geopend"), [])
        await vul(pg, 'ms-outlook://ev'); await pg.wait_for_timeout(50)
        check("verder typen haalt de melding weg", await ev(pg, "() => document.getElementById('agendaLinkFout').classList.contains('hidden')"), True)
        await vul(pg, 'ms-outlook://events'); await verlaat(pg, 'Enter')
        check("Enter bewaart ook", await ev(pg, "() => localStorage.getItem('golf_agenda_link')"), 'ms-outlook://events')
        await vul(pg, 'ms-outlook://calendar/'); await klik(pg, 'Probeer')
        check("Probeer: bewaart en opent wat er staat", [await ev(pg, "() => window.__geopend"), await ev(pg, "() => localStorage.getItem('golf_agenda_link')")], [['ms-outlook://calendar/'], 'ms-outlook://calendar/'])

        print("\n=== 4. LEEG EN STANDAARD ===\n")
        await vul(pg, ''); await verlaat(pg)
        check("leeg: bewaard als leeg", await ev(pg, "() => localStorage.getItem('golf_agenda_link')"), '')
        check("leeg: geen icoon in de kop", await ev(pg, "() => { nav('score'); return document.querySelector('#hdrHoleCount')?.innerHTML; }"), '')
        await ev(pg, "() => nav('settings')"); await ev(pg, SECTIE); await pg.wait_for_timeout(200)
        await klik(pg, 'Standaard')
        check("Standaard: terug naar ms-outlook://calendar", [await ev(pg, "() => document.getElementById('agendaLinkInput').value"), await ev(pg, "() => localStorage.getItem('golf_agenda_link')")], ['ms-outlook://calendar', 'ms-outlook://calendar'])
        check("en het icoon is terug", await ev(pg, "() => { nav('score'); return !!document.querySelector('#hdrHoleCount .kop-agenda'); }"), True)

        print("\n=== 5. TEKENS BLIJVEN TEKENS ===\n")
        # Geen witruimte, dus de keuring laat hem door: hij mag dan nergens als HTML gelden.
        streek = 'ms-outlook:"><svg/onload=window.__x=1><img/src=x/onerror=window.__x=2>&amp;#;'
        await ev(pg, "() => nav('settings')"); await ev(pg, SECTIE); await pg.wait_for_timeout(200)
        await vul(pg, streek); await verlaat(pg)
        await ev(pg, "() => { nav('score'); }"); await pg.reload(); await pg.wait_for_timeout(500)
        await ev(pg, "() => nav('settings')"); await ev(pg, SECTIE); await pg.wait_for_timeout(200)
        check("letterlijk bewaard en letterlijk terug in het veld", [await ev(pg, "() => localStorage.getItem('golf_agenda_link')"), await ev(pg, "() => document.getElementById('agendaLinkInput').value")], [streek, streek])
        check("niets uitgevoerd, geen extra elementen", await ev(pg, "() => [window.__x === undefined, document.querySelectorAll('#hdrHoleCount svg[onload], #hdrHoleCount img, #screen-settings img[onerror]').length]"), [True, 0])
        await ev(pg, VANG)
        await ev(pg, "() => { nav('score'); document.querySelector('#hdrHoleCount .kop-agenda')?.click(); }")
        check("het icoon opent precies die tekst als adres", await ev(pg, "() => window.__geopend"), [streek])
        check("geen dialoogvensters", dialogen, [])

        print("\n=== 6. WAT AL IN DE OPSLAG STAAT ===\n")
        for slecht in ('javascript:alert(1)', 'data:text/html,x', 'ms outlook://x', 'http://x'):
            await ev(pg, "(v) => localStorage.setItem('golf_agenda_link', v)", slecht); await pg.reload(); await pg.wait_for_timeout(400)
            await ev(pg, VANG)
            r = await ev(pg, "() => { nav('score'); document.querySelector('#hdrHoleCount .kop-agenda')?.click(); return [agendaLink(), window.__geopend]; }")
            check(f"in de opslag {slecht!r}: de standaard geldt", r, ['ms-outlook://calendar', ['ms-outlook://calendar']])
        await ev(pg, "() => nav('settings')"); await ev(pg, SECTIE); await pg.wait_for_timeout(200)
        check("en het veld toont de standaard", await ev(pg, "() => document.getElementById('agendaLinkInput').value"), 'ms-outlook://calendar')
        check("Alles wissen haalt de instelling weg (register)", await ev(pg, "() => OPSLAGSLEUTELS.golf_agenda_link"), 'wissen')

        check("geen paginafouten", pf, [])
        await b.close()
    print(f"\n{len(fouten)} FOUT(EN): {', '.join(fouten)}" if fouten else "\nGEEN FOUTEN")
    sys.exit(1 if fouten else 0)

asyncio.run(main())
