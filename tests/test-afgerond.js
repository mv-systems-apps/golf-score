// De drie manieren waarop de app "afgerond" bepaalt, letterlijk zoals ze in de code staan
const A = r => { const g = r.playedCount ?? r.holes?.filter(h => h.score !== null).length ?? 0;
                 const t = r.holesCount ?? r.holes?.length ?? 0; return t > 0 && g >= t; };
const B = r => (r.holes || []).every(h => h.score !== null);
const C = r => (r.holes || []).length > 0 && (r.holes || []).every(h => h.score !== null);

const gevallen = [
  ['normale afgeronde ronde',        { playedCount: 9, holesCount: 9, holes: Array(9).fill({score: 5}) }],
  ['halve ronde',                    { playedCount: 4, holesCount: 9, holes: [...Array(4).fill({score: 5}), ...Array(5).fill({score: null})] }],
  ['geplande ronde',                 { playedCount: 0, holesCount: 9, holes: Array(9).fill({score: null}) }],
  ['GEEN holes (leeg of stuk)',      { playedCount: 0, holesCount: 0, holes: [] }],
  ['holes ontbreekt helemaal',       { playedCount: 0, holesCount: 9 }],
  ['teller loopt achter op scores',  { playedCount: 4, holesCount: 9, holes: Array(9).fill({score: 5}) }],
  ['teller loopt vóór op scores',    { playedCount: 9, holesCount: 9, holes: [...Array(8).fill({score: 5}), {score: null}] }],
  ['oude backup zonder tellers',     { holes: Array(9).fill({score: 5}) }],
  ['9 holes maar holesCount 18',     { playedCount: 9, holesCount: 18, holes: Array(9).fill({score: 5}) }],
];

console.log('  ' + 'geval'.padEnd(32) + 'A: tellers   B: elke score   C: B + niet leeg   gelijk?');
let afwijkingen = 0;
gevallen.forEach(([naam, r]) => {
  const a = A(r), b = B(r), c = C(r);
  const gelijk = (a === b) && (b === c);
  if (!gelijk) afwijkingen++;
  console.log('  ' + naam.padEnd(32) + String(a).padEnd(13) + String(b).padEnd(16) + String(c).padEnd(19) + (gelijk ? 'ja' : 'NEE'));
});
console.log('\n' + afwijkingen + ' van de ' + gevallen.length + ' gevallen geven een verschillende uitkomst');
