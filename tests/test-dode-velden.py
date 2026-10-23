"""Geen verborgen invoervelden die alleen worden gevuld en nooit gelezen.

Statisch, op golf-score.html. Een verborgen veld (style="display:none") dat de app
alleen een waarde geeft maar nergens leest, is dood gewicht: het suggereert dat er
iets van afhangt, en een volgende wijziging houdt het voor niets bij. Zo stond
iDateTime er, 'voor achterwaartse compatibiliteit' met niets.

De regel: van elk verborgen <input id="..."> wordt de waarde ergens gelezen, dus
er is een .value die geen toekenning is (.value =).
"""
import os, re, sys
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from testdata import app_map
html = open(os.path.join(app_map(), 'golf-score.html'), encoding='utf-8').read()
fouten = []
verborgen = re.findall(r'<input\b[^>]*\bid="([^"]+)"[^>]*display:\s*none', html)
print(f"verborgen invoervelden: {len(verborgen)}")
for veld in verborgen:
    # Elke plek waar het veld wordt opgehaald, en wat er direct achter staat.
    gelezen = False
    plekken = list(re.finditer(r"""getElementById\(['"]%s['"]\)""" % re.escape(veld), html))
    for m in plekken:
        if re.match(r'\s*\.value\s*=(?!=)', html[m.end():m.end() + 20]):
            continue                                   # alleen gevuld
        var = re.search(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:document\.)?$', html[max(0, m.start() - 60):m.start()])
        if var:
            # In een variabele gezet: kijk wat er daarna met die variabele gebeurt.
            naam = var.group(1)
            rest = html[m.end():m.end() + 400]
            # Niet binnen een tekst tussen aanhalingstekens ('hidden' als klassenaam).
            gebruik = re.findall(r'(?<![\'"\w-])%s\b(?![\'"])(\s*\.value\s*=(?!=)|\s*\))?' % re.escape(naam), rest)
            if all(g for g in gebruik):                # alleen 'if (x)' en 'x.value ='
                continue
        gelezen = True
    ok = gelezen
    print(f" {' ok ' if ok else 'FOUT'}  {veld}: {len(plekken)} keer opgehaald, {'gelezen' if gelezen else 'nooit gelezen'}")
    if not ok: fouten.append(veld)
print("\n" + ("GEEN FOUTEN" if not fouten else f"{len(fouten)} FOUT(EN)"))
sys.exit(1 if fouten else 0)
