"""Comprobación temporal de córners y tarjetas con datos reales."""
from datetime import date

import esquinas

e = esquinas.Esquinas(date.today())
for liga, l, v in (("SP1", "Real Madrid", "Barcelona"), ("SP1", "Getafe", "Osasuna"), ("E0", "Man City", "Arsenal"),
                   ("E0", "Burnley", "Brentford"), ("I1", "Inter", "Milan"), ("D1", "Bayern Munich", "Dortmund")):
    ps = e.picks(liga, l, v)
    m = e._modelos(liga)
    if m:
        cl, cv = m[0].esperado(l, v) if m[0].conoce(l) and m[0].conoce(v) else (0, 0)
        tl, tv = m[1].esperado(l, v) if m[1].conoce(l) and m[1].conoce(v) else (0, 0)
        print(f"{liga} {l} - {v}: córners esp. {cl:.1f}+{cv:.1f}, tarjetas esp. {tl:.1f}+{tv:.1f}")
    print("   ", [(k.mercado, round(k.prob * 100)) for k in ps if k.mercado.startswith("Más")])
