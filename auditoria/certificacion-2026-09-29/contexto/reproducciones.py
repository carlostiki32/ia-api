"""Reejecuta expectativas independientes sin sobrescribir auditorias previas."""
from pathlib import Path
import contextlib,importlib.util,io,logging,runpy,sys
ROOT=Path(__file__).resolve().parents[3]
AUDIT=ROOT/'auditoria/conformidad-2026-09-29/contexto'

def controles_actuales():
    anterior=list(sys.path)
    sys.path.insert(0,str(AUDIT))
    import comun
    capturas={}
    persistir_anterior=comun.persistir
    nivel_anterior=logging.root.manager.disable
    try:
        comun.persistir=lambda n,d,m,f:capturas.update({n:d})
        logging.disable(logging.WARNING)
        with contextlib.redirect_stdout(io.StringIO()):
            for script in ('20_repro.py','21_repro.py','22_23_repro.py','42_repro.py','43_48_repro.py','49_52_repro.py','53_repro.py','54_57_repro.py'):
                runpy.run_path(str(AUDIT/script))
    finally:
        comun.persistir=persistir_anterior
        logging.disable(nivel_anterior)
        sys.path[:]=anterior
    return capturas
