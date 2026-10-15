// Uitzonderlijke score (ESR): het ONAFGERONDE dagresultaat tegen de index, zonder rekenruis.
//
// Rules of Handicapping 2024, regel 5.9: "Any reduction is based on the difference between
// the Score Differential (unrounded) and the player's Handicap Index." 7,0 t/m 9,9 slagen
// beter → −1,0; 10,0 of meer → −2,0.
//
// Tot 13527DA-13E vergeleek de app het op tienden afgeronde dagresultaat, en zonder de
// rekenruis eraf: index 8,2 en dagresultaat 1,2 gaf 6,9999… en dus geen verlaging.
//
// Deel 1: met de hand uitgerekende grensgevallen. Deel 2: 3000 willekeurige reeksen van
// 25 rondes, de verlaging per ronde nagerekend in hele getallen, tegen de index die gold
// (na soft/hard cap, sinds 13527DA-142). Deel 3: één doorloop
// over alles geeft per ronde hetzelfde als een doorloop die bij die ronde ophoudt.
const fs = require('fs');
const html = fs.readFileSync(process.env.APP || require('path').join(__dirname, '..', 'golf-score.html'), 'utf8');
const js = (html.match(/<script[^>]*>([\s\S]*)<\/script>/) || [])[1];
const pak = naam => { const a = js.indexOf('function ' + naam + '('); if (a < 0) return ''; return js.slice(a, js.indexOf('\n}', a) + 2); };
const NAMEN = ['whsRound', 'distributeChcp', 'indexVoorHoles', 'calcChcpOnafgerond', 'calcChcp', 'agsFor', 'volleSlagen', 'agsSlagen', 'agsVan', 'expectedSD9', 'sdOnafgerond', 'computeSD',
               'effectiveSD', 'esrSd', 'esrVerlaging', 'whsIndexRound', 'whsStaffel', 'applyHandicapCaps', 'whsVerloop', 'computeEsrAdjustments'];
const F = new Function(NAMEN.map(pak).join('\n') + `; return { ${NAMEN.map(n => `${n}: typeof ${n} === 'function' ? ${n} : null`).join(', ')} };`)();
// Oudere versie zonder esrSd: daar telde het afgeronde dagresultaat.
if (!F.esrSd) F.esrSd = r => { const e = F.effectiveSD(r); return e ? e.value : null; };

let fout = 0, goed = 0; const eerste = [];
const check = (naam, gekregen, verwacht, toon = false) => {
  const ok = JSON.stringify(gekregen) === JSON.stringify(verwacht);
  if (ok) goed++; else { fout++; if (eerste.length < 10) eerste.push(`  FOUT ${naam}: ${JSON.stringify(gekregen)} — verwacht ${JSON.stringify(verwacht)}`); }
  if (toon) console.log(`  ${ok ? 'ok  ' : 'FOUT'} ${naam}: ${JSON.stringify(gekregen)}${ok ? '' : ' — verwacht ' + JSON.stringify(verwacht)}`);
};
// Een ronde van 18 holes (alle par 4, SI 1..18) met een gegeven totaal; de AGS is gelijk
// aan het totaal zolang geen hole boven de net double bogey uitkomt (scores 4–6, CH ≥ 0).
function ronde18(id, dag, totaal, cr, sr, hcp = 10) {
  const scores = Array(18).fill(4); let rest = totaal - 72;
  for (let i = 0; rest > 0; i = (i + 1) % 18) { if (scores[i] < 6) { scores[i]++; rest--; } }
  const ch = F.calcChcp(18, cr, sr, 72, hcp);
  const ph = F.distributeChcp(ch, 18, Array.from({ length: 18 }, (_, i) => ({ si: i + 1 })));
  return { id, date: `2026-01-${String(dag).padStart(2, '0')}`, time: '10:00', hcp, CR: cr, SR: sr, PAR: 72, pcc: 0,
           holes: scores.map((s, i) => ({ par: 4, si: i + 1, phcp: ph[i], score: s })) };
}
// Zoals esrMapFor de reeks opbouwt: afgerond dagresultaat voor de index, het onafgeronde voor de vergelijking.
const reeks = rondes => rondes.map((r, i) => ({ id: r.id, sd: F.effectiveSD(r).value, sdEsr: F.esrSd(r), t: i }));
const handmatig = (id, dag, sd) => ({ id, date: `2026-01-${String(dag).padStart(2, '0')}`, sdFinal: sd, holes: [] });

console.log('\n=== 1. GRENSGEVALLEN ===\n');
{
  // 20 rondes met dagresultaat 8,2 → index 8,2 (gemiddelde van de laagste 8, geen bijtelling).
  const basis = Array.from({ length: 20 }, (_, i) => handmatig(i + 1, i + 1, 8.2));
  // Vastgesteld dagresultaat 1,2: precies 7,0 beter → −1,0 (rekenruis mag dit niet breken).
  let m = F.computeEsrAdjustments(reeks([...basis, handmatig(99, 25, 1.2)]));
  check('index 8,2, dagresultaat 1,2 (precies 7,0 beter): −1,0', m.get(99), -1, true);
  // 10,0 beter: 8,2 − (−1,8) = 10,0 → −2,0.
  m = F.computeEsrAdjustments(reeks([...basis, handmatig(99, 25, -1.8)]));
  check('index 8,2, dagresultaat −1,8 (precies 10,0 beter): −2,0', m.get(99), -2, true);
  // 6,9 beter: geen verlaging.
  m = F.computeEsrAdjustments(reeks([...basis, handmatig(99, 25, 1.3)]));
  check('index 8,2, dagresultaat 1,3 (6,9 beter): geen verlaging', m.get(99), 0, true);
}
{
  // Onafgerond telt: CR 70,6, SR 130, AGS 72 → (72 − 70,6) × 113/130 = 1,2169… → afgerond 1,2.
  // Afgerond zou 8,2 − 1,2 = 7,0 zijn (verlaging), onafgerond is het 6,983 → GEEN verlaging.
  const basis = Array.from({ length: 20 }, (_, i) => handmatig(i + 1, i + 1, 8.2));
  const r = ronde18(99, 25, 72, 70.6, 130);
  check('dagresultaat van die ronde, afgerond: 1,2', F.computeSD(r).value, 1.2, true);
  check('onafgerond 6,98 beter dan 8,2: geen verlaging (regel 5.9)', F.computeEsrAdjustments(reeks([...basis, r])).get(99), 0, true);
  // En de andere kant: CR 70,7 → (72 − 70,7) × 113/130 = 1,1300 → 7,07 beter → −1,0.
  const r2 = ronde18(99, 25, 72, 70.7, 130);
  check('onafgerond 7,07 beter: −1,0', F.computeEsrAdjustments(reeks([...basis, r2])).get(99), -1, true);
}
{
  // De verlaging geldt voor de uitzonderlijke ronde en de 19 rondes ervóór.
  const basis = Array.from({ length: 25 }, (_, i) => handmatig(i + 1, i + 1, 8.2));
  const m = F.computeEsrAdjustments(reeks([...basis, handmatig(99, 28, 1.2)]));
  check('de 19 rondes ervóór krijgen ook −1,0, de oudere niet', [m.get(7), m.get(6), m.get(25)], [-1, 0, -1], true);
}

console.log('\n=== 2. 3000 WILLEKEURIGE REEKSEN, NAGEREKEND IN HELE GETALLEN ===\n');
let zaad = 5309; const rnd = () => (zaad = (zaad * 48271) % 2147483647) / 2147483647;
const kies = (a, b) => a + Math.floor(rnd() * (b - a + 1));
let nRondes = 0, nEsr = 0;
for (let k = 0; k < 3000; k++) {
  const rondes = [];
  const lengte = kies(5, 25);
  for (let i = 0; i < lengte; i++) {
    if (rnd() < 0.1) rondes.push(handmatig(i + 1, i + 1, kies(-20, 400) / 10));
    else rondes.push(ronde18(i + 1, i + 1, kies(72, 108), kies(650, 760) / 10, kies(100, 150), 10));
  }
  const r = reeks(rondes);
  const app = F.computeEsrAdjustments(r);
  // Eigen naberekening, stap voor stap in tienden. Per ronde: eerst de vergelijking met de
  // index die gold (na de vorige stap, MET soft/hard cap: regel 5.9 en 13527DA-142), het
  // verschil met het ONAFGERONDE dagresultaat exact; dan de index uit de recentste 20 met
  // de verlagingen van dat moment; dan de cap tegen de Low HI (de laagste eerdere index,
  // vanaf 20 scores; alle rondes liggen hier binnen een jaar).
  const adj = new Map(r.map(x => [x.id, 0]));
  const index10 = [];
  r.forEach((x, i) => {
    if (i > 0) {
      const hi10 = index10[i - 1];
      const ronde = rondes[i];
      let groter7, groter10;
      if (ronde.sdFinal != null) {
        const sd10 = Math.round(ronde.sdFinal * 10);
        groter7 = hi10 - sd10 >= 70; groter10 = hi10 - sd10 >= 100;
      } else {
        // dagresultaat = 113 × (AGS − CR) / SR; in tienden × SR: 113 × (AGS×10 − CR×10)
        const ags = ronde.holes.reduce((t, h) => t + h.score, 0), cr10 = Math.round(ronde.CR * 10);
        const links = hi10 * ronde.SR - 113 * (ags * 10 - cr10);          // (index − dagresultaat) × 10 × SR
        groter7 = links >= 70 * ronde.SR; groter10 = links >= 100 * ronde.SR;
      }
      const m = groter10 ? 2 : groter7 ? 1 : 0;
      if (m) { nEsr++; r.slice(Math.max(0, i - 19), i + 1).forEach(p => adj.set(p.id, adj.get(p.id) - m)); }
    }
    // index na deze ronde, in tienden: (som/aantal + bijtelling), ,5 naar boven
    const venster = r.slice(Math.max(0, i - 19), i + 1);
    const st = F.whsStaffel(venster.length);
    const vals = venster.map(p => Math.round((p.sd + adj.get(p.id)) * 10)).sort((a, b) => a - b).slice(0, st.count);
    const som = vals.reduce((a, b) => a + b, 0), adj10 = Math.round(st.adj * 10);
    const ruw10 = Math.floor((2 * (som + adj10 * st.count) + st.count) / (2 * st.count));
    let waarde10 = Math.min(ruw10, 540);
    if (i + 1 >= 20) {
      const low10 = Math.min(...index10);
      if (ruw10 - low10 > 30) {
        // soft: low + 3,0 + de helft van wat erboven komt; hard: hooguit low + 5,0. In halve tienden.
        const half = Math.min(2 * (low10 + 30) + (ruw10 - low10 - 30), 2 * (low10 + 50), 1080);
        waarde10 = Math.floor((half + 1) / 2);
      }
    }
    index10.push(waarde10);
  });
  r.forEach(x => check(`reeks ${k}, ronde ${x.id}`, app.get(x.id), adj.get(x.id)));
  nRondes += r.length;
  // Deel 3 meteen meenemen: één doorloop over alles geeft per ronde dezelfde index als een
  // doorloop die bij die ronde ophoudt (latere rondes veranderen het verleden niet).
  const alles = F.whsVerloop(r).stappen.map(st => st.value);
  const perStap = r.map((x, i) => F.whsVerloop(r.slice(0, i + 1)).stappen[i].value);
  check(`reeks ${k}: één doorloop gelijk aan per ronde opnieuw`, alles, perStap);
}
console.log(`  ${nRondes} rondes in 3000 reeksen nagerekend; ${nEsr} keer een uitzonderlijke score`);

console.log(`\n${goed} goed, ${fout} fout`);
if (eerste.length) console.log(eerste.join('\n'));
console.log('\n' + (fout ? `${fout} FOUT(EN)` : 'GEEN FOUTEN'));
process.exit(fout ? 1 : 0);
