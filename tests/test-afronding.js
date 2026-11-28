// Afronden van de Handicap Index en de caps, getoetst aan rekenen met hele getallen.
//
// De app rekent met kommagetallen. Een gemiddelde als 12,65 bewaart de computer als
// 12,649999…, en dat werd tot 13527DA-119 naar 12,6 afgerond in plaats van 12,7. De
// Rules of Handicapping (uitgave 2024, regel 5.2) ronden de Handicap Index af op één
// decimaal; een exacte ,x5 gaat hier naar boven (richting plus), ook bij plushandicaps.
//
// Deze test rekent elke uitkomst na in hele tienden en honderdsten, waar geen
// afrondruis bestaat, en vergelijkt dat met wat de functies van de app geven.
const fs = require('fs');
const html = fs.readFileSync(process.env.APP || require('path').join(__dirname, '..', 'golf-score.html'), 'utf8');
const js = (html.match(/<script[^>]*>([\s\S]*)<\/script>/) || [])[1];
const pak = naam => { const a = js.indexOf('function ' + naam + '('); if (a < 0) throw new Error(naam + ' niet gevonden'); return js.slice(a, js.indexOf('\n}', a) + 2); };
const { whsIndexRound, whsStaffel, applyHandicapCaps } = new Function(
  pak('whsIndexRound') + pak('whsStaffel') + pak('applyHandicapCaps') + '; return { whsIndexRound, whsStaffel, applyHandicapCaps };')();

let fout = 0, goed = 0;
const eerste = [];
const check = (naam, gekregen, verwacht) => {
  if (Object.is(gekregen, verwacht) || gekregen === verwacht) { goed++; return; }
  fout++; if (eerste.length < 12) eerste.push(`  FOUT ${naam}: ${gekregen} — verwacht ${verwacht}`);
};
// ,x5 naar boven (richting plus): in hele tienden is dat floor(x + 0,5).
const rondTienden = (teller, noemer) => Math.floor((2 * teller + noemer) / (2 * noemer));

console.log('\n=== 1. DE VOORBEELDEN ===\n');
const voorbeelden = [
  ['twee laagste 10,6 en 14,7 (12,65)',            [10.6, 14.7], 0, 12.7],
  ['acht laagste, gemiddeld 14,85',                [10.2, 10.7, 12.9, 13.2, 16.6, 17.5, 17.8, 19.9], 0, 14.9],
  ['plushandicap −4,9 en −4,2 min 1,0 (−5,55)',    [-4.9, -4.2], -1.0, -5.5],
  ['gewoon geval 20,0 en 21,0',                    [20.0, 21.0], 0, 20.5],
  ['drie rondes: laagste 31,4 min 2,0',            [31.4], -2.0, 29.4],
];
voorbeelden.forEach(([naam, sds, adj, verwacht]) => {
  const uit = whsIndexRound(sds.reduce((s, x) => s + x, 0) / sds.length + adj);
  const ok = uit === verwacht; console.log(`  ${ok ? 'ok  ' : 'FOUT'} ${naam}: ${uit}${ok ? '' : ' — verwacht ' + verwacht}`); ok ? goed++ : fout++;
});

console.log('\n=== 2. ELK AANTAL RONDES, WILLEKEURIGE DAGRESULTATEN ===\n');
// Zelfde bewerking als de app: de laagste N optellen als kommagetallen, delen, bijtelling erbij.
// Park–Miller: blijft binnen de gehele getallen die JavaScript exact kan bewaren.
let zaad = 20241; const rnd = () => (zaad = (zaad * 48271) % 2147483647) / 2147483647;
let halven = 0, n2 = 0;
for (let rondes = 1; rondes <= 20; rondes++) {
  const st = whsStaffel(rondes);
  for (let k = 0; k < 4000; k++) {
    const tienden = Array.from({ length: st.count }, () => Math.round(rnd() * 600) - 60);   // −6,0 t/m 54,0
    const som = tienden.reduce((s, x) => s + x, 0);
    const exact = rondTienden(som + Math.round(st.adj * 10) * st.count, st.count) / 10;
    if ((2 * som) % st.count === 0 && ((2 * som) / st.count) % 2 !== 0) halven++;
    const app = whsIndexRound(tienden.map(t => t / 10).reduce((s, x) => s + x, 0) / st.count + st.adj);
    check(`${rondes} rondes, laagste ${tienden.map(t => t / 10).join(' ')}`, app, exact); n2++;
  }
}
console.log(`  ${n2} gevallen nagerekend, waarvan ${halven} precies op ,x5`);

console.log('\n=== 3. DE CAPS, VOOR ELKE COMBINATIE VAN HANDICAP EN LOW HI ===\n');
let n3 = 0;
for (let raw = -60; raw <= 600; raw += 1) {            // in tienden
  for (let low = -60; low <= 540; low += 3) {
    const uit = applyHandicapCaps(raw / 10, low / 10);
    const stijging = raw - low;                         // tienden, exact
    let waarde, soort = null;
    if (stijging <= 30) waarde = Math.min(raw, 540);
    else {
      const honderdsten = low * 10 + 300 + (stijging - 30) * 5;       // soft cap, exact in honderdsten
      const hard = low * 10 + 500;
      soort = honderdsten > hard ? 'hard' : 'soft';
      waarde = rondTienden(Math.min(honderdsten, hard, 5400), 10);
    }
    check(`cap raw ${raw / 10} low ${low / 10}: waarde`, uit.value, waarde / 10);
    check(`cap raw ${raw / 10} low ${low / 10}: soort`, uit.type, soort); n3++;
  }
}
console.log(`  ${n3} combinaties nagerekend`);

console.log('\n=== 4. DE STAFFEL ===\n');
const tabel = [[1,1,-2],[2,1,-2],[3,1,-2],[4,1,-1],[5,1,0],[6,2,-1],[7,2,0],[8,2,0],[9,3,0],[10,3,0],[11,3,0],[12,4,0],[13,4,0],[14,4,0],[15,5,0],[16,5,0],[17,6,0],[18,6,0],[19,7,0],[20,8,0],[21,8,0],[40,8,0]];
tabel.forEach(([n, aantal, bij]) => { const s = whsStaffel(n); check(`staffel ${n} rondes`, `${s.count}/${s.adj}`, `${aantal}/${bij}`); });
console.log(`  ${tabel.length} regels van de staffel nagelopen (1 en 2 rondes volgens de NGF-tabel)`);

eerste.forEach(r => console.log(r));
console.log(`\n${goed} goed, ${fout} fout`);
console.log(fout ? `\n${fout} FOUT(EN)` : '\nGEEN FOUTEN');
process.exit(fout ? 1 : 0);
