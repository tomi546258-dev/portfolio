#!/usr/bin/env python3
"""
Portfólió-ellenőrző — futtasd a repó gyökerében, feltöltés ELŐTT:

    python ellenorzes.py

Csak a Python alapkönyvtárát használja, nem kell hozzá telepíteni semmit.
Azokat a hibákat keresi, amelyek a böngészőben NÉMÁN törnek el: a lap
betöltődik, csak épp egy canvas üres marad vagy a nyelvváltó nem csinál semmit.
"""
import html
import json
import os
import re
import sys
from collections import Counter

HIBA, FIGYELEM = [], []


def hiba(f, msg):
    HIBA.append(f"{f}: {msg}")


def figyelem(f, msg):
    FIGYELEM.append(f"{f}: {msg}")


def szoveg_tagek_nelkul(s):
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", s, flags=re.S | re.I)
    return re.sub(r"<[^>]+>", " ", s)


def ellenoriz(f):
    nyers = open(f, encoding="utf-8").read()
    # A HTML-kommentek nem futnak: a bennük lévő hivatkozás nem hiányzó fájl.
    s = re.sub(r"<!--.*?-->", " ", nyers, flags=re.S)

    # 1. Csonka fájl — pontosan ez volt az index.html baja
    if "<html" in nyers.lower() and "</html>" not in nyers.lower():
        hiba(f, "a fájl csonka: nincs </html> záró tag")
    for tag in ("script", "style", "body"):
        nyit = len(re.findall(rf"<{tag}\b", s, re.I))
        zar = len(re.findall(rf"</{tag}>", s, re.I))
        if nyit != zar:
            hiba(f, f"<{tag}> párosítás: {nyit} nyitó, {zar} záró")

    # 2. Duplikált id — ettől a getElementById rossz elemet talál,
    #    a canvas üres marad, a csúszó nem reagál
    idk = re.findall(r'\bid="([^"]+)"', s)
    for azon, db in Counter(idk).items():
        if db > 1:
            hiba(f, f'duplikált id="{azon}" ({db}x)')

    # 3. Hivatkozott helyi fájlok léteznek-e
    konyvtar = os.path.dirname(os.path.abspath(f)) or "."
    for url in re.findall(r'(?:src|href)="(?!https?:|//|#|mailto:|data:)([^"]+)"', s):
        util = url.split("?")[0].split("#")[0]
        if util and not os.path.exists(os.path.join(konyvtar, util)):
            hiba(f, f"hiányzó hivatkozott fájl: {util}")

    # 4. JSON-LD érvényessége
    for blokk in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', s, re.S):
        try:
            json.loads(blokk)
        except Exception as e:
            hiba(f, f"hibás JSON-LD: {e}")

    # 5. i18n szótár
    m = re.search(r"const\s+(?:T|TRANS|translations)\s*=\s*\{", s)
    if not m:
        return
    blokk = s[m.start():]
    veg = blokk.find("\n};")
    if veg == -1:
        veg = blokk.find("\n    };")
    blokk = blokk[: veg + 4] if veg != -1 else blokk

    kulcsok = set(re.findall(r'data-i18n="([^"]+)"', s))
    hatarok = {mm.group(1): mm.start() for mm in re.finditer(r"[\n{]\s*(hu|en|de)\s*:\s*\{", blokk)}
    sorrend = sorted(hatarok.items(), key=lambda kv: kv[1])
    if not sorrend:
        return

    for i, (nyelv, kezd) in enumerate(sorrend):
        veg2 = sorrend[i + 1][1] if i + 1 < len(sorrend) else len(blokk)
        resz = blokk[kezd:veg2]
        megvan = set(re.findall(r'"([\w.]+)"\s*:', resz))
        hianyzo = kulcsok - megvan
        if hianyzo:
            hiba(f, f"[{nyelv}] hiányzó fordítás ({len(hianyzo)}): {', '.join(sorted(hianyzo)[:6])}")

        # 5b. Szótárértékbe ragadt szerkezeti HTML.
        #     Ez okozta a bojler-szimuláció némajegy hibáját: a magyar
        #     pattern.lambda kulcsba belekerült fél oldalnyi markup,
        #     benne egy MÁSODIK <canvas id="boiler-canvas"> elemmel.
        for kulcs, ertek in re.findall(r'"([\w.]+)"\s*:\s*"((?:[^"\\]|\\.)*)"', resz):
            if re.search(r"\bid=\\?\"", ertek):
                hiba(f, f'[{nyelv}] "{kulcs}" id="..." attribútumot tartalmaz — '
                        f"duplikált id-t injektál betöltéskor")
            elif re.search(r"<(canvas|script|section|nav|footer|input)\b", ertek, re.I):
                hiba(f, f'[{nyelv}] "{kulcs}" szerkezeti HTML-t tartalmaz')
            elif len(ertek) > 1500:
                figyelem(f, f'[{nyelv}] "{kulcs}" gyanúsan hosszú ({len(ertek)} karakter)')

    # 6. MathJax-őr: a <head>-beli MathJax = {...} csak konfiguráció,
    #    a typesetPromise csak a könyvtár betöltése után létezik
    if re.search(r"if\s*\(\s*window\.MathJax\s*\)\s*MathJax\.typesetPromise", s):
        hiba(f, "nem biztonságos MathJax-hívás — lassú vagy blokkolt CDN-nél "
                "kivételt dob és megszakítja az indítási láncot")


def main():
    fajlok = sorted(x for x in os.listdir(".") if x.endswith(".html"))
    if not fajlok:
        print("Nincs .html fájl ebben a könyvtárban. A repó gyökerében futtasd.")
        return 1
    for f in fajlok:
        ellenoriz(f)

    print(f"Ellenőrizve: {len(fajlok)} oldal\n")
    for sor in FIGYELEM:
        print("  figyelem:", sor)
    for sor in HIBA:
        print("  HIBA:    ", sor)
    if not HIBA and not FIGYELEM:
        print("  Minden rendben — mehet a feltöltés.")
    elif not HIBA:
        print("\n  Hiba nincs, csak figyelmeztetés.")
    else:
        print(f"\n  {len(HIBA)} hiba — ezeket javítsd feltöltés előtt.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
