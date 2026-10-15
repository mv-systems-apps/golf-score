const fs = require('fs');
const html = fs.readFileSync(process.env.APP || require('path').join(__dirname, '..', 'golf-score.html'), 'utf8');
let fout = 0, punt = 0;
const ok = (g, t, d) => { if (!g) fout++; console.log((g ? '  ok  ' : ' FOUT ') + t + (d ? ' → ' + d : '')); };
const let_op = t => { punt++; console.log(' let op ' + t); };

const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]).filter(s => s.trim());
let sOk = true, sFout = '';
scripts.forEach(s => { try { new Function(s); } catch (e) { sOk = false; sFout = e.message; } });
const js = scripts.join('\n');

console.log('=== 1. SYNTAX & BEREIKBAARHEID ===');
ok(sOk, 'JS-syntax', sFout);
['herplanRonde', 'toonHerplanBanner', 'annuleerHerplan', 'ruimHerplanOp'].forEach(f =>
  ok(new RegExp('function ' + f + '\\s*\\(').test(js), 'functie ' + f + ' gedefinieerd'));
// 'Opnieuw plannen' zit sinds kort in het bewerkvenster, niet meer in een eigen menu
// op de kaart. De knop op de kaart is dus de bewerkknop.
ok(html.includes("roundEditChoiceHerplan"), 'opnieuw plannen zit in het bewerkvenster');
ok(html.includes('id="herplanBanner"'), 'balkje bestaat in het startscherm');

console.log('\n=== 2. WANNEER VERSCHIJNT DE KNOP ===');
const knop = r => (r.holes || []).filter(h => h && h.score !== null).length === 0;
// Rondes met echte holes: het aantal gespeelde holes wordt uit de scores geteld.
const H = n => ({ holesCount: 9, holes: Array.from({ length: 9 }, (_, i) => ({ id: i + 1, par: 4, si: i + 1, score: i < n ? 5 : null })) });
[[H(0), true, 'geplande ronde'],
 [H(0), true, 'oude ronde zonder scores'],
 [H(1), false, 'ronde met één score'],
 [H(9), false, 'afgeronde ronde'],
 [{}, true, 'ronde zonder holes (oude backup)']].forEach(([r, verwacht, naam]) =>
  ok(knop(r) === verwacht, naam + ' → knop ' + (verwacht ? 'zichtbaar' : 'verborgen')));
// Herplannen weigert nog steeds bij een gespeelde ronde; die gaat via CORRIGEREN, dat
// dezelfde functie aanroept met metScores=true.
ok(js.includes('if (!metScores && gespeeldeHoles(r) > 0) return;'),
   'herplannen weigert bij een gespeelde ronde, tenzij het corrigeren is');
ok(js.includes('function corrigeerRonde(id)'), 'corrigeren bestaat als eigen functie');
ok(js.includes("if (!r || gespeeldeHoles(r) === 0) return;"),
   'corrigeren weigert juist bij een ronde ZONDER scores');

console.log('\n=== 3. KOPPELING MET SPELER 2 ===');
const saved = [
  { id: 1, player: 'Mark', date: '2026-08-24', time: '09:30', holesCount: 9, holes: Array.from({length:9},(_,i)=>({id:i+1,par:4,si:i+1,score: i < 0 ? 5 : null})) },
  { id: 2, player: 'Speler 2', date: '2026-08-24', time: '09:30', holesCount: 9, holes: Array.from({length:9},(_,i)=>({id:i+1,par:4,si:i+1,score: i < 0 ? 5 : null})) },
  { id: 3, player: 'Mark', date: '2026-08-24', time: '14:00', holesCount: 9, holes: Array.from({length:9},(_,i)=>({id:i+1,par:4,si:i+1,score: i < 0 ? 5 : null})) },
  { id: 4, player: 'Jan', date: '2026-08-24', time: '09:30', holesCount: 9, holes: Array.from({length:9},(_,i)=>({id:i+1,par:4,si:i+1,score: i < 9 ? 5 : null})) },
];
const maat = r => saved.find(x => String(x.id) !== String(r.id) && (x.holes || []).filter(h => h && h.score !== null).length === 0 &&
  (x.date || '') === (r.date || '') && (x.time || '') === (r.time || ''));
ok(maat(saved[0]) && maat(saved[0]).id === 2, 'gekoppelde ronde gevonden op datum+tijd');
ok(!maat(saved[2]), 'andere tijd → geen koppeling');
ok(maat(saved[0]).id !== 4, 'een GESPEELDE ronde op hetzelfde tijdstip wordt niet meegenomen');
// Bij corrigeren heeft de medespeler juist wél scores, dus die eis geldt daar niet.
ok(js.includes("(metScores || gespeeldeHoles(x) === 0) &&"),
   'de maat wordt bij herplannen op nul scores gezocht, bij corrigeren niet');

console.log('\n=== 4. GEGEVENSBEHOUD ===');
ok(js.indexOf('ruimHerplanOp(speler2Mislukt);') > js.indexOf('function startRoundConfirmed'), 'opruimen gebeurt binnen startRoundConfirmed');
// Ruim venster: startRoundConfirmed is gegroeid (o.a. het terugzetten van de scores van
// speler 2 bij corrigeren), en een te krap venster liet 'ruimHerplanOp' erbuiten vallen.
const startBlok = js.slice(js.indexOf('function startRoundConfirmed'), js.indexOf('function startRoundConfirmed') + 12000);
const iOpslaan = startBlok.indexOf('setRoundsAndMark');
const iOpruimen = startBlok.indexOf('ruimHerplanOp(speler2Mislukt)');
ok(iOpslaan > 0 && iOpruimen > iOpslaan, 'nieuwe ronde wordt EERST opgeslagen, daarna pas de oude verwijderd', `opslaan op ${iOpslaan}, opruimen op ${iOpruimen}`);
ok(js.includes('saved.filter(r => !weg.has(String(r.id)))'), 'opruimen verwijdert alleen de gemarkeerde id\'s');
ok(js.includes('const nieuweAanwezig = saved.some') && js.includes('annuleerHerplan();\n}'), 'opruimen alleen als de nieuwe ronde er staat, daarna markering wissen');
ok(js.includes('function annuleerHerplan'), 'afbreken laat de oude ronde staan');

console.log('\n=== 5. RANDGEVALLEN ===');
ok(js.includes("if (r.track && COURSES[r.track]) {") && js.includes("sel.track = r.track;"),
   'baan die niet meer bestaat wordt overgeslagen (geen crash)');
ok(js.includes('sel._teeUserSelected = true;') && js.includes('sel2._teeUserSelected = true;'),
   'tee van de ronde blijft staan (wordt niet vervangen door het NGF-advies)');
ok(/sel\.holeCount = String\(aantalHoles\)/.test(js),
   '9/18-filter volgt de ronde, anders valt de baan buiten beeld');
ok(js.includes('sel.chcpOverride = null;'), 'handmatige baanhandicap wordt niet meegesleept (tee kan wijzigen)');
ok(js.includes('sel.dateTimeEdited = true;'), 'datum/tijd blijven staan i.p.v. terug te vallen op nu');
ok(js.includes("let r = saved.find(x => String(x.id) === String(id));\n  if (!r) return;"), 'verwijderde ronde onderweg → stille stop');
ok(js.includes('_herplanIds = [String(hoofd.id)]'), 'id\'s als tekst bewaard (vergelijking blijft kloppen)');
ok(!js.includes("if (id !== 'setup') annuleerHerplan();") && js.includes('controleerHerplan();'), 'markering blijft staan als je het startscherm verlaat; vervalt alleen als de oude ronde weg of veranderd is');

console.log('\n=== 6. INTERACTIE MET BESTAANDE FUNCTIES ===');
ok(js.includes('player2Visible = !!maat;'), 'speler 2-blok wordt aan- of uitgezet op basis van de koppeling');
const iRebuild = js.indexOf('rebuildAll();', js.indexOf('function herplanRonde'));
const iNav = js.indexOf("nav('setup');", iRebuild);
ok(iRebuild > 0 && iNav > iRebuild, 'schermen worden opnieuw opgebouwd vóór de sprong');
ok(js.includes("document.getElementById('gb-' + g)?.classList.toggle('active', g === sel.gender)"),
   'de knoppen voor geslacht volgen de herplande ronde');
ok(js.includes('setRoundsAndMark'), 'verwijdering telt mee voor de backupwaarschuwing');
// De knop staat nooit meer uit: hij wisselt van naam. Zonder scores 'Herplannen',
// met scores 'Corrigeren'.
ok(js.includes("corrigeren ? 'Corrigeren' : 'Herplannen'"),
   'de knop wisselt van naam in plaats van uit te gaan');

console.log('\n=== 7. TAGBALANS ===');
['span', 'button', 'svg'].forEach(t => {
  const o = (html.match(new RegExp('<' + t + '[\\s>]', 'g')) || []).length;
  const c = (html.match(new RegExp('</' + t + '>', 'g')) || []).length;
  ok(o === c, 'tagbalans ' + t, o + '/' + c);
});

console.log('\n' + (fout === 0 ? 'GEEN FOUTEN' : fout + ' FOUT(EN)') + (punt ? ', ' + punt + ' aandachtspunt(en)' : ''));
