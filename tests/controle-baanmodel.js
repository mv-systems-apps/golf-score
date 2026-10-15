/**
 * Bewaakt het baanmodel: par en SI horen bij de TEE, niet bij de baan.
 *
 * Een baan bewaart alleen `holeIds`; elke tee heeft een eigen `holes: [{par, si}]`.
 * Een losse aanpassing kan daar zomaar weer `course.holes` of `teeData.PAR` in
 * schuiven — dat blijft onopgemerkt zolang die tak nooit wordt geraakt, en levert dan
 * ineens rondes op met de verkeerde par. Deze controle is puur tekstueel en kost
 * niets, maar vangt precies dat geval.
 */
const fs = require('fs');
const path = require('path');

const APP = process.env.APP ||
  path.join(path.dirname(path.dirname(path.resolve(__filename))), 'golf-score.html');
const html = fs.readFileSync(APP, 'utf8');

let fout = 0;
const ok = (goed, tekst, detail) => {
  if (!goed) fout++;
  console.log((goed ? '  ok  ' : ' FOUT ') + tekst + (detail ? ' → ' + detail : ''));
};

// Alleen de code beoordelen: commentaar en tekst voor de gebruiker mogen de oude
// begrippen gewoon noemen (bijvoorbeeld in een uitleg over wat er veranderd is).
const codeRegels = html.split('\n').map((regel, i) => ({ nr: i + 1, tekst: regel }))
  .filter(r => !/^\s*(\/\/|\*|\/\*)/.test(r.tekst));

const zoek = (patroon, uitzondering) => codeRegels
  .filter(r => patroon.test(r.tekst))
  .filter(r => !(uitzondering && uitzondering.test(r.tekst)))
  .map(r => r.nr + ': ' + r.tekst.trim().slice(0, 70));

console.log('=== 1. GEEN HOLES OP BAANNIVEAU ===');
// `course.holes`, `data.courses[x].holes`, `co.holes` — de oude vorm.
const baanHoles = zoek(
  /\b(course|co|baan|data\.courses\[[^\]]+\]|courses\[[^\]]+\])\s*[?.]?\.holes\b/,
  // teeData.holes en row._holes zijn juist WEL de nieuwe vorm
  /teeData|_holes|\.holeIds/
);
ok(baanHoles.length === 0, 'geen enkele verwijzing naar holes op de baan',
   baanHoles.join(' | '));

console.log('\n=== 2. GEEN OPGESLAGEN PAR PER TEE ===');
// PAR was het opgeslagen teetotaal; dat is nu altijd de som van de eigen holes.
const teePar = zoek(/\b(teeData2?|vals|v)\s*[?.]?\.PAR\b/);
ok(teePar.length === 0, 'geen tee die een opgeslagen PAR uitleest', teePar.join(' | '));

// Een RONDE bewaart zijn par-totaal wel (die kopie hoort er juist te zijn, zodat
// statistieken niet meebewegen als de baan later verandert). Verboden is alleen een PAR
// die bij een TEE wordt weggeschreven: dat is het veld dat is afgeschaft.
const parBijTee = zoek(/tees?\[[^\]]+\]\[[^\]]+\]\s*=\s*\{[^}]*\bPAR\b/)
  .concat(zoek(/\bPAR\b\s*:[^,}]+,[^}]*\bholes\s*:/))
  .concat(zoek(/\{\s*PAR\s*:[^}]*\bCR\b[^}]*\bSR\b[^}]*\}/));
ok(parBijTee.length === 0, 'geen PAR die als teeveld wordt weggeschreven',
   parBijTee.join(' | '));

console.log('\n=== 3. DE HULPFUNCTIES BESTAAN EN WORDEN GEBRUIKT ===');
[
  ['teePar',          'par-totaal van een tee'],
  ['firstTeeOf',      'eerste tee voor baanbrede weetjes'],
  ['buildRoundHoles', 'ronde-holes uit baan + tee'],
  ['leesSi',          'slagindex uit de editor lezen'],
].forEach(([naam, wat]) => {
  const gedefinieerd = new RegExp('function\\s+' + naam + '\\s*\\(').test(html);
  const aanroepen = (html.match(new RegExp('\\b' + naam + '\\s*\\(', 'g')) || []).length;
  ok(gedefinieerd && aanroepen > 1, wat + ' (' + naam + ')',
     gedefinieerd ? aanroepen + ' aanroepen' : 'ONTBREEKT');
});

console.log('\n=== 4. ÉÉN PLEK WAAR EEN RONDE-HOLE ONTSTAAT ===');
// Alles na het starten leest uit de ronde zelf. Ontstaat er elders tóch een ronde-hole
// uit baangegevens, dan kan die de par van een andere tee krijgen.
const bouwers = (html.match(/buildRoundHoles\s*\(/g) || []).length;
ok(bouwers === 3, 'buildRoundHoles: 1 definitie + 2 aanroepen (speler 1 en 2)',
   bouwers + ' voorkomens');

console.log('\n=== 5. VALIDATIE DEKT BEIDE KANTEN ===');
[
  ['validateCourseInput',      'de baaneditor'],
  ['validateImportedClubData', 'het importeren'],
].forEach(([naam, wat]) => {
  const blok = html.slice(html.indexOf('function ' + naam));
  const eind = blok.indexOf('\nfunction ');
  const body = blok.slice(0, eind > 0 ? eind : 4000);
  ok(/holes/.test(body) && /si/i.test(body) && /par/i.test(body),
     wat + ' controleert par én SI per tee (' + naam + ')');
});

console.log('\n=== 6. GEEN TERUGVAL OP EEN GEDEELDE HOLELIJST ===');
// Een terugval als `teeData.holes || course.holes` zou twee modellen naast elkaar
// zetten — precies wat bij het ontwerp bewust is afgewezen.
const terugval = zoek(/\.holes\s*\|\|\s*(course|co)\b/);
ok(terugval.length === 0, 'geen terugval van tee-holes op baan-holes',
   terugval.join(' | '));

console.log('\n' + (fout ? fout + ' FOUT(EN)' : 'GEEN FOUTEN'));
process.exit(fout ? 1 : 0);
