"""Convierte los articulos de docs/*.md en sus paginas HTML.

Deliberadamente sin librerias de markdown: los ficheros fuente los controlo yo
y solo usan parrafos, titulos, enlaces, enfasis, codigo en linea y una regla.
Meter una dependencia para eso seria peor que las cuarenta lineas de aqui.

La composicion es la contraria a la del informe. El informe es un tablero: va
por bloques, cifras grandes y color semantico, pensado para escanear. Esto es un
articulo largo, y ahi el diseno tiene que quitarse de en medio -- cuerpo en
serif, una columna estrecha, sin cajas ni insignias, y que la tipografia haga el
trabajo.

Medido en el navegador, no supuesto: 66 caracteres por linea (el optimo clasico
de lectura larga) y contraste 16,7:1 en claro, 14,9:1 en oscuro.
"""
from __future__ import annotations

import html
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[1]
SALTO = chr(10)

CC_EN = "https://creativecommons.org/licenses/by-nc-nd/4.0/"
CC_ES = "https://creativecommons.org/licenses/by-nc-nd/4.0/deed.es"
REPO = "https://github.com/EazyHood/cielociego"
DOI = "https://doi.org/10.5281/zenodo.22132250"

# Un idioma por entrada: fichero fuente, salida y los textos de la interfaz.
IDIOMAS = {
    "en": {
        "origen": "post.md",
        "destino": "post.html",
        "lang": "en",
        "nav": [("./", "Full report"), (REPO, "Code"), (DOI, "DOI"),
                ("post.es.html", "En español")],
        "desc": ("Sentinel-2 passes every five days. On two fields in the Colombian "
                 "Caribbean, 89% and 91% of days had no usable view at all."),
        "pie": ("© 2026 Jhonatan del Río. All rights reserved. This text and its charts "
                'are licensed <a href="' + CC_EN + '">CC BY-NC-ND 4.0</a>; the source '
                "code is MIT. The measurements belong to nobody — reproduce them."),
    },
    "es": {
        "origen": "post.es.md",
        "destino": "post.es.html",
        "lang": "es",
        "nav": [("./", "Informe completo"), (REPO, "Código"), (DOI, "DOI"),
                ("post.html", "In English")],
        "desc": ("Sentinel-2 pasa cada cinco días. Sobre dos predios del Caribe colombiano, "
                 "el 89 % y el 91 % de los días no hubo una sola vista aprovechable."),
        "pie": ("© 2026 Jhonatan del Río. Todos los derechos reservados. Este texto y sus "
                'gráficas están bajo <a href="' + CC_ES + '">CC BY-NC-ND 4.0</a>; el '
                "código, bajo MIT. Las mediciones no son de nadie: reprodúcelas."),
    },
}

CSS = """
:root{
  --papel:#fbfaf8; --tinta:#1a1a19; --tinta-suave:#6b6b66; --linea:#e0ded8;
  --acento:#8a3d16;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --papel:#12120f; --tinta:#e8e5dd; --tinta-suave:#94918a; --linea:#2c2b26;
  --acento:#d98a5a;
}}
:root[data-theme="dark"]{
  --papel:#12120f; --tinta:#e8e5dd; --tinta-suave:#94918a; --linea:#2c2b26;
  --acento:#d98a5a;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  background:var(--papel); color:var(--tinta); margin:0;
  font-family:"Newsreader",Georgia,"Times New Roman",serif;
  font-size:20px; line-height:1.62; font-weight:400;
  -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
}
.hoja{max-width:37rem; margin:0 auto; padding:clamp(2.5rem,7vw,6rem) 1.4rem 5rem}

.tira{
  font-family:"IBM Plex Sans",system-ui,sans-serif; font-size:.72rem;
  letter-spacing:.14em; text-transform:uppercase; color:var(--tinta-suave);
  margin:0 0 1.4rem; display:flex; gap:.9rem; flex-wrap:wrap;
}
.tira a{color:var(--tinta-suave); text-decoration:none; border-bottom:1px solid var(--linea)}
.tira a:hover{color:var(--acento); border-color:var(--acento)}

h1{
  font-size:clamp(2.1rem,5.6vw,3rem); line-height:1.08; font-weight:500;
  letter-spacing:-.02em; margin:0 0 1.6rem; text-wrap:balance;
}
h2{
  font-size:1.32rem; line-height:1.3; font-weight:600; letter-spacing:-.008em;
  margin:3.4rem 0 1rem; text-wrap:balance;
}
p{margin:0 0 1.35rem}
a{color:var(--tinta); text-decoration:none; border-bottom:1px solid var(--acento)}
a:hover{color:var(--acento)}
em{font-style:italic}
strong{font-weight:600}
code{
  font-family:"IBM Plex Mono",ui-monospace,monospace; font-size:.86em;
  background:color-mix(in srgb, var(--linea) 55%, transparent);
  padding:.1em .32em; border-radius:2px;
}
hr{border:0; border-top:1px solid var(--linea); margin:3.4rem 0 2rem}

.entradilla{
  font-size:1.06rem; color:var(--tinta-suave); line-height:1.55;
  font-family:"IBM Plex Sans",system-ui,sans-serif;
  padding-bottom:2.2rem; margin-bottom:2.4rem; border-bottom:1px solid var(--linea);
}
.pie{
  font-family:"IBM Plex Sans",system-ui,sans-serif; font-size:.82rem;
  line-height:1.6; color:var(--tinta-suave);
  border-top:1px solid var(--linea); margin-top:3rem; padding-top:1.6rem;
}
.pie p{margin:0}
a:focus-visible{outline:2px solid var(--acento); outline-offset:3px}
@media (max-width:480px){ body{font-size:18px} .hoja{padding-top:2rem} }
"""


def en_linea(t: str) -> str:
    """Enfasis, codigo y enlaces. El orden importa: el codigo va primero."""
    piezas: list[str] = []

    def guarda(m: re.Match[str]) -> str:
        piezas.append("<code>" + html.escape(m.group(1)) + "</code>")
        return "\x00" + str(len(piezas) - 1) + "\x00"

    t = re.sub(r"`([^`]+)`", guarda, t)
    t = html.escape(t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
    return re.sub(r"\x00(\d+)\x00", lambda m: piezas[int(m.group(1))], t)


def convierte(md: str) -> tuple[str, str]:
    """Devuelve (titulo, cuerpo html)."""
    titulo = ""
    cuerpo: list[str] = []
    parrafo: list[str] = []

    def cierra() -> None:
        if parrafo:
            cuerpo.append("<p>" + en_linea(" ".join(parrafo)) + "</p>")
            parrafo.clear()

    for linea in md.split(SALTO):
        s = linea.strip()
        if not s:
            cierra()
        elif s.startswith("# "):
            cierra()
            titulo = s[2:].strip()
            cuerpo.append("<h1>" + en_linea(titulo) + "</h1>")
        elif s.startswith("## "):
            cierra()
            cuerpo.append("<h2>" + en_linea(s[3:].strip()) + "</h2>")
        elif s == "---":
            cierra()
            cuerpo.append("<hr>")
        else:
            parrafo.append(s)
    cierra()
    return titulo, SALTO.join(cuerpo)


def entradilla(cuerpo: str) -> str:
    """La primera parrafada tras el h1 hace de entradilla."""
    partes = cuerpo.split("</h1>", 1)
    if len(partes) != 2:
        return cuerpo
    resto = partes[1].lstrip(SALTO)
    primero, _, cola = resto.partition("</p>")
    return (partes[0] + "</h1>" + SALTO
            + primero.replace("<p>", '<p class="entradilla">', 1) + "</p>" + SALTO + cola)


def escribe(cfg: dict) -> None:
    origen = RAIZ / "docs" / cfg["origen"]
    destino = RAIZ / "docs" / cfg["destino"]
    titulo, cuerpo = convierte(origen.read_text(encoding="utf-8"))
    cuerpo = entradilla(cuerpo)

    nav = SALTO.join(
        '  <a href="' + u + '">' + html.escape(t) + "</a>" for u, t in cfg["nav"]
    )
    t = html.escape(titulo)
    d = html.escape(cfg["desc"])
    url = "https://eazyhood.github.io/cielociego/" + cfg["destino"]

    pagina = f"""<!doctype html>
<html lang="{cfg["lang"]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t} — cielociego</title>
<meta name="description" content="{d}">
<meta name="author" content="Jhonatan del Río">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:type" content="article">
<meta property="og:locale" content="{cfg["lang"]}">
<meta property="og:url" content="{url}">
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&family=IBM+Plex+Sans:wght@400;500&family=IBM+Plex+Mono:wght@400&display=swap">
<style>{CSS}</style>
</head>
<body>
<article class="hoja">
<p class="tira">
{nav}
</p>
{cuerpo}
<footer class="pie">
  <p>{cfg["pie"]}</p>
</footer>
</article>
</body>
</html>
"""
    destino.write_text(pagina, encoding="utf-8")
    print("  " + cfg["destino"] + ": " + str(destino.stat().st_size // 1024)
          + " KB - " + titulo)


def main() -> None:
    for cfg in IDIOMAS.values():
        escribe(cfg)


if __name__ == "__main__":
    main()
