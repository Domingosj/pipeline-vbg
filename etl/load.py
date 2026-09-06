"""Carga em PostgreSQL (Supabase).

Estratégia: carga total com upsert por record_id, dentro de uma única
transacção. Registos que deixaram de existir na fonte são marcados como
inactivos em vez de eliminados, preservando o histórico.
"""
import psycopg2
from psycopg2.extras import execute_values

import config


def ligar():
    if not config.DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL não definido. Obtenha a string de ligação em "
            "Supabase → Settings → Database → Connection string (porta 5432)."
        )
    return psycopg2.connect(config.DATABASE_URL)


def iniciar_execucao(conn, accionado_por: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "insert into public.etl_execucoes (accionado_por, estado) "
            "values (%s, 'EM_CURSO') returning id",
            (accionado_por,),
        )
        return cur.fetchone()[0]


def fechar_execucao(conn, exec_id: int, *, estado: str, extraidos=None,
                    inseridos=None, actualizados=None, inactivados=None,
                    qualidade=None, erro=None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            update public.etl_execucoes
               set terminado_em      = now(),
                   duracao_segundos  = extract(epoch from (now() - iniciado_em)),
                   estado            = %s,
                   registos_extraidos    = %s,
                   registos_inseridos    = %s,
                   registos_actualizados = %s,
                   registos_inactivados  = %s,
                   qualidade_media       = %s,
                   mensagem_erro         = %s
             where id = %s
            """,
            (estado, extraidos, inseridos, actualizados, inactivados,
             qualidade, (erro or "")[:2000] or None, exec_id),
        )


def carregar(conn, registos: list[dict]) -> dict:
    """Upsert de todos os registos e soft-delete dos ausentes. Uma transacção."""
    colunas = config.COLUNAS_BD
    valores = [tuple(r.get(c) for c in colunas) for r in registos]
    ids_actuais = [r["record_id"] for r in registos]

    lista_cols = ", ".join(colunas)
    # Na colisão actualiza tudo excepto a chave, e reactiva o registo
    atribuicoes = ", ".join(
        f"{c} = excluded.{c}" for c in colunas if c != "record_id"
    )

    with conn.cursor() as cur:
        cur.execute("select count(*) from public.casos where activo")
        antes_activos = cur.fetchone()[0]

        cur.execute("select record_id from public.casos")
        ids_existentes = {r[0] for r in cur.fetchall()}

        execute_values(
            cur,
            f"""
            insert into public.casos ({lista_cols})
            values %s
            on conflict (record_id) do update
               set {atribuicoes},
                   extraido_em = now(),
                   activo      = true
            """,
            valores,
            page_size=500,
        )

        # Soft delete: o que existia e já não vem da fonte
        cur.execute(
            "update public.casos set activo = false "
            "where activo and not (record_id = any(%s))",
            (ids_actuais,),
        )
        inactivados = cur.rowcount

    novos = len([i for i in ids_actuais if i not in ids_existentes])
    return {
        "inseridos": novos,
        "actualizados": len(ids_actuais) - novos,
        "inactivados": inactivados,
        "antes_activos": antes_activos,
    }
