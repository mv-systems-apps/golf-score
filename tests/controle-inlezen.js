const fs = require('fs');
const html = fs.readFileSync(process.env.APP || require('path').join(__dirname, '..', 'golf-score.html'), 'utf8');
const js = (html.match(/<script[^>]*>([\s\S]*)<\/script>/) || [])[1];
const functieVan = i => {
  const m = [...js.slice(0, i).matchAll(/^(?:async\s+)?function\s+([\w$]+)/gm)];
  return m.length ? m[m.length - 1][1] : '(top)';
};

// Zoek voor elke JSON.parse het OMHULLENDE try-blok door haakjes te tellen
function omhullendeTry(pos) {
  let diepte = 0;
  for (let i = pos; i > 0; i--) {
    const c = js[i];
    if (c === '}') diepte++;
    else if (c === '{') {
      if (diepte === 0) {
        const voor = js.slice(Math.max(0, i - 60), i);
        if (/\btry\s*$/.test(voor)) {
          // bijbehorende catch zoeken
          let d = 0;
          for (let j = i; j < js.length; j++) {
            if (js[j] === '{') d++;
            else if (js[j] === '}') { d--; if (d === 0) {
              const na = js.slice(j, j + 260);
              const m = na.match(/^\}\s*catch\s*\([^)]*\)\s*\{([\s\S]{0,200})/);
              return m ? m[1] : null;
            } }
          }
          return null;
        }
        return omhullendeTry(i - 1);
      }
      diepte--;
    }
  }
  return null;
}

console.log('ELK PUNT WAAR DE APP EEN BESTAND OF DE OPSLAG INLEEST:\n');
[...js.matchAll(/JSON\.parse\(/g)].forEach(m => {
  const naam = functieVan(m.index);
  const catchInhoud = omhullendeTry(m.index);
  let oordeel;
  if (catchInhoud === null) oordeel = 'GEEN AFVANG — een stuk bestand laat de functie halverwege stoppen';
  else if (/showInfoModal|showStatus|showStartError|alert/.test(catchInhoud)) oordeel = 'melding aan de gebruiker';
  else if (/return|=/.test(catchInhoud)) oordeel = 'stille terugval (' + catchInhoud.trim().split('\n')[0].slice(0, 46) + ')';
  else oordeel = 'lege afvang';
  console.log('  ' + naam.padEnd(26) + oordeel);
});
