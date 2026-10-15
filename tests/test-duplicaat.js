const fs = require('fs');
const html = fs.readFileSync(process.env.APP || require('path').join(__dirname, '..', 'golf-score.html'), 'utf8');
const js = (html.match(/<script[^>]*>([\s\S]*)<\/script>/) || [])[1];

// De echte maat-zoeker uit herplanRonde
const i = js.indexOf('let maat = saved.find(');
const maatCode = js.slice(i, js.indexOf(';', js.indexOf("!== (r.player || '')", i)) + 1);
// gespeeldeHoles hoort bij de code die we testen — meegeven aan het fragment
const gespeeldeHolesCode = js.slice(js.indexOf('function gespeeldeHoles'), js.indexOf('}', js.indexOf('function gespeeldeHoles')) + 1);
// 'metScores' komt uit herplanRonde: bij CORRIGEREN gaan rondes mét scores mee, bij
// herplannen alleen lege. Dat is een parameter van de omliggende functie en zit dus niet
// in het uitgeknipte fragment; hier geven we hem mee zodat het fragment draait. Deze test
// gaat over de maat-zoeker, niet over die keuze — vandaar false: het strengste geval.
const maatTest = new Function('saved', 'r',
  'const metScores = false;\n' + gespeeldeHolesCode + '\n' + maatCode + ' return maat;');

// De echte naamcontrole uit startRound
const naamTest = (name, name2) => name2 === name;

// Met live tellen moeten de testrondes echte holes hebben — een ronde zonder holes
// bestaat in de app niet (de import weigert hem).
const R = (id, date, time, player, played = 0) => ({ id, date, time, player, holesCount: 9,
  holes: Array.from({ length: 9 }, (_, i) => ({ id: i + 1, par: 4, si: i + 1, score: i < played ? 5 : null })) });
let fout = 0, ok = 0;
const check = (goed, tekst, extra) => { goed ? ok++ : fout++; console.log((goed ? '  ok   ' : ' FOUT  ') + tekst + (extra ? '   ' + extra : '')); };

console.log('=== WIE GAAT ER MEE ALS SPELER 2 BIJ HERPLANNEN? ===');
{
  const s = [R(1, '2026-08-24', '09:30', 'Mark'), R(2, '2026-08-24', '09:30', 'Speler 2')];
  check(maatTest(s, s[0])?.id === 2, 'andere speler op hetzelfde tijdstip gaat mee');
}
{
  const s = [R(1, '2026-08-24', '09:30', 'Mark'), R(2, '2026-08-24', '09:30', 'Mark')];
  check(maatTest(s, s[0]) === undefined, 'DEZELFDE speler op hetzelfde tijdstip gaat NIET mee', '(dit veroorzaakte het duplicaat)');
}
{
  const s = [R(1, '2026-08-24', '09:30', 'Mark'), R(2, '2026-08-24', '09:30', 'Speler 2', 9)];
  check(maatTest(s, s[0]) === undefined, 'ronde met scores gaat niet mee');
}
{
  const s = [R(1, '2026-08-24', '09:30', 'Mark'), R(2, '2026-08-24', '14:00', 'Speler 2')];
  check(maatTest(s, s[0]) === undefined, 'andere tijd gaat niet mee');
}
{
  const s = [R(1, '2026-08-24', '09:30', 'Mark'), R(2, '2026-08-24', '09:30', 'Mark'), R(3, '2026-08-24', '09:30', 'Jan')];
  check(maatTest(s, s[0])?.id === 3, 'bij meerdere: de ronde van een andere speler wordt gekozen');
}
{
  const s = [R(1, '2026-08-24', '', 'Mark'), R(2, '2026-08-24', '', 'Speler 2')];
  check(maatTest(s, s[0])?.id === 2, 'zonder tijd: koppeling werkt nog steeds');
}
{
  const s = [R(1, '2026-08-24', '09:30', 'Mark'), R(2, '2026-08-24', '09:30', 'mark')];
  check(maatTest(s, s[0])?.id === 2, 'andere hoofdletters gelden als een andere speler', '(zoals overal in de app)');
}

console.log('\n=== TWEE KEER DEZELFDE NAAM BIJ HET STARTEN ===');
check(naamTest('Mark', 'Mark') === true, 'identieke namen worden geweigerd');
check(naamTest('Mark', 'Speler 2') === false, 'verschillende namen zijn toegestaan');
check(naamTest('Mark', 'mark') === false, 'hoofdlettersverschil telt als een andere speler');
check(naamTest('Mark', '') === false, 'lege naam valt onder de bestaande controle ervoor');

console.log('\n' + (fout === 0 ? 'ALLE ' + ok + ' CONTROLES GESLAAGD' : fout + ' FOUT(EN), ' + ok + ' geslaagd'));
