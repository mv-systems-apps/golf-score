// De rekenkern van de handicap, getoetst aan met de hand uitgerekende voorbeelden en aan
// een tweede berekening in hele getallen.
//
// test-afronding.js dekt de afronding van de Handicap Index, de caps en de staffel. Deze
// test dekt de rest: baanhandicap, slagen per hole, Stableford, het dagresultaat voor 18
// en 9 holes met PCC, het voorrang geven aan een vastgesteld dagresultaat, ESR, en de
// Handicap Index van begin tot eind. Regels volgens de Rules of Handicapping, uitgave 2024.
//
// De functies worden rechtstreeks uit golf-score.html geladen: ze zijn zuiver (geen
// scherm, geen opslag), dus dit draait zonder browser. Deel 8 legt drie keuzes vast;
// wie ze wijzigt, ziet het hier.
const fs = require('fs');
const html = fs.readFileSync(process.env.APP || require('path').join(__dirname, '..', 'golf-score.html'), 'utf8');
const js = (html.match(/<script[^>]*>([\s\S]*)<\/script>/) || [])[1];
const pak = naam => { const a = js.indexOf('function ' + naam + '('); if (a < 0) throw new Error(naam + ' niet gevonden'); return js.slice(a, js.indexOf('\n}', a) + 2); };
const NAMEN = ['whsRound', 'distributeChcp', 'indexVoorHoles', 'calcChcpOnafgerond', 'calcChcp', 'stbFor', 'agsFor', 'volleSlagen', 'agsSlagen', 'agsVan', 'sdOnafgerond', 'esrSd', 'esrVerlaging', 'expectedSD9', 'computeSD', 'effectiveSD', 'whsIndexRound', 'whsStaffel',
               'applyHandicapCaps', 'whsVerloop', 'computeEsrAdjustments', 'whsHandicap'];
const F = new Function(NAMEN.map(pak).join('\n') + `; return { ${NAMEN.join(', ')} };`)();

let fout = 0, goed = 0; const eerste = [], perSoort = {};
const gelijk = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const check = (naam, gekregen, verwacht, toon = false) => {
  const ok = gelijk(gekregen, verwacht);
  if (ok) goed++; else { fout++; const soort = naam.split(/[ :]/)[0]; perSoort[soort] = (perSoort[soort] || 0) + 1; if (perSoort[soort] <= 6) eerste.push(`  FOUT ${naam}: ${JSON.stringify(gekregen)} — verwacht ${JSON.stringify(verwacht)}`); }
  if (toon) console.log(`  ${ok ? 'ok  ' : 'FOUT'} ${naam}: ${JSON.stringify(gekregen)}${ok ? '' : ' — verwacht ' + JSON.stringify(verwacht)}`);
};
// Afronden van een breuk teller/noemer (noemer > 0) op een heel getal, ,5 naar boven.
const rond = (teller, noemer) => Math.floor((2 * teller + noemer) / (2 * noemer));
// Park–Miller: blijft binnen de gehele getallen die JavaScript exact kan bewaren.
let zaad = 20241; const rnd = () => (zaad = (zaad * 48271) % 2147483647) / 2147483647;
const kies = (a, b) => a + Math.floor(rnd() * (b - a + 1));

console.log('\n=== 1. BAANHANDICAP ===\n');
// Baanhandicap = Handicap Index × (Slope / 113) + (Course Rating − par); bij 9 holes de halve index.
[
  ['18 holes: index 30,7, SR 120, CR 70,5, par 72 (32,60 − 1,5 = 31,10)', [18, 70.5, 120, 72, 30.7], 31],
  ['9 holes: index 30,7, SR 120, CR 35,0, par 36 (16,30 − 1,0 = 15,30)', [9, 35.0, 120, 36, 30.7], 15],
  ['precies op een half: 10,0 + 0,5 = 10,5 wordt 11', [18, 72.5, 113, 72, 10.0], 11],
  ['plushandicap: −2,0 op een baan met CR gelijk aan par', [18, 72.0, 113, 72, -2.0], -2],
  ['plushandicap precies op een half: −2,5 wordt −2 (naar boven)', [18, 72.5, 113, 72, -3.0], -2],
  ['index 54,0 op een zware baan: 54 × 155/113 + 3,2 = 77,27', [18, 75.2, 155, 72, 54.0], 77],
  ['9 holes, de halve index NIET afgerond (R&A, regel 6.1b): Marks ronde 30-11-2025, index 31,7: 15,85 × 119/113 − 2,2 = 14,49 → 14 (NGF-app: 14)', [9, 33.8, 119, 36, 31.7], 14],
  ['9 holes: Marks ronde 15-12-2025, index 32,1: 16,05 × 115/113 − 1,8 = 14,53 → 15 (NGF-app: 15)', [9, 33.2, 115, 35, 32.1], 15],
  ['9 holes, halve index negatief: −3,3 → −1,65 × 113/113 = −1,65 → −2', [9, 36.0, 113, 36, -3.3], -2],
  ['6 holes (lus): index naar rato, 30,8 × 6/18 = 10,267; × 120/113 = 10,90 → 11', [6, 24.0, 120, 24, 30.8], 11],
  ['12 holes: 30,8 × 12/18 = 20,533; × 130/113 + 0,4 = 24,02 → 24', [12, 48.4, 130, 48, 30.8], 24],
].forEach(([naam, a, v]) => check(naam, F.calcChcp(...a), v, true));
let n1 = 0;
for (let k = 0; k < 60000; k++) {
  // Meestal 9 of 18 holes; soms een lus of korte baan met een ander aantal.
  const keus = rnd(), holes = keus < 0.45 ? 9 : keus < 0.9 ? 18 : kies(3, 17);
  const sr = kies(55, 155), h10 = kies(-60, 540), par = holes === 18 ? kies(66, 74) : kies(3 * holes, 4 * holes + 1), cr10 = par * 10 + kies(-45, 45);
  // In hele getallen. Index × n/18 (bij 18 holes de index, bij 9 de onafgeronde helft:
  // R&A-tekst van regel 6.1b, zoals de NGF rekent) × SR/113 + (CR − par):
  // (h10 × n × SR + (cr10 − par10) × 113 × 18) / (18 × 1130).
  const teller = h10 * holes * sr + (cr10 - par * 10) * 113 * 18;
  check(`baanhandicap ${holes} holes, index ${h10 / 10}, SR ${sr}, CR ${cr10 / 10}, par ${par}`, F.calcChcp(holes, cr10 / 10, sr, par, h10 / 10), rond(teller, 18 * 1130)); n1++;
}
console.log(`  ${n1} willekeurige combinaties nagerekend in hele getallen`);

console.log('\n=== 2. SLAGEN PER HOLE ===\n');
const holesMet = sis => sis.map(si => ({ si }));
const SI9 = [5, 1, 9, 3, 7, 2, 8, 4, 6], SI18 = [7, 15, 1, 11, 5, 17, 3, 13, 9, 8, 16, 2, 12, 6, 18, 4, 14, 10];
check('15 slagen op 9 holes: elke hole 1, en een tweede op SI 1 t/m 6', F.distributeChcp(15, 9, holesMet(SI9)), [2, 2, 1, 2, 1, 2, 1, 2, 2], true);
check('40 slagen op 18 holes: elke hole 2, en een derde op SI 1 t/m 4', F.distributeChcp(40, 18, holesMet(SI18)), SI18.map(si => si <= 4 ? 3 : 2), true);
check('0 slagen: nergens iets', F.distributeChcp(0, 9, holesMet(SI9)), Array(9).fill(0), true);
check('plushandicap −3 op 18 holes: een slag inleveren op de drie makkelijkste holes (SI 16, 17, 18)', F.distributeChcp(-3, 18, holesMet(SI18)), SI18.map(si => si >= 16 ? -1 : 0), true);
let n2 = 0;
for (let k = 0; k < 20000; k++) {
  const n = rnd() < 0.5 ? 9 : 18, chcp = kies(-8, 60);
  const sis = Array.from({ length: n }, (_, i) => i + 1).sort(() => rnd() - 0.5);
  const uit = F.distributeChcp(chcp, n, holesMet(sis));
  // Tweede berekening: vaste slagen per hole, de rest naar de moeilijkste (bij plus: de makkelijkste) holes.
  const basis = Math.trunc(chcp / n), rest = Math.abs(chcp % n);
  const verwacht = sis.map(si => basis + (chcp > 0 ? (si <= rest ? 1 : 0) : (si > n - rest ? -1 : 0)));
  check(`slagen: ${chcp} over ${n} holes`, uit, verwacht);
  check(`slagen: som is de baanhandicap (${chcp} over ${n})`, uit.reduce((s, x) => s + x, 0), chcp); n2++;
}
console.log(`  ${n2} willekeurige verdelingen nagerekend; de som is steeds de baanhandicap`);

console.log('\n=== 3. STABLEFORD EN DE HOOGSTE SCORE PER HOLE ===\n');
[ // [omschrijving, hole, punten, aangepaste score]
  ['par 4 met 1 slag, 5 gespeeld: netto par',            { par: 4, phcp: 1, score: 5 }, 2, 5],
  ['par 4 met 1 slag, 4 gespeeld: netto birdie',         { par: 4, phcp: 1, score: 4 }, 3, 4],
  ['par 4 met 1 slag, 7 gespeeld: netto dubbel bogey',   { par: 4, phcp: 1, score: 7 }, 0, 7],
  ['par 4 met 1 slag, 9 gespeeld: telt als 7',           { par: 4, phcp: 1, score: 9 }, 0, 7],
  ['par 3 met 2 slagen, 1 gespeeld',                     { par: 3, phcp: 2, score: 1 }, 6, 1],
  ['par 5 zonder slagen, 5 gespeeld',                    { par: 5, phcp: 0, score: 5 }, 2, 5],
  ['plushandicap: par 4 met −1, 3 gespeeld is netto par', { par: 4, phcp: -1, score: 3 }, 2, 3],
  ['plushandicap: par 4 met −1, 6 gespeeld telt als 5',  { par: 4, phcp: -1, score: 6 }, 0, 5],
  ['niet gespeeld',                                      { par: 4, phcp: 1, score: null }, 0, 0],
].forEach(([naam, h, stb, ags]) => check(naam + ' → punten, aangepaste score', [F.stbFor(h), F.agsFor(h)], [stb, ags], true));

console.log('\n=== 4. DAGRESULTAAT ===\n');
// Dagresultaat = (113 / Slope) × (aangepaste bruto score − Course Rating − PCC).
// Bij 9 holes komt daar de verwachte score voor de andere negen bij: 0,52 × Handicap Index + 1,2.
const ronde = (n, score, extra) => Object.assign({ holes: Array.from({ length: n }, () => ({ par: 4, phcp: 9, score })), CR: n === 18 ? 70.5 : 35.0, SR: 120, hcp: 30.7, pcc: 0 }, extra);
const met = (n, totaal, extra) => { const r = ronde(n, Math.floor(totaal / n), extra); for (let i = 0; i < totaal % n; i++) r.holes[i].score++; return r; };
[
  ['18 holes, 95 slagen: 113/120 × 24,5 = 23,07',                    met(18, 95), { value: 23.1, approx: false }],
  ['18 holes, 95 slagen, PCC +1: 113/120 × 23,5 = 22,13',            met(18, 95, { pcc: 1 }), { value: 22.1, approx: false }],
  ['18 holes, 95 slagen, PCC −1: 113/120 × 25,5 = 24,01',            met(18, 95, { pcc: -1 }), { value: 24, approx: false }],
  ['18 holes, 95 slagen, PCC +3',                                    met(18, 95, { pcc: 3 }), { value: 20.2, approx: false }],
  ['18 holes onder de CR: 68 slagen geeft een negatief dagresultaat', met(18, 68), { value: -2.4, approx: false }],
  ['9 holes, 50 slagen, index 30,7: 14,125 + 15,964 + 1,2 = 31,29',  met(9, 50), { value: 31.3, approx: true }],
  ['9 holes, 50 slagen, PCC +0,5: de helft telt (NGF: ½ × PCC), 31,289 − 0,235 = 31,05', met(9, 50, { pcc: 0.5 }), { value: 31.1, approx: true }],
  ['9 holes zonder handicap: geen dagresultaat',                     met(9, 50, { hcp: null }), null],
  ['een hole niet gespeeld: geen dagresultaat',                      (() => { const r = met(18, 95); r.holes[17].score = null; return r; })(), null],
  ['een lus van 6 holes: geen dagresultaat',                         met(6, 30), null],
  ['zonder slope rating: geen dagresultaat',                         met(18, 95, { SR: 0 }), null],
].forEach(([naam, r, v]) => check(naam, F.computeSD(r), v, true));
let n4 = 0;
for (let k = 0; k < 60000; k++) {
  const n = rnd() < 0.5 ? 9 : 18, sr = kies(55, 155), cr10 = (n === 9 ? 350 : 705) + kies(-60, 60), totaal = (n === 9 ? 36 : 72) + kies(-6, 60);
  const pcc10 = n === 9 ? [-5, 0, 5, 10, 15][kies(0, 4)] : [-10, 0, 10, 20, 30][kies(0, 4)], h10 = kies(-40, 540);
  const r = met(n, totaal, { CR: cr10 / 10, SR: sr, pcc: pcc10 / 10, hcp: h10 / 10 });
  r.holes.forEach(h => { h.phcp = 40; });                       // ruim genoeg: de aangepaste score is dan de score zelf
  // Bij 9 holes telt de helft van de PCC (NGF, Wegwijs in Handicapping 2024: "½*PCC").
  const kern = 113 * (totaal * 10 - cr10 - pcc10);              // tienden × SR
  const kern2 = 113 * (totaal * 20 - cr10 * 2 - pcc10);         // twintigsten × SR, met de halve PCC
  const verwacht = n === 18 ? rond(kern, sr) / 10 : rond(kern2 * 50 + (52 * h10 + 1200) * sr, sr * 100) / 10;
  check(`dagresultaat ${n} holes: ${totaal} slagen, CR ${cr10 / 10}, SR ${sr}, PCC ${pcc10 / 10}, index ${h10 / 10}`, F.computeSD(r).value, verwacht); n4++;
}
console.log(`  ${n4} willekeurige rondes nagerekend in hele getallen`);

console.log('\n=== 5. EEN VASTGESTELD DAGRESULTAAT GAAT VOOR ===\n');
check('vastgesteld 28,4 wint van het berekende 23,1',     F.effectiveSD(met(18, 95, { sdFinal: 28.4 })), { value: 28.4, approx: false, manual: true }, true);
check('vastgesteld als tekst "28.4"',                     F.effectiveSD(met(18, 95, { sdFinal: '28.4' })), { value: 28.4, approx: false, manual: true }, true);
check('vastgesteld 0 telt ook als vastgesteld',           F.effectiveSD(met(18, 95, { sdFinal: 0 })), { value: 0, approx: false, manual: true }, true);
check('vastgesteld −1,5 (onder de CR)',                   F.effectiveSD(met(18, 95, { sdFinal: -1.5 })), { value: -1.5, approx: false, manual: true }, true);
check('niet vastgesteld: het berekende, als benadering bij 9 holes', F.effectiveSD(met(9, 50, { sdFinal: null })), { value: 31.3, approx: true, manual: false }, true);
check('leeg vastgesteld: het berekende',                  F.effectiveSD(met(18, 95, { sdFinal: '' })), { value: 23.1, approx: false, manual: false }, true);
check('vastgesteld op een onvolledige ronde blijft staan', F.effectiveSD((() => { const r = met(18, 95, { sdFinal: 30 }); r.holes[0].score = null; return r; })()), { value: 30, approx: false, manual: true }, true);

console.log('\n=== 6. UITZONDERLIJKE SCORE (ESR) ===\n');
// Een dagresultaat dat 7,0 tot en met 9,9 onder de Handicap Index ligt geeft −1,0, vanaf
// 10,0 geeft het −2,0, op elk van de laatste 20 dagresultaten (de uitzonderlijke ronde zelf incl.).
const reeks = sds => sds.map((sd, i) => ({ id: i + 1, sd, t: i }));
const esr = sds => { const m = F.computeEsrAdjustments(reeks(sds)); return sds.map((_, i) => m.get(i + 1)); };
const twintig = Array(20).fill(20.0);
check('20 × 20,0 en dan 13,1 (6,9 eronder): geen verlaging', esr([...twintig, 13.1]), Array(21).fill(0), true);
check('20 × 20,0 en dan 13,0 (7,0 eronder): −1 op de laatste 20, de oudste niet', esr([...twintig, 13.0]), [0, ...Array(20).fill(-1)], true);
check('20 × 20,0 en dan 10,1 (9,9 eronder): −1', esr([...twintig, 10.1])[20], -1, true);
check('20 × 20,0 en dan 10,0 (10,0 eronder): −2 op de laatste 20', esr([...twintig, 10.0]), [0, ...Array(20).fill(-2)], true);
check('twee uitzonderlijke rondes na elkaar stapelen', (() => { const a = esr([...twintig, 13.0, 11.0]); return [a[1], a[2], a[20], a[21]]; })(), [-1, -2, -2, -1], true);
check('de verlaging dooft uit: 20 rondes later draagt geen ronde hem nog in het venster', (() => { const sds = [...twintig, 13.0, ...Array(20).fill(20.0)]; const a = esr(sds); return a.slice(21); })(), Array(20).fill(0), true);
check('de eerste ronde kan niet uitzonderlijk zijn (er is nog geen handicap)', esr([5.0]), [0], true);
check('per ronde bijgehouden geeft dezelfde uitkomst als achteraf', (() => { const sds = Array.from({ length: 60 }, () => kies(80, 360) / 10); const r = reeks(sds); const m = F.computeEsrAdjustments(r);
  const stap = F.whsVerloop(r).stappen; return stap.length === 60 && stap[59].value === F.whsVerloop(r.slice(0, 60)).stappen[59].value && m.get(60) === F.whsVerloop(r).adj.get(60); })(), true, true);
// De Handicap Index na een uitzonderlijke ronde: beste 8 van de laatste 20, elk 1,0 lager.
const rondeMet = (id, sd) => ({ id, date: `2026-${String(1 + Math.floor((id - 1) / 28)).padStart(2, '0')}-${String(1 + (id - 1) % 28).padStart(2, '0')}`, sdFinal: sd, holes: [] });
const na = sds => { const alle = sds.map((sd, i) => rondeMet(i + 1, sd)); const m = F.computeEsrAdjustments(reeks(sds)); return F.whsHandicap(alle.slice(-20), null, m); };
check('index na 20 × 20,0 en 13,0: (12,0 + 7 × 19,0) / 8 = 18,125 wordt 18,1', (r => [r.value, r.rawValueNoEsr, r.esrApplied])(na([...twintig, 13.0])), [18.1, 19.1, true], true);
check('zonder uitzonderlijke ronde: 20 × 20,0 en 13,1 geeft (13,1 + 7 × 20,0) / 8 = 19,1', (r => [r.value, r.esrApplied])(na([...twintig, 13.1])), [19.1, false], true);

console.log('\n=== 7. HANDICAP INDEX VAN BEGIN TOT EIND ===\n');
let n7 = 0;
for (let aantal = 1; aantal <= 20; aantal++) {
  for (let k = 0; k < 300; k++) {
    const t10 = Array.from({ length: aantal }, () => kies(-40, 540));
    const st = F.whsStaffel(aantal);
    const laagste = [...t10].sort((a, b) => a - b).slice(0, st.count);
    const som = laagste.reduce((s, x) => s + x, 0);
    const verwacht = rond(som + Math.round(st.adj * 10) * st.count, st.count) / 10;
    const r = F.whsHandicap(t10.map((x, i) => rondeMet(i + 1, x / 10)));
    check(`index uit ${aantal} rondes: ${t10.map(x => x / 10).join(' ')}`, [r.value, r.usedIds.size], [Math.min(verwacht, 54), st.count]); n7++;
  }
}
console.log(`  ${n7} reeksen van 1 t/m 20 rondes nagerekend: de laagste volgens de staffel, gemiddeld, bijtelling erbij`);
const gelijkspel = [20, 15, 15, 15, 30, 31, 32].map((sd, i) => rondeMet(i + 1, sd));
check('bij gelijke dagresultaten tellen de oudste rondes mee', [...F.whsHandicap(gelijkspel).usedIds].sort(), [2, 3], true);
const hoog = Array.from({ length: 20 }, (_, i) => rondeMet(i + 1, i < 8 ? 30 : 33 + (i % 3)));
check('soft cap: 30,0 berekend bij Low HI 24,0 wordt 27,0 + 1,5 = 28,5', (r => [r.rawValue, r.value, r.capType, r.capped])(F.whsHandicap(hoog, 24.0)), [30, 28.5, 'soft', true], true);
check('hard cap: 30,0 berekend bij Low HI 20,0 wordt 25,0', (r => [r.value, r.capType])(F.whsHandicap(hoog, 20.0)), [25, 'hard'], true);
check('geen cap binnen 3,0: 30,0 bij Low HI 27,0 blijft 30,0', (r => [r.value, r.capType, r.capped])(F.whsHandicap(hoog, 27.0)), [30, null, false], true);
check('nooit boven 54,0', F.whsHandicap(Array.from({ length: 20 }, (_, i) => rondeMet(i + 1, 58))).value, 54, true);
check('plushandicap: 20 × −2,3 geeft −2,3', F.whsHandicap(Array.from({ length: 20 }, (_, i) => rondeMet(i + 1, -2.3))).value, -2.3, true);
check('zonder rondes: geen handicap', F.whsHandicap([]), null, true);

console.log('\n=== 8. VASTGELEGD EN BEVESTIGD ===\n');
// Deze leggen vast wat de app NU doet, zodat een wijziging opvalt. Alle drie bevestigd:
// de staffel bij 1–2 rondes door de NGF-tabel (Wegwijs in Handicapping 2024), ESR tegen
// de index na de cap (13527DA-142), de halve PCC bij 9 holes (13527DA-144).
check('1 of 2 rondes geven al een handicap: laagste dagresultaat min 2,0 (NGF-tabel; de WHS-tabel begint bij 3)',
  [F.whsHandicap([rondeMet(1, 30)]).value, F.whsHandicap([rondeMet(1, 30), rondeMet(2, 26)]).value], [28, 24], true);
// Sinds 13527DA-142 bevestigd en aangepast (regel 5.9, 2024: "Handicap Index in effect when
// the round was played"): ESR vergelijkt met de index die gold, dus NA de cap. Hier: Low HI
// 18,0 (na de eerste ronde), ongecapt 27,0, met hard cap 23,0; 23,0 − 19,5 = 3,5, geen
// verlaging. Tot 13527DA-141 was het 27,0 − 19,5 = 7,5 en dus −1.
check('ESR vergelijkt met de handicap NA de caps: 23,0 − 19,5 = 3,5, geen verlaging (vóór de cap zou het 27,0 − 19,5 = 7,5 zijn)',
  esr([...Array(20).fill(20.0), ...Array(20).fill(27.0), 19.5])[40], 0, true);
// Bevestigd in 13527DA-144: bij 9 holes telt de helft van de PCC die de NGF-app toont
// (NGF: "½*PCC"; nagerekend op Marks rondes). Tot 13527DA-143 ging de volle waarde eraf.
check('PCC bij 9 holes: de helft telt (de app begrenst de invoer op −0,5 t/m 1,5, zoals de NGF-app die toont)',
  [F.computeSD(met(9, 50, { pcc: 1 })).value, F.computeSD(met(9, 50)).value], [30.8, 31.3], true);

eerste.forEach(r => console.log(r));
console.log(`\n${goed} goed, ${fout} fout`);
console.log(fout ? `\n${fout} FOUT(EN)` : '\nGEEN FOUTEN');
process.exit(fout ? 1 : 0);
