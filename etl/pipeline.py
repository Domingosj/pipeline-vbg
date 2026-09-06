#!/usr/bin/env python3
"""Pipeline ETL — Indicadores de VBG | GCR Moçambique

Extrai do ActivityInfo, transforma e carrega em PostgreSQL (Supabase).
Cada execução é registada em public.etl_execucoes.

    python pipeline.py

Requer ACTIVITYINFO_TOKEN e DATABASE_URL no ambiente (.env ou GitHub Secrets).
"""
import os
import sys
import time
from datetime import datetime

import extract
import load
import tests
import transform


def main() -> int:
    inicio = time.time()
    accionado_por = "github-actions" if os.environ.get("GITHUB_ACTIONS") else "manual"

    print("=" * 66)
    print("ETL — Indicadores de VBG | GCR Moçambique")
    print(f"Início: {datetime.now():%Y-%m-%d %H:%M:%S}  ({accionado_por})")
    print("=" * 66)

    conn = load.ligar()
    conn.autocommit = False
    exec_id = None

    try:
        exec_id = load.iniciar_execucao(conn, accionado_por)
        conn.commit()
        print(f"\nExecução #{exec_id} registada.")

        # 1 — Extracção
        print("\n[1/4] Extracção do ActivityInfo...")
        t = time.time()
        brutos = extract.fetch_raw()
        extract.validar_resposta(brutos)
        print(f"      {len(brutos)} registos em {time.time()-t:.1f}s")

        # 2 — Transformação
        print("\n[2/4] Transformação e enriquecimento...")
        t = time.time()
        registos = transform.transform_all(brutos)
        print(f"      {len(registos)} registos em {time.time()-t:.1f}s")

        # 3 — Testes de qualidade
        print("\n[3/4] Testes de qualidade...")
        avisos = tests.validar(registos)
        qualidade = tests.qualidade_media(registos)
        for a in avisos:
            print(f"      [aviso] {a}")
        print(f"      Qualidade média dos dados: {qualidade}%")

        # 4 — Carga
        print("\n[4/4] Carga em PostgreSQL...")
        t = time.time()
        r = load.carregar(conn, registos)
        print(f"      inseridos {r['inseridos']} | actualizados {r['actualizados']} "
              f"| inactivados {r['inactivados']}  ({time.time()-t:.1f}s)")

        load.fechar_execucao(
            conn, exec_id, estado="SUCESSO",
            extraidos=len(brutos), inseridos=r["inseridos"],
            actualizados=r["actualizados"], inactivados=r["inactivados"],
            qualidade=qualidade,
        )
        conn.commit()

        print("\n" + "=" * 66)
        print(f"Concluído em {time.time()-inicio:.1f}s")
        print("=" * 66)
        return 0

    except Exception as e:
        conn.rollback()
        print(f"\n[ERRO] {type(e).__name__}: {e}", file=sys.stderr)
        if exec_id is not None:
            try:
                load.fechar_execucao(conn, exec_id, estado="FALHA", erro=f"{type(e).__name__}: {e}")
                conn.commit()
            except Exception as e2:
                print(f"[ERRO] não foi possível registar a falha: {e2}", file=sys.stderr)
        return 1

    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
