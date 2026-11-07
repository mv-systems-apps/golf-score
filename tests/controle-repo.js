const fs = require('fs');
const lees = p => { try { return fs.readFileSync('/home/claude/' + p, 'utf8'); } catch (e) { return null; } };
const html = lees('golf-score.html');
const idx = lees('index.html');
const sw = lees('sw-golf-score.js');
const py = lees('update_cache_version.py');
const man = JSON.parse(lees('/mnt/user-data/uploads/manifest.json') || fs.readFileSync('/mnt/user-data/uploads/manifest.json', 'utf8'));
let fout = 0, punt = 0;
const ok = (g, t, d) => { if (!g) fout++; console.log((g ? '  ok  ' : ' FOUT ') + t + (d ? ' → ' + d : '')); };
const let_op = t => { punt++; console.log(' let op ' + t); };

console.log('=== 1. SERVICE WORKER: ÉÉN NAAM OVERAL ===');
const regApp = (html.match(/serviceWorker\.register\('([^']+)'\)/) || [])[1];
const regIdx = (idx.match(/serviceWorker\.register\('([^']+)'\)/) || [])[1];
const swInPy = (py.match(/SW_FILE = DIR \/ '([^']+)'/) || [])[1];
ok(regApp === './sw-golf-score.js', 'golf-score.html registreert', regApp);
ok(regIdx === './sw-golf-score.js', 'index.html registreert', regIdx);
ok(swInPy === 'sw-golf-score.js', 'update_cache_version.py bewerkt', swInPy);
ok(regApp === regIdx, 'beide pagina\'s registreren dezelfde service worker');
[['golf-score.html', html], ['index.html', idx], ['sw-golf-score.js', sw], ['update_cache_version.py', py]]
  .forEach(([naam, inh]) => ok(!/['"\/ ]sw\.js/.test(inh.replace(/sw-golf-score\.js/g, '')), 'geen oude naam in ' + naam));

console.log('\n=== 2. BESTANDSLIJSTEN GELIJK ===');
const swFiles = [...(sw.match(/const APP_FILES = \[([\s\S]*?)\];/) || [])[1].matchAll(/'([^']+)'/g)].map(m => m[1].replace(/^\.\//, ''));
const pyFiles = [...(py.match(/APP_FILES = \[([^\]]*)\]/) || [])[1].matchAll(/'([^']+)'/g)].map(m => m[1]);
console.log('  service worker : ' + swFiles.join(', '));
console.log('  hash-script    : ' + pyFiles.join(', '));
const alleenSw = swFiles.filter(f => f && f !== '' && !pyFiles.includes(f));
const alleenPy = pyFiles.filter(f => !swFiles.includes(f));
ok(alleenSw.length === 0 || (alleenSw.length === 1 && alleenSw[0] === ''), 'geen bestand dat alleen de service worker kent', alleenSw.filter(Boolean).join(', '));
ok(alleenPy.length === 0, 'geen bestand dat alleen het hash-script kent', alleenPy.join(', '));

console.log('\n=== 3. MANIFEST ===');
ok(man.start_url === './golf-score.html', 'start_url wijst naar de app', man.start_url);
ok(man.scope === './', 'scope omvat de hele map', man.scope);
const manIcons = [...new Set(man.icons.map(i => i.src.replace(/^\.\//, '')))];
console.log('  iconen in het manifest: ' + manIcons.join(', '));
const iconsMissend = manIcons.filter(i => !swFiles.includes(i));
ok(iconsMissend.length === 0, 'alle manifest-iconen staan in de cachelijst', iconsMissend.join(', '));

console.log('\n=== 4. INDEX ALS INSTAPPUNT ===');
ok(/url=\.\/golf-score\.html/.test(idx), 'doorverwijzing zonder JavaScript aanwezig');
ok(/location\.replace\('\.\/golf-score\.html'\)/.test(idx), 'doorverwijzing met JavaScript aanwezig');
ok(/rel="manifest" href="\.\/manifest\.json"/.test(idx), 'index verwijst naar het manifest');
ok(!/rel="manifest"/.test(html) || true, 'app zelf: manifest-verwijzing ' + (/rel="manifest"/.test(html) ? 'aanwezig' : 'ontbreekt'));
if (!/rel="manifest"/.test(html)) let_op('golf-score.html heeft zelf geen manifest-verwijzing; bij installeren vanaf die pagina valt de PWA terug op de standaardwaarden');

console.log('\n=== 5. KLEUREN EN NAMEN ===');
const themaIdx = (idx.match(/name="theme-color" content="([^"]+)"/) || [])[1];
ok(themaIdx === man.theme_color, 'theme-color gelijk in index en manifest', themaIdx + ' / ' + man.theme_color);
const titelIdx = (idx.match(/<title>([^<]+)<\/title>/) || [])[1];
ok(titelIdx === man.name, 'titel gelijk aan manifest-naam', titelIdx + ' / ' + man.name);

console.log('\n=== 6. OFFLINE-GEDRAG ===');
const fallback = (sw.match(/req\.mode === 'navigate'\) return caches\.match\('([^']+)'\)/) || [])[1];
ok(fallback === './golf-score.html', 'offline terugval', fallback);
ok(swFiles.includes('index.html') && swFiles.includes('golf-score.html'), 'beide pagina\'s worden gecacht');

console.log('\n' + (fout === 0 ? 'GEEN FOUTEN' : fout + ' FOUT(EN)') + (punt ? ', ' + punt + ' aandachtspunt(en)' : ''));
