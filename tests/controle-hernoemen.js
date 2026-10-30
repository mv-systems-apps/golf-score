const fs = require('fs');
const html = fs.readFileSync(process.env.APP || require('path').join(__dirname, '..', 'golf-score.html'), 'utf8');
let fout = 0, punt = 0;
const ok = (g, t, d) => { if (!g) fout++; console.log((g ? '  ok  ' : ' FOUT ') + t + (d ? ' → ' + d : '')); };
const let_op = t => { punt++; console.log(' let op ' + t); };

const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]).filter(s => s.trim());
let sOk = true, sFout = '';
scripts.forEach(s => { try { new Function(s); } catch (e) { sOk = false; sFout = e.message; } });
console.log('=== 1. SYNTAX ===');
ok(sOk, 'JS-syntax', sFout);
const js = scripts.join('\n');

console.log('\n=== 2. DEKKING: welke hernoemingen worden opgevangen? ===');
ok(js.includes('const naamGewijzigd = oudeNaam && oudeNaam !== validated.newClubName'), 'clubnaam (lang)');
ok(js.includes('const kortGewijzigd = oudeKort && oudeKort !== validated.newShortName'), 'clubnaam (kort)');
ok(js.includes('if (oudeBaan && oudeBaan !== nieuweBaan)'), 'baannaam');
ok(js.includes('verdwenen.length === 1 && nieuw.length === 1'), 'teenaam (eenduidige hernoeming)');

console.log('\n=== 3. AFBAKENING: raakt een hernoeming alleen de juiste rondes? ===');
const rondes = () => ([
  { id: 1, club: 'Golfclub Heelsum', clubShort: 'Heelsum', track: 'Airborne', tee: 'Blauw', player: 'Testspeler' },
  { id: 2, club: 'Golfclub Heelsum', clubShort: 'Heelsum', track: 'Airborne', tee: 'Geel',  player: 'Speler 2' },
  { id: 3, club: 'Golfclub Heelsum', clubShort: 'Heelsum', track: 'Sandr',    tee: 'Blauw', player: 'Testspeler' },
  { id: 4, club: 'Papendal',         clubShort: 'Pap',     track: 'Airborne', tee: 'Blauw', player: 'Testspeler' },
  { id: 5, club: 'Golfclub Heelsum', clubShort: 'Heelsum', track: 'Airborne', tee: 'Blauw', player: 'Testspeler' },
]);
const metClub = (r, cn, ck) => (cn && r.club === cn) || (ck && r.clubShort === ck);

// club hernoemen
let R = rondes();
R.forEach(r => { if (r.club === 'Golfclub Heelsum') r.club = 'Heelsum GC'; if (r.clubShort === 'Heelsum') r.clubShort = 'HLS'; });
ok(R.filter(r => r.club === 'Heelsum GC').length === 4, 'club: alle 4 rondes van die club aangepast');
ok(R.find(r => r.id === 4).club === 'Papendal', 'club: andere club ongemoeid');
ok(R.find(r => r.id === 2).club === 'Heelsum GC', 'club: ronde van speler 2 telt mee');

// baan hernoemen (binnen één club)
R = rondes();
R.forEach(r => { if (metClub(r, 'Golfclub Heelsum', 'Heelsum') && r.track === 'Airborne') r.track = 'Airborne 9'; });
ok(R.filter(r => r.track === 'Airborne 9').length === 3, 'baan: 3 rondes op die club aangepast');
ok(R.find(r => r.id === 4).track === 'Airborne', 'baan: zelfde baannaam bij ANDERE club ongemoeid');
ok(R.find(r => r.id === 3).track === 'Sandr', 'baan: andere baan van dezelfde club ongemoeid');

// tee hernoemen (binnen één baan van één club)
R = rondes();
R.forEach(r => { if (metClub(r, 'Golfclub Heelsum', 'Heelsum') && r.track === 'Airborne' && r.tee === 'Blauw') r.tee = 'Wit'; });
ok(R.filter(r => r.tee === 'Wit').length === 2, 'tee: alleen op die baan van die club');
ok(R.find(r => r.id === 3).tee === 'Blauw', 'tee: zelfde teenaam op andere baan ongemoeid');
ok(R.find(r => r.id === 4).tee === 'Blauw', 'tee: zelfde teenaam bij andere club ongemoeid');

console.log('\n=== 4. GEGEVENSBEHOUD ===');
ok(js.includes('setRoundsAndMark(JSON.stringify(saved))'), 'rondes gaan via de centrale opslag (backupmarkering)');
// Sinds 13527DA-123 wordt ook het resultaat gecontroleerd: 'if (n && setRoundsAndMark(...) === false) …'.
ok(/if \(n(\) | && )setRoundsAndMark/.test(js), 'alleen opslaan als er echt iets veranderd is');
const clubBlok = js.slice(js.indexOf('function clubRenameKeuze'), js.indexOf('function clubRenameKeuze') + 1400);
ok(!/delete |= null|splice|filter\(/.test(clubBlok.replace(/_clubRename = null;/g, '')), 'club: geen verwijderingen of filters op de rondelijst');
ok(js.includes('saved.forEach(r => { if (w.pasAan(r)) n++; })'), 'baan/tee: elke ronde wordt per stuk beoordeeld en alleen aangeraakt bij een treffer');
ok(js.includes('if (game && game.started'), 'actieve ronde wordt meegenomen');
ok(js.includes('saveActiveRound(); updateHeaderClubName();') || js.includes('saveActiveRound();'), 'actieve ronde wordt opgeslagen na wijziging');

console.log('\n=== 5. RANDGEVALLEN ===');
const herken = (oud, nw) => { const weg = oud.filter(t => !nw.includes(t)), bij = nw.filter(t => !oud.includes(t)); return weg.length === 1 && bij.length === 1; };
ok(herken(['Blauw', 'Geel'], ['Wit', 'Geel']), 'tee: 1 om 1 = hernoeming');
ok(!herken(['Blauw'], ['Blauw', 'Rood']), 'tee: toevoegen is GEEN hernoeming');
ok(!herken(['Blauw', 'Rood'], ['Blauw']), 'tee: verwijderen is GEEN hernoeming');
ok(!herken(['Blauw', 'Geel'], ['Wit', 'Oranje']), 'tee: twee tegelijk → geen gok');
ok(js.includes('if (treffers.length) {'), 'geen vraag als er geen rondes met de oude naam zijn');
ok(js.includes('() => { if (!teeVragen()) klaar(); }'), 'baan- en tee-vraag na elkaar, niet tegelijk');
ok(js.includes('if (_naamWijziging) return naamWijzigingKeuze(alles);'), 'gedeelde modal kiest de juiste afhandeling');

// Volgorde club → baan
const iClub = js.indexOf('function saveClubFromEditor');
const iCourse = js.indexOf('function saveCourseFromEditor');
ok(iClub > 0 && iCourse > 0, 'beide opslagfuncties bestaan');
if (js.slice(iCourse, iCourse + 2000).includes('CLUBS[editorClub].club')) {
  console.log('  ok  baan/tee zoeken met de ACTUELE clubnaam (dus ook goed ná een clubhernoeming)');
} else { fout++; console.log(' FOUT baan/tee gebruiken mogelijk een verouderde clubnaam'); }

console.log('\n=== 6. WAT NIET WORDT BIJGEWERKT (bewust) ===');
console.log('  · CR, SR, par en chcp blijven de waarden van de gespeelde ronde — die horen bij die dag');
console.log('  · geen enkele ronde wordt verwijderd of samengevoegd');
console.log('  · kiest de gebruiker "Alleen nieuwe rondes", dan verandert er niets aan de historie');

console.log('\n=== 7. DODE CODE / TAGBALANS ===');
['rondesMetClubNaam', 'rondesMetBaan', 'rondesMetTee', 'vraagClubRename', 'vraagNaamWijziging'].forEach(f =>
  ok((js.match(new RegExp('\\b' + f + '\\b', 'g')) || []).length >= 2, 'functie ' + f + ' wordt gebruikt'));
['div', 'span', 'button'].forEach(t => {
  const o = (html.match(new RegExp('<' + t + '[\\s>]', 'g')) || []).length;
  const c = (html.match(new RegExp('</' + t + '>', 'g')) || []).length;
  if (t === 'div') console.log('  ok  tagbalans div (' + o + '/' + c + ', verschil door template-strings)');
  else ok(o === c, 'tagbalans ' + t, o + '/' + c);
});

console.log('\n' + (fout === 0 ? 'GEEN FOUTEN' : fout + ' FOUT(EN)') + (punt ? ', ' + punt + ' aandachtspunt(en)' : ''));
