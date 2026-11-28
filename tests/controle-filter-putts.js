const fs = require('fs');
const html = fs.readFileSync(process.env.APP || require('path').join(__dirname, '..', 'golf-score.html'), 'utf8');
let fout = 0, punt = 0;
const ok = (goed, tekst, detail) => { if (!goed) fout++; console.log((goed ? '  ok  ' : ' FOUT ') + tekst + (detail ? ' → ' + detail : '')); };
const let_op = (tekst) => { punt++; console.log(' let op ' + tekst); };

console.log('=== 1. SYNTAX ===');
const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]).filter(s => s.trim());
let sOk = true, sFout = '';
scripts.forEach(s => { try { new Function(s); } catch (e) { sOk = false; sFout = e.message; } });
ok(sOk, 'JS-syntax', sFout);
const js = scripts.join('\n');

console.log('\n=== 2. FILTERMECHANISME: samenhang ===');
const filters = ['warn', 'dup', 'putt'];
filters.forEach(f => ok(js.includes(`'${f}'`), `filtersoort '${f}' bestaat`));
ok(js.includes('const dupNu = _warnFilterActive'), 'dup berekent de duplicaten zelf (geen volgorde-afhankelijkheid)');
ok(js.includes("_warnFilterActive === 'putt' ? roundHasPuttWarning(r)"), 'putt leest rechtstreeks de rondes');
ok(js.includes(': roundHasWarning(r))'), 'warn leest alleen ontbrekende dagresultaten');
ok(!js.includes('_dupIds'), 'de duplicaten worden niet apart bewaard: het filter rekent ze zelf uit');
ok(js.includes('if (_warnFilterActive && !bron.length)'), 'filter heft zichzelf op als er niets meer aan voldoet');
ok(js.includes('function clearWarnFilter'), 'clearWarnFilter bestaat (×-knop)');
ok(js.includes("if (!lijst.length || _warnFilterActive)"), 'meldingenblok verbergt zich tijdens een filter');

ok(!js.includes('window._dupIds && window._dupIds.has'), 'filter leunt niet meer op een eerder gevulde verzameling');
ok(js.includes('refreshStatusReminder(saved)'), 'refreshStatusReminder draait bij elke tekenRondelijst (met de lijst mee)');

console.log('\n=== 3. FILTER: gedragssimulatie ===');
const rondes = [
  { id: 1, sd: false, dup: false, putt: false },   // schoon
  { id: 2, sd: true,  dup: false, putt: false },   // zonder dagresultaat
  { id: 3, sd: false, dup: true,  putt: false },   // duplicaat
  { id: 4, sd: false, dup: false, putt: true },    // onvolledige putts
  { id: 5, sd: true,  dup: false, putt: true },    // beide
];
const dupIds = new Set(rondes.filter(r => r.dup).map(r => String(r.id)));
const pas = (f, r) => f === 'dup' ? dupIds.has(String(r.id)) : f === 'putt' ? r.putt : r.sd;
filters.forEach(f => {
  const lijst = rondes.filter(r => pas(f, r)).map(r => r.id);
  console.log('  filter ' + f.padEnd(5) + '→ rondes ' + JSON.stringify(lijst));
});
ok(rondes.filter(r => pas('warn', r)).length === 2, "warn toont ronde 2 en 5 (niet de puttronde)");
ok(rondes.filter(r => pas('putt', r)).length === 2, 'putt toont ronde 4 en 5');
ok(!rondes.filter(r => pas('warn', r)).some(r => r.id === 4), 'een pure puttronde valt NIET onder warn');

console.log('\n=== 4. PUTTS: gegevensregels ===');
const trackAan = { v: true };
const sync = h => { if (h.score === null) { delete h.putts; return; } if (!trackAan.v) return; if (h.putts == null) h.putts = 2; };
const step = (h, d) => { if (h.score === null || !trackAan.v) return; if (h.putts == null) { h.putts = 2; } else { const n = h.putts + d; if (n < 0) delete h.putts; else h.putts = Math.min(5, n); } };
let h = { par: 4, score: null };
sync(h); ok(!('putts' in h), 'geen score → geen putts');
h.score = 5; sync(h); ok(h.putts === 2, 'score invullen → 2');
step(h, -1); step(h, -1); ok(h.putts === 0, 'aftellen tot 0', 'nu ' + h.putts);
step(h, -1); ok(!('putts' in h), 'onder 0 → leeg');
step(h, -1); ok(h.putts === 2, 'vanuit leeg start elke knop op 2');
for (let i = 0; i < 9; i++) step(h, 1); ok(h.putts === 5, 'bovengrens 5');
h.score = null; sync(h); ok(!('putts' in h), 'score wissen → putts weg');
trackAan.v = false;
let oud = { par: 4, score: 6 }; sync(oud); step(oud, 1);
ok(!('putts' in oud), 'instelling uit → oude ronde blijft ongemoeid');
trackAan.v = true;
let backup = { par: 4, score: 5, putts: 1 }; sync(backup); ok(backup.putts === 1, 'bestaande waarde uit backup blijft');

console.log('\n=== 5. PUTTS: waarschuwing en statistiek ===');
const warn = holes => { const g = holes.filter(x => x && x.score != null); if (g.length < 2) return false; const m = g.filter(x => x.putts != null).length; return m > 0 && m < g.length; };
ok(!warn([{ score: 4 }, { score: 5 }]), 'nergens putts → geen waarschuwing');
ok(!warn([{ score: 4, putts: 2 }, { score: 5, putts: 2 }]), 'overal putts → geen waarschuwing');
ok(warn([{ score: 4, putts: 2 }, { score: 5 }]), 'deels putts → waarschuwing');
ok(!warn([{ score: 4, putts: 0 }, { score: 5, putts: 2 }]), '0 telt als ingevuld');
ok(!warn([null, { score: 4, putts: 2 }]), 'lege hole in de lijst breekt niets');
ok(!warn([{ score: 4, putts: 2 }]), 'één hole → geen waarschuwing (te weinig om te vergelijken)');

const compleet = r => { const g = (r.holes || []).filter(x => x && x.score != null); return g.length > 0 && g.every(x => x.putts != null); };
ok(compleet({ holes: [{ score: 4, putts: 2 }] }), 'volledige ronde telt mee voor statistiek');
ok(!compleet({ holes: [{ score: 4, putts: 2 }, { score: 5 }] }), 'halve ronde telt niet mee');
ok(!compleet({ holes: [] }), 'lege ronde telt niet mee');
ok(!compleet({ holes: [{ score: null, putts: 2 }] }), 'ongespeelde hole telt niet als gespeeld');

console.log('\n=== 6. GIR EN AFGELEIDEN ===');
const gir = h => h.score - h.putts <= h.par - 2;
ok(gir({ par: 4, score: 4, putts: 2 }), 'par 4 in 2 slagen + 2 putts = GIR');
ok(!gir({ par: 4, score: 5, putts: 2 }), 'par 4 in 3 slagen + 2 putts = geen GIR');
ok(gir({ par: 3, score: 3, putts: 2 }), 'par 3 op de green in 1 = GIR');
ok(!gir({ par: 4, score: 4, putts: 1 }), 'chip-in telt terecht niet als GIR');
const holes = [{ par: 4, score: 5, putts: 2 }, { par: 4, score: 4, putts: 2 }];
const vTot = holes.reduce((s, x) => s + (x.score - x.par), 0);
const vVoor = holes.reduce((s, x) => s + ((x.score - x.putts) - (x.par - 2)), 0);
const vOp = holes.reduce((s, x) => s + (x.putts - 2), 0);
ok(vVoor + vOp === vTot, 'splitsing telt exact op tot het totale verlies', `${vVoor} + ${vOp} = ${vTot}`);

console.log('\n=== 7. RAAKVLAKKEN MET BESTAANDE CODE ===');
ok(js.includes('holes: game.holes.map(h => ({ ...h }))'), 'putts liften mee in buildRoundEntry (integrale kopie)');
ok(!/putts:\s*null/.test(js), 'nooit putts:null weggeschreven');
ok((js.match(/delete h\.putts/g) || []).length >= 2, 'wissen verwijdert de sleutel');
ok(js.includes("storage.getItem('golf_track_putts')") && js.includes("storage.getItem('golf_putts_stats')"), 'beide instellingen worden gelezen');
ok(html.includes("golf_track_putts: 'wissen'") && html.includes("golf_putts_stats: 'wissen'"), 'beide sleutels gewist bij Alles wissen (OPSLAGSLEUTELS)');
ok(js.includes('if (!game || !game.started'), 'geen puttregel zonder actieve ronde');
ok(js.includes("document.getElementById('puttOverlay')?.remove()"), 'zwevende regel wordt opgeruimd');
ok(js.includes("paneel.style.position = 'absolute'"), 'zwevende regel scrolt mee (absoluut in de lijst)');
ok(js.includes('roundHasPuttWarning(r) ? puttWarnIcon'), 'waarschuwingsicoon op de archiefkaart');
ok(js.includes("['Putts'") && js.includes("['Putts per hole'"), 'beide regels in het rondeoverzicht');

console.log('\n=== 8. DODE CODE ===');
['refreshDataHealth', 'dataHealthClick', 'dataHealthLine', 'gaNaarBackup', 'statusRegel', 'puttRowCells',
 'puttsInlineEnabled', 'golf_putts_inline', 'updateBackupReminder', 'backupReminder"'].forEach(r =>
  ok(!html.includes(r), 'restant "' + r + '" opgeruimd'));

console.log('\n=== 9. TAGBALANS ===');
['span', 'button', 'svg', 'label'].forEach(t => {
  const o = (html.match(new RegExp('<' + t + '[\\s>]', 'g')) || []).length;
  const c = (html.match(new RegExp('</' + t + '>', 'g')) || []).length;
  ok(o === c, 'tagbalans ' + t, o + '/' + c);
});

console.log('\n' + (fout === 0 ? 'GEEN FOUTEN' : fout + ' FOUT(EN)') + (punt ? ', ' + punt + ' aandachtspunt(en)' : ''));
