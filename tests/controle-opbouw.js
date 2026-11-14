/* controle-opbouw.js — bewaakt de opbouw van het script in golf-score.html.

   Het script is ingedeeld in secties. Functies mogen vrij tussen secties verhuizen:
   JavaScript kent een functiedeclaratie al voordat de eerste regel draait, dus
   waar hij staat maakt voor de werking niets uit. Voor de rest gelden drie regels:

   1. Elke naam op het hoogste niveau komt één keer voor (een tweede functie met
      dezelfde naam zou de eerste stil vervangen).
   2. Alles wat bij het laden iets uitvoert, staat in de sectie OPSTART, de laatste.
      Daar horen ook declaraties waarvan de beginwaarde iets aanroept (zoals
      `const storage = (() => {...})()`). Hun onderlinge volgorde is de volgorde
      waarin de app opstart.
   3. Een gewone declaratie (een getal, tekst, lijst, object, pijlfunctie) staat
      vóór OPSTART, en gebruikt in zijn beginwaarde geen let/const die pas later
      wordt gedeclareerd.

   Gebruik:
     node tests/controle-opbouw.js                  controleert ../golf-score.html
     node tests/controle-opbouw.js --commentaar oud.html
                                                    en bewijst dat alleen commentaar is
                                                    gewijzigd (de code zelf is gelijk)
     node tests/controle-opbouw.js oud.html         en vergelijkt met een eerdere versie:
                                                    dezelfde stukken code (letterlijk),
                                                    alleen in een andere volgorde, de
                                                    opstart in dezelfde volgorde, en de
                                                    HTML buiten het script ongewijzigd.
   APP=/pad/naar/golf-score.html kiest een ander bestand.

   Geen afhankelijkheden: het script wordt hier zelf in stukken gedeeld (strings,
   commentaar, template literals en reguliere expressies worden overgeslagen). */
'use strict';
const fs = require('fs'), path = require('path');

const APP = process.env.APP || path.join(__dirname, '..', 'golf-score.html');

/* ---------- lezen ---------- */
function scriptVan(html) {
  const open = html.indexOf('<script>');
  const dicht = html.lastIndexOf('</script>');
  if (open < 0 || dicht < open) throw new Error('geen <script> gevonden');
  return { voor: html.slice(0, open + 8), code: html.slice(open + 8, dicht), na: html.slice(dicht) };
}

/* ---------- een eenvoudige tokenizer, genoeg om grenzen te vinden ---------- */
const WOORDEN_VOOR_REGEX = new Set(['return', 'typeof', 'instanceof', 'in', 'of', 'new', 'delete', 'void', 'throw', 'case', 'do', 'else', 'yield', 'await']);
function tokens(code) {
  const uit = [];          // {t: soort, v: tekst, s: start, e: eind}
  let i = 0;
  const n = code.length;
  const templStapel = [];  // diepte van { binnen ${ } per open template
  let laatste = null;      // laatste betekenisvolle token
  const regexMag = () => {
    if (!laatste) return true;
    if (laatste.t === 'punct') return !/^[)\]}]$/.test(laatste.v) || laatste.v === '}' && laatste.blokEinde;
    if (laatste.t === 'naam') return WOORDEN_VOOR_REGEX.has(laatste.v);
    return false;
  };
  const push = (t, s, e, extra) => { const tok = Object.assign({ t, v: code.slice(s, e), s, e }, extra || {}); uit.push(tok); if (t !== 'com') laatste = tok; return tok; };
  const leesTemplate = (s) => {           // vanaf een ` of } die een template voortzet
    let j = s + 1;
    while (j < n) {
      const c = code[j];
      if (c === '\\') { j += 2; continue; }
      if (c === '`') { return { e: j + 1, open: false }; }
      if (c === '$' && code[j + 1] === '{') { return { e: j + 2, open: true }; }
      j++;
    }
    throw new Error('template niet afgesloten bij ' + s);
  };
  const accoladeStapel = []; // per { : 'blok' | 'templ'
  while (i < n) {
    const c = code[i];
    if (c === ' ' || c === '\t' || c === '\n' || c === '\r') { i++; continue; }
    if (c === '/' && code[i + 1] === '/') { let j = code.indexOf('\n', i); if (j < 0) j = n; push('com', i, j); i = j; continue; }
    if (c === '/' && code[i + 1] === '*') { const j = code.indexOf('*/', i + 2); if (j < 0) throw new Error('commentaar niet afgesloten'); push('com', i, j + 2); i = j + 2; continue; }
    if (c === '"' || c === "'") {
      let j = i + 1;
      while (j < n && code[j] !== c) { if (code[j] === '\\') j++; j++; }
      push('str', i, j + 1); i = j + 1; continue;
    }
    if (c === '`') {
      const r = leesTemplate(i);
      push('str', i, r.e);
      if (r.open) accoladeStapel.push('templ');
      i = r.e; continue;
    }
    if (c === '}' && accoladeStapel[accoladeStapel.length - 1] === 'templ') {
      accoladeStapel.pop();
      const r = leesTemplate(i);
      push('str', i, r.e);
      if (r.open) accoladeStapel.push('templ');
      i = r.e; continue;
    }
    if (c === '/' && regexMag()) {
      let j = i + 1, klasse = false;
      while (j < n) {
        const d = code[j];
        if (d === '\\') { j += 2; continue; }
        if (d === '[') klasse = true; else if (d === ']') klasse = false;
        else if (d === '/' && !klasse) break;
        else if (d === '\n') throw new Error('regex over een regeleinde bij ' + i);
        j++;
      }
      j++;
      while (j < n && /[a-z]/i.test(code[j])) j++;
      push('regex', i, j); i = j; continue;
    }
    if (/[A-Za-z_$À-￿]/.test(c)) {
      let j = i + 1;
      while (j < n && /[\w$À-￿]/.test(code[j])) j++;
      push('naam', i, j); i = j; continue;
    }
    if (/[0-9]/.test(c) || (c === '.' && /[0-9]/.test(code[i + 1]))) {
      let j = i + 1;
      while (j < n && /[\w.]/.test(code[j])) j++;
      push('getal', i, j); i = j; continue;
    }
    // leestekens; => en ... apart herkennen
    const drie = code.slice(i, i + 3), twee = code.slice(i, i + 2);
    let len = 1;
    if (['...', '===', '!==', '**=', '<<=', '>>=', '>>>', '&&=', '||=', '??='].includes(drie)) len = 3;
    else if (['=>', '==', '!=', '<=', '>=', '&&', '||', '??', '?.', '++', '--', '+=', '-=', '*=', '/=', '%=', '&=', '|=', '^=', '**', '<<', '>>'].includes(twee)) len = 2;
    const v = code.slice(i, i + len);
    if (v === '{') accoladeStapel.push('blok');
    if (v === '}') accoladeStapel.pop();
    const tok = push('punct', i, i + len);
    /* na een } die een blok sluit (functie, if) mag een regex volgen; na een
       } van een objectliteral niet. Op het hoogste niveau is het altijd een blok. */
    if (v === '}') tok.blokEinde = true;
    i += len;
  }
  return uit;
}

/* ---------- het script in stukken op het hoogste niveau ---------- */
/* Een stuk = het commentaar en de witruimte ervóór + de opdracht zelf. Een
   commentaar achter op dezelfde regel als het einde hoort bij die opdracht. */
const SECTIEKOP = /^\/\* =+ (\d+)\. ([^=]+?) =+ \*\/$/;
const INHOUDKOP = /^\/\* =+ INHOUD =+/;
function stukken(code) {
  const toks = tokens(code);
  const uit = [];
  let diepte = 0, start = null, begin = 0, haakjes = 0;
  const sluit = (eind) => {
    // commentaar op dezelfde regel erachter hoort erbij
    let k = eind;
    const regelEind = code.indexOf('\n', k);
    const rest = code.slice(k, regelEind < 0 ? code.length : regelEind);
    const m = rest.match(/^[ \t]*(\/\/.*|\/\*.*?\*\/[ \t]*)$/);
    if (m) k += rest.length;
    uit.push({ tekst: code.slice(begin, k), kern: code.slice(start, k), start, eind: k });
    begin = k; start = null;
  };
  for (let x = 0; x < toks.length; x++) {
    const t = toks[x];
    if (t.t === 'com') {
      if (start === null && (SECTIEKOP.test(t.v) || INHOUDKOP.test(t.v))) {
        uit.push({ kop: true, tekst: code.slice(begin, t.e), kern: t.v, start: t.s, eind: t.e });
        begin = t.e;
      }
      continue;
    }
    if (start === null) start = t.s;
    if (t.t === 'punct') {
      if (t.v === '{' || t.v === '(' || t.v === '[') diepte++;
      else if (t.v === '}' || t.v === ')' || t.v === ']') diepte--;
    }
    if (t.t === 'str' && /\$\{$/.test(t.v)) diepte++;
    if (t.t === 'str' && /^\}/.test(t.v)) diepte--;
    if (diepte !== 0) continue;
    if (t.t === 'punct' && t.v === ';') { sluit(t.e); continue; }
    if (t.t === 'punct' && t.v === '}') {
      // einde van een functie, blok of if/else: klaar tenzij er else/catch/finally/. /( volgt
      const volg = toks.slice(x + 1).find(y => y.t !== 'com');
      const kop = code.slice(start, start + 40);
      const isBlokOpdracht = /^(async\s+)?function\b|^class\b|^if\b|^for\b|^while\b|^try\b|^\{/.test(kop);
      if (isBlokOpdracht && !(volg && volg.t === 'naam' && /^(else|catch|finally)$/.test(volg.v))) {
        if (!(volg && volg.t === 'punct' && /^[.(,;]$/.test(volg.v))) { sluit(t.e); continue; }
      }
    }
  }
  if (start !== null) throw new Error('laatste opdracht niet afgesloten: ' + code.slice(start, start + 80));
  return { stukken: uit, staart: code.slice(begin) };
}

/* ---------- soort van een stuk ---------- */
function soort(stuk) {
  if (stuk.kop) return { soort: 'kop' };
  const k = stuk.kern;
  let m = k.match(/^(?:async\s+)?function\s*\*?\s*([\w$]+)/);
  if (m) return { soort: 'functie', namen: [m[1]] };
  m = k.match(/^(const|let|var)\s/);
  if (m) {
    const d = declaratie(k);
    return { soort: d.vrij ? 'declaratie' : 'opstart', namen: d.namen, soortDecl: m[1], gebruikt: d.gebruikt };
  }
  return { soort: 'opstart', namen: [] };
}
/* Namen en beginwaarden van een declaratie. Vrij = de beginwaarden roepen niets
   aan (geen ( buiten een functie- of pijllichaam, geen new, geen tagged template). */
function declaratie(k) {
  const toks = tokens(k).filter(t => t.t !== 'com');
  const namen = [], gebruikt = [];
  let vrij = true;
  let x = 1;               // na const/let/var
  while (x < toks.length) {
    // naam (of destructurering: dan niet vrij genoemd, om zeker te zijn)
    if (toks[x].t !== 'naam') { vrij = false; break; }
    namen.push(toks[x].v); x++;
    if (toks[x] && toks[x].v === '=') {
      x++;
      // beginwaarde tot een , of ; op diepte 0
      let diepte = 0;
      for (; x < toks.length; x++) {
        const t = toks[x];
        if (diepte === 0 && (t.v === ',' || t.v === ';')) break;
        // een functie- of pijllichaam overslaan: wordt pas later uitgevoerd
        if (t.t === 'naam' && t.v === 'function') {
          while (x < toks.length && toks[x].v !== '{') x++;
          x = sluitend(toks, x); continue;
        }
        if (t.v === '=>') {
          if (toks[x + 1] && toks[x + 1].v === '{') { x = sluitend(toks, x + 1); continue; }
          // pijl met een expressie: tot , of ; of sluitend haakje op deze diepte
          let d2 = 0; x++;
          for (; x < toks.length; x++) {
            const u = toks[x];
            if (/^[({[]$/.test(u.v)) d2++;
            else if (/^[)}\]]$/.test(u.v)) { if (d2 === 0) { x--; break; } d2--; }
            else if (d2 === 0 && (u.v === ',' || u.v === ';')) { x--; break; }
            if (u.t === 'str' && /\$\{$/.test(u.v)) d2++;
            if (u.t === 'str' && /^\}/.test(u.v)) d2--;
          }
          continue;
        }
        if (t.v === '(' && x > 0 && /^[\w$)\]]$|^[\w$]+$/.test(toks[x - 1].v) && toks[x - 1].t !== 'punct' || t.v === '(' && /^[)\]]$/.test(toks[x - 1].v)) vrij = false;
        if (t.v === '(' && toks[x - 1].t === 'punct' && toks[x - 1].v === ')') vrij = false;
        /* new Map() en dergelijke zonder argumenten: een lege verzameling, roept niets
           van de app aan */
        if (t.t === 'naam' && t.v === 'new') {
          const leeg = toks[x + 1] && /^(Map|Set|WeakMap|WeakSet)$/.test(toks[x + 1].v) && toks[x + 2] && toks[x + 2].v === '(' && toks[x + 3] && toks[x + 3].v === ')';
          if (leeg) { x += 3; continue; }
          vrij = false;
        }
        if (t.t === 'str' && toks[x - 1] && toks[x - 1].t === 'naam' && !/^(return|typeof|in|of|case)$/.test(toks[x - 1].v)) vrij = false;
        if (t.v === '(' && toks[x + 1] && toks[x + 1].v === 'function') vrij = false;
        if (t.t === 'naam' && !(toks[x - 1] && (toks[x - 1].v === '.' || toks[x - 1].v === '?.')) && !(toks[x + 1] && toks[x + 1].v === ':' && toks[x - 1] && /^[{,]$/.test(toks[x - 1].v))) gebruikt.push(t.v);
        if (/^[({[]$/.test(t.v)) diepte++;
        else if (/^[)}\]]$/.test(t.v)) diepte--;
        if (t.t === 'str' && /\$\{$/.test(t.v)) diepte++;
        if (t.t === 'str' && /^\}/.test(t.v)) diepte--;
      }
    }
    if (toks[x] && toks[x].v === ',') { x++; continue; }
    break;
  }
  return { namen, vrij, gebruikt };
}
function sluitend(toks, x) {      // x wijst naar {; geeft index van de bijbehorende }
  let d = 0;
  for (; x < toks.length; x++) {
    const t = toks[x];
    if (t.v === '{' ) d++;
    else if (t.v === '}') { d--; if (d === 0) return x; }
    if (t.t === 'str' && /\$\{$/.test(t.v)) d++;
    if (t.t === 'str' && /^\}/.test(t.v)) d--;
  }
  return x;
}

/* ---------- controles ---------- */
let fouten = 0, geslaagd = 0;
function ok(naam, goed, toelichting) {
  if (goed) { geslaagd++; console.log('  OK   ' + naam); }
  else { fouten++; console.log('  FOUT ' + naam + (toelichting ? '  — ' + toelichting : '')); }
}
function analyse(html) {
  const s = scriptVan(html);
  const st = stukken(s.code);
  st.stukken.forEach(x => Object.assign(x, soort(x)));
  return Object.assign(s, st);
}

module.exports = { tokens, stukken, soort, scriptVan, analyse };
if (require.main !== module) return;

const html = fs.readFileSync(APP, 'utf8');
const nu = analyse(html);
const delen = nu.stukken.filter(x => !x.kop);
const koppen = nu.stukken.filter(x => x.kop);
console.log('golf-score.html: ' + delen.filter(x => x.soort === 'functie').length + ' functies, ' +
  delen.filter(x => x.soort === 'declaratie').length + ' declaraties, ' +
  delen.filter(x => x.soort === 'opstart').length + ' opdrachten bij het opstarten, ' +
  koppen.filter(k => SECTIEKOP.test(k.kern)).length + ' secties');

/* 1. elke naam één keer */
{
  const tel = new Map();
  delen.forEach(x => (x.namen || []).forEach(nm => tel.set(nm, (tel.get(nm) || 0) + 1)));
  const dubbel = [...tel].filter(([, c]) => c > 1).map(([nm]) => nm);
  ok('elke naam op het hoogste niveau komt één keer voor', dubbel.length === 0, dubbel.join(', '));
}

/* secties: als er koppen zijn, dan in volgorde, en OPSTART de laatste */
const secties = koppen.filter(k => SECTIEKOP.test(k.kern)).map(k => { const m = k.kern.match(SECTIEKOP); return { nr: +m[1], naam: m[2].trim(), pos: k.start }; });
const opstartKop = secties.find(sc => sc.naam === 'OPSTART');
ok('het script is in secties ingedeeld, met OPSTART als laatste', secties.length > 1 && !!opstartKop);
if (secties.length) {
  ok('de secties zijn genummerd 1, 2, 3, …', secties.every((sc, i) => sc.nr === i + 1), secties.map(sc => sc.nr).join(','));
  ok('OPSTART is de laatste sectie', !!opstartKop && secties[secties.length - 1] === opstartKop);
  const inhoud = koppen.find(k => INHOUDKOP.test(k.kern));
  ok('de inhoudsopgave bovenaan noemt elke sectie, in volgorde', !!inhoud && (() => {
    const genoemd = [...inhoud.kern.matchAll(/^\s*(\d+)\.\s+([A-ZÀ-Ý0-9 ,&'-]+?)(?:\s{2,}.*)?$/gm)].map(m => m[1] + '. ' + m[2].trim());
    return JSON.stringify(genoemd) === JSON.stringify(secties.map(sc => sc.nr + '. ' + sc.naam));
  })(), 'werk de lijst onder INHOUD bij');
}

/* 2. alles wat uitvoert, in OPSTART;  3. declaraties ervoor, zonder latere let/const */
if (opstartKop) {
  const fout = delen.filter(x => x.soort === 'opstart' && x.start < opstartKop.pos);
  ok('alles wat bij het laden iets uitvoert staat in OPSTART', fout.length === 0, fout.map(x => x.kern.slice(0, 60)).join(' | '));
  const laat = delen.filter(x => x.soort === 'declaratie' && x.start > opstartKop.pos);
  ok('gewone declaraties staan vóór OPSTART', laat.length === 0, laat.map(x => x.namen.join(',')).join(' | '));
}
{
  const plek = new Map();
  delen.forEach((x, i) => { if (x.soortDecl && x.soortDecl !== 'var') x.namen.forEach(nm => plek.set(nm, i)); });
  const tdz = [];
  delen.forEach((x, i) => (x.gebruikt || []).forEach(nm => { if (plek.has(nm) && plek.get(nm) > i) tdz.push(x.namen.join(',') + ' gebruikt ' + nm); }));
  ok('geen declaratie gebruikt een let/const die pas later komt', tdz.length === 0, tdz.join(' | '));
}

/* alleen commentaar gewijzigd: de code zonder commentaar is gelijk aan een eerdere versie */
if (process.argv[2] === '--commentaar') {
  const zonder = h => tokens(scriptVan(h).code).filter(t => t.t !== 'com').map(t => t.v).join(' ');
  const oudHtml = fs.readFileSync(process.argv[3], 'utf8');
  ok('alleen commentaar gewijzigd: de code zelf is gelijk aan ' + path.basename(process.argv[3]), zonder(oudHtml) === zonder(html));
}

/* vergelijken met een eerdere versie */
const oudPad = process.argv[2] === '--commentaar' ? null : process.argv[2];
if (oudPad) {
  const oud = analyse(fs.readFileSync(oudPad, 'utf8'));
  const oudDelen = oud.stukken.filter(x => !x.kop);
  const norm = x => x.tekst.replace(/^\s+|\s+$/g, '');
  const telling = l => { const m = new Map(); l.forEach(x => { const k = norm(x); m.set(k, (m.get(k) || 0) + 1); }); return m; };
  const a = telling(oudDelen), b = telling(delen);
  const weg = [...a].filter(([k, c]) => (b.get(k) || 0) < c).map(([k]) => k.split('\n').find(r => r.trim() && !/^\s*(\/\/|\/\*|\*)/.test(r)) || k.slice(0, 60));
  const bij = [...b].filter(([k, c]) => (a.get(k) || 0) < c).map(([k]) => k.split('\n').find(r => r.trim() && !/^\s*(\/\/|\/\*|\*)/.test(r)) || k.slice(0, 60));
  ok('dezelfde stukken code, letterlijk, met hun commentaar (' + oudDelen.length + ')', weg.length === 0 && bij.length === 0,
     (weg.length ? 'weg/anders: ' + weg.slice(0, 5).map(r => r.trim().slice(0, 70)).join(' | ') : '') + (bij.length ? '  nieuw/anders: ' + bij.slice(0, 5).map(r => r.trim().slice(0, 70)).join(' | ') : ''));
  const opstartOud = oudDelen.filter(x => x.soort === 'opstart').map(norm);
  const opstartNu = delen.filter(x => x.soort === 'opstart').map(norm);
  ok('de opstart in dezelfde volgorde (' + opstartOud.length + ' opdrachten)', JSON.stringify(opstartOud) === JSON.stringify(opstartNu));
  ok('de HTML vóór het script is ongewijzigd', oud.voor === nu.voor);
  ok('de HTML na het script is ongewijzigd', oud.na === nu.na);
  ok('niets na de laatste opdracht verdwenen', oud.staart.trim() === nu.staart.trim());
}

/* de slotregel in de vorm die run-alles.py herkent */
console.log('\n' + (fouten ? fouten + ' fout(en), ' + geslaagd + ' geslaagd' : 'GEEN FOUTEN (' + geslaagd + ' controles geslaagd)'));
process.exitCode = fouten ? 1 : 0;
