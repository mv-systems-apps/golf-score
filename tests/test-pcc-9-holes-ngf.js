// Dagresultaat bij 9 holes met PCC, tegen de dagresultaten die de NGF-app gaf.
//
// NGF, Wegwijs in Handicapping (2024): "Dagresultaat = (113 ÷ 9-holes Slope Rating) x
// (aangepaste bruto score – 9-holes Course Rating – ½*PCC aanpassing)", daarna aangevuld
// met het verwachte resultaat voor de andere negen. De PCC die de NGF-app bij een
// 9-holesronde toont (bij Mark −0,5) telt dus voor de helft.
//
// Tot 13527DA-143 trok de app de volle waarde af en kwam 0,2 tot 0,3 te hoog uit. Deze test
// rekent Marks echte rondes uit echte-rondes.json na (zonder het vastgestelde dagresultaat)
// en vergelijkt met wat de NGF-app vaststelde:
//   - alle rondes met PCC (bij 9 holes −0,5);
//   - als controle alle rondes zonder PCC, die al klopten.
// Marks backup van 13-10-2026 21:10: hij heeft daarin zijn invoerfouten hersteld (scores,
// PCC en de index die gold), zodat alle 36 qualifying rondes het NGF-dagresultaat geven.
const fs = require('fs'), path = require('path');
const html = fs.readFileSync(process.env.APP || path.join(__dirname, '..', 'golf-score.html'), 'utf8');
const js = (html.match(/<script[^>]*>([\s\S]*)<\/script>/) || [])[1];
const pak = naam => { const a = js.indexOf('function ' + naam + '('); if (a < 0) return ''; return js.slice(a, js.indexOf('\n}', a) + 2); };
const NAMEN = ['whsRound', 'whsIndexRound', 'distributeChcp', 'indexVoorHoles', 'calcChcpOnafgerond', 'calcChcp', 'agsFor', 'volleSlagen', 'agsSlagen', 'agsVan', 'expectedSD9', 'sdOnafgerond', 'computeSD'];
const F = new Function(NAMEN.map(pak).join('\n') + `; return { computeSD };`)();
const RONDES = JSON.parse(fs.readFileSync(path.join(__dirname, 'echte-rondes.json'), 'utf8'));

let fout = 0;
const check = (naam, gekregen, verwacht) => {
  const ok = gekregen === verwacht; if (!ok) fout++;
  console.log(`  ${ok ? 'ok  ' : 'FOUT'} ${naam}: ${gekregen}${ok ? '' : ' — verwacht ' + verwacht}`);
};
const reken = (datum, aanpassing = {}) => {
  const r = RONDES.find(x => x.date === datum && x.holes.length === 9 && x.qualifying);
  const ngf = r.sdFinal;
  const c = F.computeSD(Object.assign({}, r, { sdFinal: null }, aanpassing));
  return [c ? c.value : null, ngf];
};

// Alle qualifying rondes met een vastgesteld dagresultaat, 9 en 18 holes (backup van
// 13-10-2026 21:10, waarin Mark ook de index van de rondes vóór juli heeft nagekeken).
const alle = RONDES.filter(r => r.qualifying && r.sdFinal != null && r.sdFinal !== '')
  .sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
const reken2 = r => { const c = F.computeSD(Object.assign({}, r, { sdFinal: null })); return c ? c.value : null; };

console.log('\n=== 1. RONDES MET PCC: BIJ 9 HOLES TELT DE HELFT ===\n');
alle.filter(r => +(r.pcc || 0) !== 0).forEach(r => check(`${r.date} (${r.holes.length} holes, PCC ${r.pcc}): NGF ${r.sdFinal}`, reken2(r), r.sdFinal));

console.log('\n=== 2. RONDES ZONDER PCC: ONGEWIJZIGD ===\n');
alle.filter(r => +(r.pcc || 0) === 0).forEach(r => check(`${r.date} (${r.holes.length} holes): NGF ${r.sdFinal}`, reken2(r), r.sdFinal));
console.log(`\n  ${alle.length} rondes nagerekend tegen de NGF`);

console.log('\n' + (fout ? `${fout} FOUT(EN)` : 'GEEN FOUTEN'));
process.exit(fout ? 1 : 0);
