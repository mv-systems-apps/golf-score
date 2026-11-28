// Het handicapverloop (whsVerloop) nagerekend met een rechttoe-rechtaan tweede berekening.
//
// Sinds 13527DA-142 komen de handicap van nu, de ESR-verlagingen, de Low HI, de rondekaarten
// en de grafiek uit één doorrekening. Die houdt de laagste index van de afgelopen 365 dagen
// bij in een oplopende rij (snel, maar foutgevoelig). Deze test rekent elke stap opnieuw uit
// door gewoon alle eerdere stappen af te lopen, volgens de Rules of Handicapping 2024:
//   - 5.4: de index wordt per speeldag bijgewerkt; bij meer rondes op één dag geldt bij elk
//          de index van het begin van die dag;
//   - 5.9: uitzonderlijke score tegen de index die gold (de eindstand van de vorige
//          speeldag, mét cap), −1 of −2 op de recentste 20, deze ronde inbegrepen;
//   - 5.7: Low HI = de laagste eindstand van een speeldag (zoals hij gold, dus mét ESR) uit
//          de 365 dagen vóór de dag van de ronde, pas vanaf 20 scores; een handmatige Low HI
//          geldt altijd;
//   - 5.8: soft en hard cap tegen die Low HI.
// 400 willekeurige reeksen van 1 tot 150 rondes, met tussenpozen van 0 (dezelfde dag) tot 40 dagen (dus ook
// rondes die uit het venster van 365 dagen vallen), soms een handmatige Low HI, soms een
// uitschieter naar beneden. Ook de Low HI van nu (waarde én ronde: bij gelijke waarde de oudste).
const fs = require('fs');
const html = fs.readFileSync(process.env.APP || require('path').join(__dirname, '..', 'golf-score.html'), 'utf8');
const js = (html.match(/<script[^>]*>([\s\S]*)<\/script>/) || [])[1];
const pak = naam => { const a = js.indexOf('function ' + naam + '('); if (a < 0) throw new Error(naam + ' niet gevonden'); return js.slice(a, js.indexOf('\n}', a) + 2); };
const NAMEN = ['whsIndexRound', 'whsStaffel', 'applyHandicapCaps', 'esrVerlaging', 'whsVerloop'];
const F = new Function(NAMEN.map(pak).join('\n') + `; return { ${NAMEN.join(', ')} };`)();

let zaad = 7; const rnd = () => (zaad = (zaad * 48271) % 2147483647) / 2147483647;
const kies = (a, b) => a + Math.floor(rnd() * (b - a + 1));
const DAG = 864e5, JAAR = 365 * DAG;
let fout = 0, stappen = 0, metCap = 0, metEsr = 0; const eerste = [];
const meld = t => { fout++; if (eerste.length < 10) eerste.push('  FOUT ' + t); };

for (let s = 0; s < 400; s++) {
  const lengte = kies(1, 150); let t = 0; const c = [];
  for (let i = 0; i < lengte; i++) {
    t += kies(0, 40) * DAG;
    const sd = Math.round((kies(-20, 500) / 10 + (rnd() < 0.05 ? -12 : 0)) * 10) / 10;
    c.push({ id: i, sd, sdEsr: sd - kies(0, 9) / 100, t });
  }
  const handmatig = rnd() < 0.2 ? kies(50, 300) / 10 : null;
  const v = F.whsVerloop(c, handmatig);
  // Tweede berekening
  const dag = x => { const d = new Date(x); return Math.round(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / DAG); };
  const eindVanDag = j => j === lengte - 1 || dag(c[j + 1].t) !== dag(c[j].t);
  const adj = c.map(() => 0), index = [];
  for (let i = 0; i < lengte; i++) {
    let gold = null;                          // de index aan het begin van de speeldag
    for (let j = i - 1; j >= 0; j--) if (dag(c[j].t) < dag(c[i].t)) { gold = index[j]; break; }
    if (gold !== null) {
      const m = F.esrVerlaging(gold, c[i].sdEsr);
      if (m) { metEsr++; for (let k = Math.max(0, i - 19); k <= i; k++) adj[k] -= m; }
    }
    const w = []; for (let k = Math.max(0, i - 19); k <= i; k++) w.push(c[k].sd + adj[k]);
    w.sort((a, b) => a - b);
    const st = F.whsStaffel(w.length);
    const ruw = F.whsIndexRound(w.slice(0, st.count).reduce((a, b) => a + b, 0) / st.count + st.adj);
    let low = handmatig;
    if (low == null && i + 1 >= 20) for (let j = 0; j < i; j++)
      if (eindVanDag(j) && dag(c[j].t) < dag(c[i].t) && dag(c[j].t) >= dag(c[i].t) - 365 && (low == null || index[j] < low)) low = index[j];
    const cap = F.applyHandicapCaps(ruw, low); if (cap.type) metCap++;
    index.push(cap.value);
    const g = v.stappen[i];
    if (g.value !== cap.value || g.lowHi !== low || g.raw !== ruw || g.capType !== cap.type) meld(`reeks ${s}, stap ${i}: ${JSON.stringify(g)} — verwacht index ${cap.value}, Low HI ${low}, ruw ${ruw}`);
    stappen++;
  }
  for (let k = 0; k < lengte; k++) if (v.adj.get(k) !== adj[k]) { meld(`reeks ${s}: verlaging ronde ${k} ${v.adj.get(k)} — verwacht ${adj[k]}`); break; }
  let lo = null, id = null;
  if (lengte >= 20) for (let j = 0; j < lengte; j++)
    if (eindVanDag(j) && dag(c[j].t) >= dag(c[lengte - 1].t) - 365 && (lo == null || index[j] < lo)) { lo = index[j]; id = c[j].id; }
  const kreeg = v.lowHi ? [v.lowHi.value, v.lowHi.roundId] : [null, null];
  if (kreeg[0] !== lo || kreeg[1] !== id) meld(`reeks ${s}: Low HI van nu ${JSON.stringify(kreeg)} — verwacht ${JSON.stringify([lo, id])}`);
}
console.log(`\n  ${stappen} stappen in 400 reeksen nagerekend; ${metCap} met een cap, ${metEsr} uitzonderlijke scores`);
eerste.forEach(r => console.log(r));
console.log('\n' + (fout ? `${fout} FOUT(EN)` : 'GEEN FOUTEN'));
process.exit(fout ? 1 : 0);
