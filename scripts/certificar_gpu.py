"""Kit de certificación en GPU para las tres funciones de IA de ia-api.

Uso:
  python scripts/certificar_gpu.py --salida CARPETA [--rapido] [--omitir FASE ...] [--simulado]
  python scripts/certificar_gpu.py --cerrar CARPETA
"""
import argparse
from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.certificacion.infra import RelojSimulado, TelemetriaSimulada
from scripts.certificacion.kit import Kit
from scripts.certificacion.simulado import servir_simulado
from scripts.certificacion.veredicto import cerrar


def imprimir_tabla(informe):
    criterios = informe.get("criterios", {})
    perfiles = informe.get("perfiles", {})
    print("\n" + "=" * 80)
    print(f"VEREDICTO GLOBAL: {informe.get('veredicto_global', 'PENDIENTE')}")
    print("=" * 80)
    print(f"{'Criterio':<10} | {'Estado':<14} | {'Umbral'}")
    print("-" * 80)
    for k, v in criterios.items():
        print(f"{k:<10} | {v.get('estado', ''):<14} | {v.get('umbral', '')}")
    print("-" * 80)
    print(f"{'Perfil':<10} | {'Veredicto':<14}")
    print("-" * 80)
    for p, v in perfiles.items():
        print(f"{p:<10} | {v.get('estado', ''):<14}")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Kit de certificación en GPU de ia-api.")
    parser.add_argument("--salida", type=str, help="Carpeta de salida (debe estar vacía y fuera del repositorio)")
    parser.add_argument("--cerrar", type=str, help="Cerrar certificación leyendo hojas CSV marcadas en la carpeta")
    parser.add_argument("--rapido", action="store_true", help="Modo rápido sin esperas sostenidas (nunca APTO global)")
    parser.add_argument("--omitir", nargs="*", default=(), help="Fases a omitir (nunca APTO global)")
    parser.add_argument("--simulado", action="store_true", help="Usar Ollama y telemetría simulados (para pruebas)")
    args = parser.parse_args()

    if args.cerrar:
        carpeta = Path(args.cerrar).resolve()
        if not carpeta.exists():
            parser.error(f"La carpeta '{args.cerrar}' no existe.")
        print(f"Cerrando certificación en {carpeta}...")
        informe = cerrar(carpeta)
        imprimir_tabla(informe)
        return 0

    if not args.salida:
        parser.error("Debe especificar --salida CARPETA o --cerrar CARPETA.")

    carpeta = Path(args.salida).resolve()
    print(f"Iniciando certificación con salida en: {carpeta}")
    if args.simulado:
        print("Modo simulado activo (sin GPU real).")
        with servir_simulado() as sim:
            reloj = RelojSimulado() if args.rapido else None
            telemetria = TelemetriaSimulada(sim)
            kit = Kit(carpeta, rapido=args.rapido, omitir=args.omitir, simulado=sim,
                      reloj=reloj, telemetria=telemetria, progreso=print)
            informe = kit.ejecutar()
    else:
        kit = Kit(carpeta, rapido=args.rapido, omitir=args.omitir, progreso=print)
        informe = kit.ejecutar()

    imprimir_tabla(informe)
    print(f"Archivos generados en {carpeta}:")
    print("  - informe.json")
    print("  - informe.md")
    print("  - revision_paciente.csv")
    print("  - revision_whatsapp.csv")
    print("\nPara completar la certificación, revise los CSV y ejecute:")
    print(f"  python scripts/certificar_gpu.py --cerrar \"{carpeta}\"")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
