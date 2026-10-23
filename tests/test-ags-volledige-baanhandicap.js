// De aangepaste bruto score (AGS) rekent met de VOLLEDIGE course handicap.
//
// Rules of Handicapping 2024, regel 3.1b: de hoogste holescore is een net double bogey,
// par + 2 + de handicapslagen op die hole, en "The player's full, unrestricted Course
// Handicap should be used for all applications of net double bogey adjustments."
// Een wedstrijdpercentage of een met +/− bijgestelde baanhandicap telt dus NIET voor de
// AGS; die geldt alleen voor de wedstrijd (Stableford, netto). Verder: "Where a Course
// Handicap is calculated at more than 54 and a player receives 4 or more strokes on a
// hole", dan is de hoogste holescore par + 5.
//
// Tot 13527DA-13D gebruikte de app de gespeelde slagen (phcp). Met 85% kwam het
// dagresultaat daardoor te gunstig uit.
//
// Deel 1: met de hand uitgerekende voorbeelden. Deel 2: 40.000 willekeurige rondes
// nagerekend met een eigen berekening in hele getallen (los van de app). Deel 3: rondes
// zonder bijstelling geven precies hetzelfde als voorheen.
const fs = require('fs');
const html = fs.readFileSync(process.env.APP || require('path').join(__dirname, '..', 'golf-score.html'), 'utf8');
const js = (html.match(/<script[^>]*>([\s\S]*)<\/script>/) || [])[1];
const pak = naam => { const a = js.indexOf('function ' + naam + '('); if (a < 0) return ''; return js.slice(a, js.indexOf('\n}', a) + 2); };
const NAMEN = ['whsRound', 'distributeChcp', 'whsIndexRound', 'indexVoorHoles', 'calcChcpOnafgerond', 'calcChcp', 'agsFor', 'volleSlagen', 'agsSlagen', 'agsVan', 'expectedSD9', 'sdOnafgerond', 'computeSD'];
const F = new Function(NAMEN.map(pak).join('\n') + `; return { ${NAMEN.map(n => `${n}: typeof ${n} === 'function' ? ${n} : null`).join(', ')} };`)();

// Een oudere versie zonder agsSlagen rekende met de gespeelde slagen: zo naspelen, zodat
// de test daar faalt op de uitkomst in plaats van te struikelen.
if (!F.agsSlagen) F.agsSlagen = r => r.holes.map(h => h.phcp);
let fout = 0, goed = 0; const eerste = [];
const gelijk = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const check = (naam, gekregen, verwacht, toon = false) => {
  const ok = gelijk(gekregen, verwacht);
  if (ok) goed++; else { fout++; if (eerste.length < 12) eerste.push(`  FOUT ${naam}: ${JSON.stringify(gekregen)} — verwacht ${JSON.stringify(verwacht)}`); }
  if (toon) console.log(`  ${ok ? 'ok  ' : 'FOUT'} ${naam}: ${JSON.stringify(gekregen)}${ok ? '' : ' — verwacht ' + JSON.stringify(verwacht)}`);
};
const rond = (teller, noemer) => Math.floor((2 * teller + noemer) / (2 * noemer));   // ,5 naar boven

// ── Eigen berekening, los van de app ──────────────────────────────────────
// Course handicap in tienden: index × SR/113 + (CR − par); bij 9 holes de halve index,
// niet afgerond (R&A-tekst van regel 6.1b, zoals de NGF rekent).
const chEigen = (n, cr10, sr, par, h10) => rond(n === 9 ? sr * h10 * 5 + (cr10 - par * 10) * 1130 : sr * h10 * 10 + (cr10 - par * 10) * 1130, 11300);
// Slagen per hole: iedereen ch div n, en de rest op de moeilijkste holes (laagste SI);
// bij een plushandicap slagen terug op de makkelijkste holes (hoogste SI).
function slagenEigen(ch, sis) {
  const n = sis.length, uit = Array(n).fill(0);
  const volgorde = sis.map((si, i) => [si, i]).sort((a, b) => ch >= 0 ? a[0] - b[0] : b[0] - a[0]).map(x => x[1]);
  const basis = ch >= 0 ? Math.floor(ch / n) : -Math.floor(-ch / n), rest = Math.abs(ch) % n;
  for (let i = 0; i < n; i++) uit[i] = basis;
  for (let k = 0; k < rest; k++) uit[volgorde[k]] += ch >= 0 ? 1 : -1;
  return ch > 54 ? uit.map(s => Math.min(s, 3)) : uit;
}
const agsEigen = (pars, scores, slagen) => scores.reduce((t, s, i) => t + Math.min(s, pars[i] + 2 + slagen[i]), 0);
// Dagresultaat 18 holes in tienden: 113 / SR × (AGS − CR − PCC), op tienden.
const sd18Eigen = (ags, cr10, sr, pcc10) => rond(113 * (ags * 10 - cr10 - pcc10), sr) / 10;

const ronde = (pars, sis, scores, phcps, extra) => Object.assign({ holes: pars.map((p, i) => ({ par: p, si: sis[i], phcp: phcps[i], score: scores[i] })) }, extra);
const SI18 = [7, 15, 1, 11, 5, 17, 3, 13, 9, 8, 16, 2, 12, 6, 18, 4, 14, 10];
const PAR18 = [4, 4, 4, 3, 5, 4, 4, 3, 5, 4, 4, 3, 5, 4, 4, 4, 3, 5];   // 72
const SI_ORDE = Array.from({ length: 18 }, (_, i) => i + 1);

console.log('\n=== 1. MET DE HAND UITGEREKEND ===\n');
{
  // HI 20, CR 72,0, SR 130, par 72 (alle holes par 4): CH = 20 × 130/113 = 23,01 → 23.
  // 85% → speelhandicap 20 (zo verdeelt de app phcp). Zestien holes een 5; op SI 4 en 5 een 8.
  // Volledige CH 23: elke hole 1 slag, SI 1–5 een tweede → net double bogey op SI 4 en 5 = 8.
  // AGS = 16 × 5 + 8 + 8 = 96 → (96 − 72) × 113/130 = 20,86 → 20,9.
  // Met de speelhandicap 20 (SI 1–2 een tweede slag) werd het 7 + 7 → 94 → 19,1 (fout).
  const pars = Array(18).fill(4), sis = SI_ORDE, scores = sis.map(si => si === 4 || si === 5 ? 8 : 5);
  const r = ronde(pars, sis, scores, F.distributeChcp(20, 18, sis.map(si => ({ si }))), { CR: 72.0, SR: 130, hcp: 20, pcc: 0 });
  check('85%: de AGS-slagen volgen de volledige course handicap 23', F.agsSlagen(r), sis.map(si => si <= 5 ? 2 : 1), true);
  check('85%: dagresultaat 20,9 (niet 19,1)', F.computeSD(r), { value: 20.9, approx: false }, true);
}
{
  // Met + bijgesteld naar 26 (boven de CH van 23): op SI 6–8 speelt hij met 2 slagen,
  // maar de net double bogey volgt de CH: 1 slag → par 4 + 2 + 1 = 7. Een 8 op SI 6 telt als 7.
  const pars = Array(18).fill(4), sis = SI_ORDE, scores = sis.map(si => si === 6 ? 8 : 5);
  const r = ronde(pars, sis, scores, F.distributeChcp(26, 18, sis.map(si => ({ si }))), { CR: 72.0, SR: 130, hcp: 20, pcc: 0 });
  // AGS = 17 × 5 + 7 = 92 → 20 × 113/130 = 17,38 → 17,4.
  check('handicap met + verhoogd: een 8 op SI 6 telt als 7, dagresultaat 17,4', F.computeSD(r), { value: 17.4, approx: false }, true);
}
{
  // CH boven 54: HI 54, SR 140, CR 74,0, par 72 → 54 × 140/113 + 2 = 68,90 → 69.
  // 69 slagen: elke hole 3, SI 1–15 een vierde. Bij 4 of meer slagen is de hoogste holescore
  // par + 5. Een 12 op SI 1 (par 4) telt als 9, niet als 10.
  const pars = Array(18).fill(4), sis = SI_ORDE, scores = sis.map(si => si === 1 ? 12 : 7);
  const r = ronde(pars, sis, scores, F.distributeChcp(69, 18, sis.map(si => ({ si }))), { CR: 74.0, SR: 140, hcp: 54, pcc: 0 });
  check('CH 69: de slagen in de AGS gaan niet boven 3 (par + 5)', F.agsSlagen(r), Array(18).fill(3), true);
  // AGS = 17 × 7 + 9 = 128 → (128 − 74) × 113/140 = 43,59 → 43,6.
  check('CH 69: een 12 telt als 9, dagresultaat 43,6', F.computeSD(r), { value: 43.6, approx: false }, true);
}
{
  // CH precies 54 (HI 54, SR 113, CR 72, par 72): geen grens, 3 slagen op elke hole.
  const r = ronde(Array(18).fill(4), SI_ORDE, Array(18).fill(9), Array(18).fill(3), { CR: 72.0, SR: 113, hcp: 54, pcc: 0 });
  check('CH precies 54: 3 slagen op elke hole, geen extra grens', F.agsSlagen(r), Array(18).fill(3), true);
}
{
  // Plushandicap: HI −2,3, SR 113, CR 72, par 72 → CH −2,3 → −2: op SI 17 en 18 een slag terug.
  // Een 7 op een par 4 met SI 18 telt als 4 + 2 − 1 = 5.
  const pars = Array(18).fill(4), sis = SI_ORDE, scores = sis.map(si => si === 18 ? 7 : 4);
  const r = ronde(pars, sis, scores, F.distributeChcp(-2, 18, sis.map(si => ({ si }))), { CR: 72.0, SR: 113, hcp: -2.3, pcc: 0 });
  check('plushandicap −2: op SI 17 en 18 een slag terug', F.agsSlagen(r), sis.map(si => si >= 17 ? -1 : 0), true);
  // AGS = 17 × 4 + 5 = 73 → 1,0.
  check('plushandicap: een 7 op SI 18 telt als 5, dagresultaat 1,0', F.computeSD(r), { value: 1.0, approx: false }, true);
}
{
  // 9 holes: HI 30,7, SR 120, CR 35,0, par 36 → 15,30 − 1 = 15,30 → 15. Met 85% gespeeld: 13.
  // Volledige CH 15: elke hole 1, SI 1–6 een tweede (SI's 1..9).
  const sis = [5, 1, 9, 3, 7, 2, 8, 4, 6], pars = [4, 4, 4, 4, 4, 4, 4, 4, 4];
  const r = ronde(pars, sis, sis.map(() => 9), F.distributeChcp(13, 9, sis.map(si => ({ si }))), { CR: 35.0, SR: 120, hcp: 30.7, pcc: 0 });
  check('9 holes met 85%: de AGS-slagen volgen de volledige 9-holes CH 15', F.agsSlagen(r), sis.map(si => si <= 6 ? 2 : 1), true);
}
{
  // Zonder handicapindex (onbekend): zoals voorheen de gespeelde slagen.
  const r = ronde(Array(18).fill(4), SI_ORDE, Array(18).fill(9), Array(18).fill(1), { CR: 72.0, SR: 113, hcp: null });
  check('zonder handicapindex: de gespeelde slagen (zoals voorheen)', F.agsSlagen(r), Array(18).fill(1), true);
}

console.log('\n=== 2. 40.000 WILLEKEURIGE RONDES, EIGEN BEREKENING IN HELE GETALLEN ===\n');
let zaad = 31337; const rnd = () => (zaad = (zaad * 48271) % 2147483647) / 2147483647;
const kies = (a, b) => a + Math.floor(rnd() * (b - a + 1));
const schud = a => { const b = a.slice(); for (let i = b.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [b[i], b[j]] = [b[j], b[i]]; } return b; };
let n9 = 0, n18 = 0, nAnders = 0;
for (let k = 0; k < 40000; k++) {
  const n = rnd() < 0.3 ? 9 : 18;
  const sis = n === 18 ? schud(SI_ORDE) : schud(rnd() < 0.5 ? [1, 3, 5, 7, 9, 11, 13, 15, 17] : SI_ORDE.slice(0, 9));
  const pars = sis.map(() => kies(3, 5)), par = pars.reduce((a, b) => a + b, 0);
  const h10 = kies(-60, 540), sr = kies(55, 155), cr10 = par * 10 + kies(-40, 40) * (n === 9 ? 1 : 2), pcc10 = n === 18 ? kies(-10, 30) : 0;
  const ch = chEigen(n, cr10, sr, par, h10);
  // gespeeld met een bijgestelde handicap: percentage of +/−, soms gewoon de CH
  const gespeeld = rnd() < 0.3 ? ch : (rnd() < 0.5 ? Math.round(ch * kies(50, 100) / 100) : ch + kies(-6, 6));
  const phcps = F.distributeChcp(gespeeld, n, sis.map(si => ({ si })));
  const scores = pars.map(p => p + kies(-2, 9));
  const r = ronde(pars, sis, scores, phcps, { CR: cr10 / 10, SR: sr, hcp: h10 / 10, pcc: pcc10 / 10 });
  const slagen = slagenEigen(ch, sis);
  check(`slagen ${n} holes, index ${h10 / 10}, SR ${sr}, CR ${cr10 / 10}, CH ${ch}`, F.agsSlagen(r), slagen);
  const ags = agsEigen(pars, scores, slagen);
  if (n === 18) {
    check(`dagresultaat 18 holes, index ${h10 / 10}, CH ${ch}, gespeeld ${gespeeld}, AGS ${ags}`, F.computeSD(r).value, sd18Eigen(ags, cr10, sr, pcc10)); n18++;
  } else {
    // 9 holes: 113/SR × (AGS − CR − PCC) + 0,52 × index + 1,2, op tienden (regel 5.1b, 2024).
    // In tienden, exact met de gemeenschappelijke noemer 1000 × SR:
    // 113 × (AGS×10 − CR×10) × 1000  +  (0,52 × index×10 + 12) × 1000 × SR.
    const teller = 113 * (ags * 10 - cr10) * 1000 + (520 * h10 + 12000) * sr;
    const verwacht = rond(teller, 1000 * sr) / 10;
    check(`dagresultaat 9 holes, index ${h10 / 10}, CH ${ch}, AGS ${ags}`, F.computeSD(r).value, verwacht); n9++;
  }
  if (gespeeld !== ch) nAnders++;
}
console.log(`  ${n18} rondes van 18 en ${n9} van 9 holes nagerekend; ${nAnders} daarvan met een bijgestelde handicap`);

console.log('\n=== 3. ZONDER BIJSTELLING: PRECIES ZOALS VOORHEEN ===\n');
let nGelijk = 0;
for (let k = 0; k < 20000; k++) {
  const sis = schud(SI_ORDE), pars = sis.map(() => kies(3, 5)), par = pars.reduce((a, b) => a + b, 0);
  const h10 = kies(0, 540), sr = kies(55, 155), cr10 = par * 10 + kies(-80, 80);
  const ch = F.calcChcp(18, cr10 / 10, sr, par, h10 / 10);
  const phcps = F.distributeChcp(ch, 18, sis.map(si => ({ si })));
  const scores = pars.map(p => p + kies(-2, 9));
  const r = ronde(pars, sis, scores, phcps, { CR: cr10 / 10, SR: sr, hcp: h10 / 10, pcc: 0 });
  const oud = r.holes.reduce((t, h) => t + Math.min(h.score, h.par + h.phcp + 2), 0);   // de berekening tot 13D
  const nieuw = r.holes.reduce((t, h, i) => t + F.agsFor(h, F.agsSlagen(r)[i]), 0);
  if (ch <= 54) { check(`gelijk aan voorheen bij CH ${ch}`, nieuw, oud); nGelijk++; }
}
console.log(`  ${nGelijk} rondes zonder bijstelling (CH t/m 54): AGS gelijk aan voorheen`);

console.log(`\n${goed} goed, ${fout} fout`);
if (eerste.length) console.log(eerste.join('\n'));
console.log('\n' + (fout ? `${fout} FOUT(EN)` : 'GEEN FOUTEN'));
process.exit(fout ? 1 : 0);
