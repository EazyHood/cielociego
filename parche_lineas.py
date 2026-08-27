"""Declara en el informe y el README la incertidumbre por linea de procesado."""
import pathlib

# ---------------------------------------------------------------- INFORME
p = pathlib.Path("herramientas/construye_html.py")
s = p.read_text(encoding="utf-8")

ANCLA = '''    <p class="nota"><b>Una toma se perdió.</b>'''
NUEVO = '''    <p class="nota"><b>La máscara de nubes es un modelo, y los modelos se actualizan.</b> El
    archivo sirve muchas tomas bajo dos versiones del procesador, y no siempre coinciden.
    Comparadas 61 de ellas sobre el polígono: <b>el 80 % son idénticas al bit</b>; el 20 % restante
    difiere una media del 6,7 % del predio, y en un caso —el 29-nov-2021— una versión daba el
    predio despejado y la otra lo daba <b>71,8 % tapado</b>, sobre la misma toma. <b>El 6,6 % de
    las tomas cruza el umbral de utilidad</b>, y siempre en el mismo sentido: la versión nueva
    marca más nube. Como aquí se usa siempre la más alta, <b>lo que se publica es la estimación
    conservadora</b>: más días ciegos de los que declararía el procesador antiguo, no menos.</p>
    <p class="nota"><b>Una toma se perdió.</b>'''
assert ANCLA in s
s = s.replace(ANCLA, NUEVO, 1)

# El titular aguanta cualquier definicion: eso hay que decirlo.
ANCLA2 = '''      <p class="nota"><b>Dos decisiones que mueven los números, y por eso se declaran.</b>'''
NUEVO2 = '''      <p class="nota"><b>Y el titular aguanta cualquier definición de «nube».</b> Contar como
      ciega solo la nube segura —ignorando la nube probable, el cirro fino y la sombra, que es lo
      más generoso que se puede defender— deja el resultado en <b>82 % y 84 % de días ciegos</b>.
      Con la definición estricta son 89 % y 91 %. La conclusión no vive de dónde se ponga la raya.</p>
      <p class="nota"><b>Dos decisiones que mueven los números, y por eso se declaran.</b>'''
assert ANCLA2 in s
s = s.replace(ANCLA2, NUEVO2, 1)
p.write_text(s, encoding="utf-8")
print("informe: incertidumbre de linea + robustez de definicion")

# ----------------------------------------------------------------- README
p = pathlib.Path("README.md")
s = p.read_text(encoding="utf-8")

ANCLA3 = "- **Una toma se perdió.**"
NUEVO3 = """- **La máscara de nubes es un modelo, y los modelos se actualizan.** El archivo
  sirve muchas tomas bajo dos versiones del procesador, y no siempre coinciden.
  Comparadas 61 sobre el polígono:

  ```
  identicas al bit ................................. 80 %
  difieren ......................................... 20 %   (|dif| media 6,7 %)
  CRUZAN el umbral de utilidad ..................... 6,6 %
     y siempre en el mismo sentido: la version nueva marca MAS nube
     (36 tomas utiles con la vieja, 32 con la nueva)

  el peor caso medido, 2021-11-29, misma toma:
     linea N0301 -> predio  0,0 % tapado
     linea N0500 -> predio 71,8 % tapado
  ```

  Como se usa siempre la línea más alta, **lo publicado es la estimación
  conservadora**: más días ciegos de los que declararía el procesador antiguo.
  Reproducible con `dedup.pares_de_lineas`.
- **El titular aguanta cualquier definición de «nube».** Contando como ciega
  solo la nube segura —ignorando nube probable, cirro y sombra, lo más generoso
  que se puede defender— quedan **82 % y 84 % de días ciegos**, frente al 89 % y
  91 % de la definición estricta. La conclusión no vive de dónde se ponga la raya.
- **Una toma se perdió.**"""
assert ANCLA3 in s
s = s.replace(ANCLA3, NUEVO3, 1)
s = s.replace("144 pruebas, sin red", "189 pruebas, sin red")
s = s.replace("67 pruebas, sin red", "189 pruebas, sin red")
s = s.replace("# 144 pruebas", "# 189 pruebas")
s = s.replace("# 67 pruebas", "# 189 pruebas")
s = s.replace("144 pruebas, 91 % de cobertura", "189 pruebas, 92 % de cobertura")
p.write_text(s, encoding="utf-8")
print("README: incertidumbre de linea + robustez de definicion")
