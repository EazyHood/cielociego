"""Convierte docs/post.md en docs/post.html.

Deliberadamente sin librerias de markdown: el fichero fuente lo controlo yo y
solo usa parrafos, titulos, enlaces, enfasis, codigo en linea y una regla.
Meter una dependencia para eso seria peor que las treinta lineas de aqui.

La composicion es la contraria a la del informe. El informe es un tablero: va
por bloques, cifras grandes y color semantico. Esto es un articulo largo, y ahi
el diseno tiene que quitarse de en medio -- cuerpo en serif, una columna
estrecha, sin cajas ni insignias, y que la tipografia haga el trabajo.
"""
from __future__ import annotations

import html
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[1]
ORIGEN = RAIZ / "docs" / "post.md"
DESTINO = RAIZ / "docs" / "post.html"

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
.hoja{max-width:37rem; margin:0 auto; padding:clamp(2.5rem,7vw,6rem) 1.4rem 6rem}

.tira{
  font-family:"IBM Plex Sans",system-ui,sans-serif; font-size:.72rem;
  letter-spacing:.14em; text-transform:uppercase; color:var(--tinta-suave);
  margin:0 0 1.4rem; display:flex; gap:.6rem; flex-wrap:wrap;
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
p+p{text-indent:0}
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
  font-family:"IBM Plex Sans",system-ui,sans-serif; font-size:.86rem;
  line-height:1.6; color:var(--tinta-suave);
}
.pie p{margin:0 0 .9rem}
a:focus-visible{outline:2px solid var(--acento); outline-offset:3px}
@media (max-width:480px){ body{font-size:18px} .hoja{padding-top:2rem} }
"""


def en_linea(t: str) -> str:
    """Enfasis, codigo y enlaces. El orden importa: el codigo va primero."""
    piezas: list[str] = []

    def guarda(m: re.Match[str]) -> str:
        piezas.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(piezas) - 1}\x00"

    t = re.sub(r"`([^`]+)`", guarda, t)
    t = html.escape(t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
    return re.sub(r"\x00(\d+)\x00", lambda m: piezas[int(m.group(1))], t)


def convierte(md: str) -> tuple[str, str]:
    """Devuelve (titulo, cuerpo html)."""
    titulo, cuerpo, parrafo = "", [], []

    def cierra() -> None:
        if parrafo:
            cuerpo.append(f"<p>{en_linea(' '.join(parrafo))}</p>")
            parrafo.clear()

    for linea in md.split("\n"):
        s = linea.rstrip()
        if not s:
            cierra()
        elif s.startswith("# "):
            cierra()
            titulo = s[2:].strip()
            cuerpo.append(f"<h1>{en_linea(titulo)}</h1>")
        elif s.startswith("## "):
            cierra()
            cuerpo.append(f"<h2>{en_linea(s[3:].strip())}</h2>")
        elif s.strip() == "---":
            cierra()
            cuerpo.append("<hr>")
        else:
            parrafo.append(s.strip())
    cierra()
    return titulo, "\n".join(cuerpo)


def main() -> None:
    titulo, cuerpo = convierte(ORIGEN.read_text(encoding="utf-8"))

    # La primera parrafada tras el h1 hace de entradilla.
    partes = cuerpo.split("</h1>", 1)
    if len(partes) == 2:
        resto = partes[1].lstrip("\n")
        primero, _, cola = resto.partition("</p>")
        cuerpo = (partes[0] + "</h1>\n"
                  + primero.replace("<p>", '<p class="entradilla">', 1) + "</p>\n" + cola)

    DESTINO.write_text(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(titulo)} — cielociego</title>
<meta name="description" content="Sentinel-2 passes every five days. On two fields in the Colombian Caribbean, 89% and 91% of days had no usable view at all. What that means, and what radar can do about it.">
<meta property="og:title" content="{html.escape(titulo)}">
<meta property="og:description" content="Sentinel-2 passes every five days. On two fields in the Colombian Caribbean, 89% and 91% of days had no usable view at all.">
<meta property="og:type" content="article">
<meta property="og:url" content="https://eazyhood.github.io/cielociego/post.html">
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&family=IBM+Plex+Sans:wght@400;500&family=IBM+Plex+Mono:wght@400&display=swap">
<style>{CSS}</style>
</head>
<body>
<article class="hoja">
<p class="tira">
  <a href="./">Full report</a>
  <a href="https://github.com/EazyHood/cielociego">Code</a>
  <a href="https://doi.org/10.5281/zenodo.22132250">DOI</a>
</p>
{cuerpo}
</article>
</body>
</html>
""", encoding="utf-8")
    print(f"docs/post.html escrito: {DESTINO.stat().st_size // 1024} KB · «{titulo}»")


if __name__ == "__main__":
    main()
