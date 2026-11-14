const fs = require('fs');
const html = fs.readFileSync(process.env.APP || require('path').join(__dirname, '..', 'golf-score.html'), 'utf8');
const css = html.slice(html.indexOf('<style'), html.indexOf('</style>'));
let fout = 0, punt = 0;
const ok = (g, t, d) => { if (!g) fout++; console.log((g ? '  ok  ' : ' FOUT ') + t + (d ? ' → ' + d : '')); };
const let_op = t => { punt++; console.log(' let op ' + t); };

console.log('=== 1. SYNTAX ===');
const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]).filter(s => s.trim());
let sOk = true, sFout = '';
scripts.forEach(s => { try { new Function(s); } catch (e) { sOk = false; sFout = e.message; } });
ok(sOk, 'JS-syntax', sFout);

console.log('\n=== 2. OPMAAKREGELS DIE BREDER GRIJPEN DAN HUN NAAM SUGGEREERT ===');
// Regels zonder klasse-anker: die raken alles van dat elementtype
const breed = [];
[...css.matchAll(/(^|\})\s*([^{}@]+)\{/g)].forEach(m => {
  const sel = m[2].trim().replace(/\s+/g, ' ');
  if (!sel || sel.startsWith('/*') || sel.startsWith('@') || sel.includes('%')) return;
  const delen = sel.split(',').map(s => s.trim());
  delen.forEach(d => {
    const heeftKlasse = /\.|#/.test(d);
    const elementOnly = /^[a-z]+(\s*[>+~]\s*[a-z:()-]+)*$/i.test(d);
    if (!heeftKlasse && elementOnly && !/^(html|body|\*)$/.test(d)) breed.push(d);
  });
});
console.log('Regels die op elementniveau werken (dus overal):');
[...new Set(breed)].forEach(d => console.log('   ' + d));
ok(true, 'geïnventariseerd — ' + new Set(breed).size + ' selectors');

console.log('\n=== 3. :only-child EN SOORTGELIJKE VALKUILEN ===');
const valkuil = [...css.matchAll(/[^{}]*:(only-child|first-child|last-child|nth-child\([^)]*\))[^{}]*\{[^}]*\}/g)];
valkuil.forEach(m => {
  const r = m[0].replace(/\s+/g, ' ');
  const sel = r.slice(0, r.indexOf('{')).trim();
  const heeftAutoMarge = /margin[^;]*auto/.test(r);
  console.log((heeftAutoMarge ? ' let op ' : '  ok  ') + sel.slice(0, 80));
  if (heeftAutoMarge) { punt++; console.log('        bevat auto-marge: in een flex-container slurpt die de vrije ruimte op'); }
});
ok(!/only-child[^{]*\{[^}]*margin[^;]*auto/.test(css), 'geen auto-marge meer op :only-child-regels');

console.log('\n=== 4. KNOPPEN: ICOON + LABEL ===');
const knoppen = [...html.matchAll(/<button\b[^>]*>([\s\S]*?)<\/button>/g)].map(m => {
  const tag = m[0].slice(0, m[0].indexOf('>') + 1);
  // Alleen de zichtbare inhoud telt: attributen zoals title staan buiten de knopinhoud,
  // en template-uitdrukkingen binnen een svg zijn geen label.
  const zichtbaar = m[1].replace(/<svg[\s\S]*?<\/svg>/g, '').replace(/<[^>]*>/g, '')
                        .replace(/\$\{[^}]*\}/g, '').replace(/&[a-z]+;/g, '').trim();
  return {
    regel: html.slice(0, m.index).split('\n').length,
    style: (tag.match(/style="([^"]*)"/) || [])[1] || '',
    cls: (tag.match(/class="([^"]*)"/) || [])[1] || '',
    inhoud: m[1],
    tekst: zichtbaar,
  };
});
const metBeide = knoppen.filter(k => /<svg/.test(k.inhoud) && k.tekst !== '');
console.log('knoppen met icoon én label: ' + metBeide.length);
const zonderGap = metBeide.filter(k => !/gap:/.test(k.style) && !/gap:/.test(css.slice(0, 0) + (k.cls ? '' : '')));
zonderGap.forEach(k => let_op('regel ' + k.regel + ': geen gap ingesteld — afstand hangt af van een spatie in de tekst'));
ok(metBeide.every(k => /display:\s*flex/.test(k.style) || /gap:/.test(k.style) || k.cls.includes('tab')),
   'alle icoon+label-knoppen regelen hun afstand zelf');

console.log('\n=== 5. ICOONKNOPPEN ===');
const icoonOnly = knoppen.filter(k => /<svg/.test(k.inhoud) && k.tekst === '');
console.log('knoppen met alleen een icoon: ' + icoonOnly.length);
ok(/button > svg:only-child[\s\S]{0,80}display: block/.test(css), 'verticale centrering via display:block aanwezig');

console.log('\n=== 6. DUBBELE ID\'S EN TAGBALANS ===');
const ids = [...html.matchAll(/id="([\w-]+)"/g)].map(m => m[1]);
const dub = [...new Set(ids.filter((v, i) => ids.indexOf(v) !== i))];
ok(dub.length === 0, 'geen dubbele id\'s', dub.join(', '));
['span', 'button', 'svg', 'textarea', 'table', 'label'].forEach(t => {
  const o = (html.match(new RegExp('<' + t + '[\\s>]', 'g')) || []).length;
  const c = (html.match(new RegExp('</' + t + '>', 'g')) || []).length;
  ok(o === c, 'tagbalans ' + t, o + '/' + c);
});

console.log('\n=== 7. VERWIJZINGEN NAAR NIET-BESTAANDE ELEMENTEN ===');
const gebruikt = [...new Set([...html.matchAll(/getElementById\('([\w-]+)'\)/g)].map(m => m[1]))];
// Elementen die in code worden aangemaakt bestaan terecht niet in de HTML.
const dynamisch = [...new Set([...html.matchAll(/\.id = '([\w-]+)'/g)].map(m => m[1]))];
const ontbreekt = gebruikt.filter(id => !ids.includes(id) && !dynamisch.includes(id));
ok(ontbreekt.length === 0, 'alle aangeroepen id\'s bestaan of worden in code aangemaakt', ontbreekt.slice(0, 12).join(', '));

console.log('\n' + (fout === 0 ? 'GEEN FOUTEN' : fout + ' FOUT(EN)') + (punt ? ', ' + punt + ' aandachtspunt(en)' : ''));
