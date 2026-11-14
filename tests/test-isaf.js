const fs = require('fs');
const html = fs.readFileSync(process.env.APP || require('path').join(__dirname, '..', 'golf-score.html'), 'utf8');
const js = (html.match(/<script[^>]*>([\s\S]*)<\/script>/) || [])[1];
const start = js.indexOf('function isRondeAf');
const eind = js.indexOf('\n}', start) + 2;
const gespeeldeHolesCode = js.slice(js.indexOf('function gespeeldeHoles'), js.indexOf('}', js.indexOf('function gespeeldeHoles')) + 1);
const isRondeAf = new Function(gespeeldeHolesCode + '\n' + js.slice(start, eind) + '; return isRondeAf;')();
// de oude formulering, ter vergelijking
const oud = r => (r.holes || []).length > 0 && (r.holes || []).every(h => h.score !== null);

const gevallen = [
  ['afgeronde ronde',              { playedCount: 9, holesCount: 9, holes: Array(9).fill({score: 5}) }, true],
  ['halve ronde',                  { playedCount: 4, holesCount: 9, holes: [...Array(4).fill({score: 5}), ...Array(5).fill({score: null})] }, false],
  ['geplande ronde',               { playedCount: 0, holesCount: 9, holes: Array(9).fill({score: null}) }, false],
  ['oude backup zonder tellers',   { holes: Array(9).fill({score: 5}) }, true],
  ['oude backup, half gespeeld',   { holes: [...Array(4).fill({score: 5}), ...Array(5).fill({score: null})] }, false],
  ['lege holes-lijst',             { playedCount: 0, holesCount: 0, holes: [] }, false],
  ['holes ontbreekt',              { playedCount: 0, holesCount: 9 }, false],
  ['ronde is null',                null, false],
  ['ronde zonder velden',          {}, false],
  // 18 holes waarvan er 9 zijn ingevuld — nu geteld uit de scores zelf
  ['18 holes, 9 gespeeld',         { holesCount: 18, holes: [...Array(9).fill({score: 5}), ...Array(9).fill({score: null})] }, false],
];

let fout = 0;
console.log('  geval                          nieuw   oud     verwacht');
gevallen.forEach(([naam, r, verwacht]) => {
  const n = isRondeAf(r);
  let o; try { o = oud(r); } catch (e) { o = 'fout'; }
  const goed = n === verwacht;
  if (!goed) fout++;
  console.log((goed ? '  ok   ' : ' FOUT  ') + naam.padEnd(30) + String(n).padEnd(8) + String(o).padEnd(8) + verwacht);
});
console.log('\n' + (fout ? fout + ' FOUT(EN)' : 'alle ' + gevallen.length + ' gevallen goed'));
console.log('\nLet op de laatste twee regels: bij "ronde is null" en "18 holes, 9 gespeeld"');
console.log('geeft de OUDE formulering een ander (fout) antwoord — de nieuwe functie is daar strenger.');
