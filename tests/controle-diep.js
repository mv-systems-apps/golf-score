const fs = require('fs');
const html = fs.readFileSync(process.env.APP || require('path').join(__dirname, '..', 'golf-score.html'), 'utf8');
const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]).filter(s => s.trim());
const js = scripts.join('\n');
const htmlZonderJs = scripts.reduce((acc, s) => acc.replace(s, ''), html);
let fout = 0, punt = 0;
const ok = (g, t, d) => { if (!g) fout++; console.log((g ? '  ok  ' : ' FOUT ') + t + (d ? ' → ' + d : '')); };
const let_op = t => { punt++; console.log(' let op ' + t); };

console.log('=== 1. SYNTAX ===');
let sOk = true, sFout = '';
scripts.forEach((s, i) => { try { new Function(s); } catch (e) { sOk = false; sFout = 'blok ' + (i + 1) + ': ' + e.message; } });
ok(sOk, 'elk scriptblok afzonderlijk (' + scripts.length + ' blokken)', sFout);
try { new Function(js); ok(true, 'alle blokken samen'); } catch (e) { ok(false, 'alle blokken samen', e.message); }
try { new Function('"use strict";' + js); ok(true, 'ook onder strikte regels'); }
catch (e) { ok(false, 'onder strikte regels', e.message); }

console.log('\n=== 2. ACCOLADEBALANS PER FUNCTIE ===');
const functies = [...js.matchAll(/^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(/gm)];
let scheef = 0;
functies.forEach((m, idx) => {
  const seg = js.slice(m.index, idx + 1 < functies.length ? functies[idx + 1].index : js.length);
  const open = (seg.match(/\{/g) || []).length, dicht = (seg.match(/\}/g) || []).length;
  if (Math.abs(open - dicht) > 1) { scheef++; console.log('   ' + m[1] + ': { ' + open + ' vs } ' + dicht); }
});
ok(scheef === 0, functies.length + ' functies met sluitende accolades');

console.log('\n=== 3. DODE CODE: FUNCTIES ===');
const gedef = [...new Set(functies.map(m => m[1]))];
const zelfaanroepend = [...new Set([...js.matchAll(/\(function\s+([A-Za-z_$][\w$]*)\s*\(/g)].map(m => m[1]))];
const dood = gedef.filter(f => {
  if (zelfaanroepend.includes(f)) return false;
  const naam = f.replace(/\$/g, '\\$');
  const gebruikJs = (js.match(new RegExp('\\b' + naam + '\\b', 'g')) || []).length;   // 1 = alleen de definitie
  const gebruikHtml = (htmlZonderJs.match(new RegExp('\\b' + naam + '\\b', 'g')) || []).length;
  return gebruikJs <= 1 && gebruikHtml === 0;
});
ok(dood.length === 0, gedef.length + ' functies, geen ongebruikte', dood.join(', '));
console.log('        (' + zelfaanroepend.length + ' zelfaanroepend, overgeslagen: ' + zelfaanroepend.join(', ') + ')');

console.log('\n=== 4. DODE CODE: VARIABELEN OP TOPNIVEAU ===');
const topVars = [...new Set([...js.matchAll(/^(?:let|const|var)\s+([A-Za-z_$][\w$]*)\s*=/gm)].map(m => m[1]))];
const doodVar = topVars.filter(v => {
  const naam = v.replace(/\$/g, '\\$');
  return (js.match(new RegExp('\\b' + naam + '\\b', 'g')) || []).length <= 1 &&
         (htmlZonderJs.match(new RegExp('\\b' + naam + '\\b', 'g')) || []).length === 0;
});
ok(doodVar.length === 0, topVars.length + ' variabelen op topniveau, geen ongebruikte', doodVar.join(', '));

console.log('\n=== 5. DODE CODE: CSS-KLASSEN ===');
const css = html.slice(html.indexOf('<style'), html.indexOf('</style>'));
const klassen = [...new Set([...css.matchAll(/\.([a-z][\w-]*)\s*[,{:.\s]/g)].map(m => m[1]))];
const ongebruikt = klassen.filter(k => {
  const inHtml = new RegExp('class="[^"]*\\b' + k + '\\b').test(html);
  const inJs = new RegExp('[\'"`][^\'"`]{0,60}\\b' + k + '\\b').test(js);
  // Klassen die in code worden samengesteld ('tee-' + kleur) of alleen als selector
  // in andere CSS-regels voorkomen, tellen niet als ongebruikt.
  const samengesteld = new RegExp("'" + k.split('-')[0] + "-' \\+").test(js);
  const alsSelector = new RegExp('\\.' + k + '\\s*[ ,>]').test(css);
  return !inHtml && !inJs && !samengesteld && !alsSelector;
});
ok(ongebruikt.length === 0, klassen.length + ' CSS-klassen, geen ongebruikte', ongebruikt.slice(0, 15).join(', '));

console.log('\n=== 6. OPSLAGSLEUTELS ===');
const geschreven = [...new Set([...js.matchAll(/storage\.setItem\(\s*'([\w-]+)'/g)].map(m => m[1]))];
const gelezen = [...new Set([...js.matchAll(/storage\.getItem\(\s*'([\w-]+)'/g)].map(m => m[1]))];
const alleenGeschreven = geschreven.filter(k => !gelezen.includes(k));
ok(alleenGeschreven.length === 0, geschreven.length + ' sleutels geschreven, allemaal ook gelezen', alleenGeschreven.join(', '));
const alleenGelezen = gelezen.filter(k => !geschreven.includes(k));
if (alleenGelezen.length) let_op('alleen gelezen: ' + alleenGelezen.join(', '));

console.log('\n=== 7. ELEMENTEN ===');
const ids = [...new Set([...html.matchAll(/id="([\w-]+)"/g)].map(m => m[1]))];
const dynamisch = [...new Set([...js.matchAll(/\.id\s*=\s*'([\w-]+)'/g)].map(m => m[1]))];
const opgevraagd = [...new Set([...js.matchAll(/getElementById\('([\w-]+)'\)/g)].map(m => m[1]))];
const missend = opgevraagd.filter(i => !ids.includes(i) && !dynamisch.includes(i));
ok(missend.length === 0, opgevraagd.length + ' opgevraagde id\'s bestaan allemaal', missend.join(', '));
const ongebruikteIds = ids.filter(i => !js.includes("'" + i + "'") && !js.includes('"' + i + '"') && !css.includes('#' + i));
// Id's die via een samengestelde naam worden opgezocht ('tab-' + x, 'screen-' + x)
// of die alleen als aanknopingspunt in de opmaak dienen, tellen niet als ongebruikt.
const samengesteldeIds = ongebruikteIds.filter(i => !/^(tab|screen)-/.test(i));
if (samengesteldeIds.length) let_op(samengesteldeIds.length + " id's worden nergens opgevraagd (mogelijk alleen als anker): " + samengesteldeIds.slice(0, 8).join(', '));

console.log('\n=== 8. HANDLERS IN DE HTML ===');
const handlers = [...new Set([...html.matchAll(/on\w+="\s*(?:event\.\w+\(\);\s*)?([A-Za-z_$][\w$]*)\s*\(/g)].map(m => m[1]))];
const ontbrekend = handlers.filter(h => !gedef.includes(h) && !topVars.includes(h) &&
  !['window', 'document', 'this', 'event', 'alert', 'console', 'var', 'if', 'return'].includes(h) &&
  !new RegExp('\\b' + h + '\\s*=\\s*(?:function|\\(|async)').test(js));
ok(ontbrekend.length === 0, handlers.length + ' handlers, alle gedefinieerd', ontbrekend.join(', '));

console.log('\n=== 9. RESTANTEN VAN VERWIJDERDE ONDERDELEN ===');
// renderPuttOverlay en roundResultModal zijn in gebruik (zwevende puttregel en het
// resultaatvenster); alleen echt vervallen namen staan hier.
const restanten = ['refreshPuttOverlay', 'puttRowCells', 'statusRegel', 'switchRoundTab',
  'confirmRoundEdit', 'pasResultaatToe', 'gaNaarBackup', 'updateBackupReminder', 'dataHealthClick',
  'puttsInlineEnabled', 'golf_putts_inline',
  // vervallen backupdrempels (13527DA-0F1): alleen de opslagsleutels worden nog opgeruimd
  'adjustBackupReminderDays', 'adjustBackupReminderRounds', 'getBackupReminderDays',
  'getBackupReminderRounds', 'setBackupReminderDays', 'setBackupReminderRounds',
  'backupReminderDaysVal', 'backupReminderRoundsVal'].filter(f =>
  (html.match(new RegExp('\\b' + f + '\\b', 'g')) || []).length > 0);
console.log('  nog aanwezig: ' + (restanten.length ? restanten.join(', ') : 'geen'));
ok(true, 'gecontroleerd');
// Contactgegevens zijn uit de app gehaald (13527DA-0F6/0F7), samen met de zinnen die
// ernaar verwezen. Dit is een echte controle: komt er iets terug, dan is dat een fout.
const contact = [/vandervelden/i, /@gmail/i, /adres\s+hierboven/i, /meld\s+dit/i, /stuur\s+een\s+bericht/i]
  .filter(r => r.test(html)).map(String);
ok(contact.length === 0, 'geen contactgegevens of verwijzingen ernaar', contact.join(', '));

// ── Meldingen duren overal even lang ────────────────────────────────────────
// Een bevestiging 2000 ms, een foutmelding 3000 ms. Er zijn drie vormen naast elkaar
// gegroeid (een groene regel bij de knop, de knoptekst die verandert, en een venster);
// de duur hoort in elk geval gelijk te zijn, anders voelt de app ongelijkmatig.
{
  const duren = [];
  const re = /setTimeout\(/g;
  let m;
  while ((m = re.exec(js))) {
    const stuk = js.slice(m.index, m.index + 400);
    const d = /\},\s*(\d+)\s*\)/.exec(stuk);
    if (!d) continue;
    const voor = js.slice(Math.max(0, m.index - 300), m.index);
    if (!/Msg|Melding|Status|Gekopieerd/.test(voor + stuk)) continue;
    duren.push(+d[1]);
  }
  const afwijkend = duren.filter(d => d !== 2000 && d !== 3000);
  ok(duren.length > 5 && afwijkend.length === 0,
     'meldingen duren 2000 ms (bevestiging) of 3000 ms (fout)',
     `${duren.length} gevonden, afwijkend: ${afwijkend.join(', ') || 'geen'}`);
}


console.log('\n=== 10. DE PIJLTJES VAN DE UITKLAPKOPJES ===');
{
  // De opmaakregel .more-toggle.open draait het pijltje 90 graden. Dat klopt alleen als
  // het pijltje in dichte stand naar RECHTS wijst. Twee kopjes (Handicap bijhouden en
  // Deze installatie) hadden een pijl naar BENEDEN: die kwam na het draaien links uit.
  const NAAR_RECHTS = '9 6 15 12 9 18';
  const varianten = new Map();
  const re = /class="more-toggle"[^>]*>[\s\S]{0,80}?<svg([\s\S]{0,240}?)<\/svg>/g;
  let m;
  while ((m = re.exec(html))) {
    const punten = /points="([^"]+)"/.exec(m[1]);
    const dikte = /stroke-width="(\d)"/.exec(m[1]);
    const sleutel = `${punten ? punten[1] : '?'} | dikte ${dikte ? dikte[1] : '?'}`;
    varianten.set(sleutel, (varianten.get(sleutel) || 0) + 1);
  }
  const lijst = [...varianten.entries()].map(([k, n]) => `${k} (${n}x)`);
  ok(varianten.size === 1 && [...varianten.keys()][0].startsWith(NAAR_RECHTS),
     'alle uitklapkopjes hebben hetzelfde pijltje, naar rechts',
     lijst.join(' / '));
}

console.log('\n' + (fout === 0 ? 'GEEN FOUTEN' : fout + ' FOUT(EN)') + (punt ? ', ' + punt + ' aandachtspunt(en)' : ''));
