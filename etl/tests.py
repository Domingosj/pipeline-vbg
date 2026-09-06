"""Testes de qualidade dos dados.

Correm entre a transformação e a carga. Um problema estrutural aborta a carga;
uma anomalia de conteúdo é registada como aviso.
"""
from collections import Counter


class FalhaDeQualidade(Exception):
    pass


def validar(registos: list[dict]) -> list[str]:
    """Devolve a lista de avisos. Levanta FalhaDeQualidade em erros graves."""
    avisos = []
    n = len(registos)
    if n == 0:
        raise FalhaDeQualidade("Nenhum registo após a transformação.")

    # ── Erros graves: abortam a carga ───────────────────────────────────────
    sem_id = [r for r in registos if not r.get("record_id")]
    if sem_id:
        raise FalhaDeQualidade(f"{len(sem_id)} registos sem record_id — chave em falta.")

    ids = [r["record_id"] for r in registos]
    duplicados = [i for i, c in Counter(ids).items() if c > 1]
    if duplicados:
        raise FalhaDeQualidade(
            f"{len(duplicados)} record_id duplicados (ex.: {duplicados[:3]})."
        )

    # ── Avisos: registados, não bloqueiam ───────────────────────────────────
    sem_tipo = sum(1 for r in registos if not r.get("violence_type_short"))
    if sem_tipo:
        avisos.append(f"{sem_tipo} registos sem tipo de violência ({sem_tipo/n:.1%})")

    sem_data = sum(1 for r in registos if not r.get("identification_date"))
    if sem_data:
        avisos.append(f"{sem_data} registos sem data de identificação ({sem_data/n:.1%})")

    sem_distrito = sum(1 for r in registos if not r.get("district"))
    if sem_distrito:
        avisos.append(f"{sem_distrito} registos sem distrito ({sem_distrito/n:.1%})")

    prioridades_validas = {"CRÍTICO", "ALTO", "MÉDIO", "BAIXO"}
    invalidas = {r.get("operational_priority") for r in registos} - prioridades_validas
    if invalidas:
        avisos.append(f"prioridades inesperadas: {invalidas}")

    fora_escala = sum(
        1 for r in registos
        if r.get("technical_risk_score") is not None
        and not (0 <= r["technical_risk_score"] <= 100)
    )
    if fora_escala:
        avisos.append(f"{fora_escala} risk scores fora do intervalo 0-100")

    lacunas = sum(1 for r in registos if r.get("possible_service_gap"))
    avisos.append(f"{lacunas} casos com lacuna de encaminhamento médico ({lacunas/n:.1%})")

    return avisos


def qualidade_media(registos: list[dict]) -> float:
    vals = [r["data_quality_score"] for r in registos if r.get("data_quality_score") is not None]
    return round(sum(vals) / len(vals), 1) if vals else 0.0
