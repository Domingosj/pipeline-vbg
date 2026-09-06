"""Transformação e enriquecimento.

Mantém a lógica validada na Fase 4 (classificação etária, risk score,
prioridade operacional, lacunas de encaminhamento, índice de qualidade),
acrescentando pseudonimização do gestor de casos.
"""
import hashlib
from datetime import date, datetime, timezone

import config

# ── Tipo de violência ───────────────────────────────────────────────────────
VIOLENCE_SHORT_MAP = {
    "violacao": "Violação", "violação": "Violação",
    "agressao sexual": "Agressão Sexual", "agressão sexual": "Agressão Sexual",
    "agressao fisica": "Agressão Física", "agressão física": "Agressão Física",
    "abuso psicologico": "Abuso Psicológico", "abuso psicológico": "Abuso Psicológico",
    "casamento forcado": "Casamento Forçado", "casamento forçado": "Casamento Forçado",
    "negacao de recursos": "Negação de Recursos", "negação de recursos": "Negação de Recursos",
}

VIOLENCE_RISK_WEIGHTS = {
    "Violação": 10, "Agressão Sexual": 8, "Agressão Física": 7,
    "Casamento Forçado": 6, "Abuso Psicológico": 5, "Negação de Recursos": 4,
}

AGE_BANDS = [
    ("10-14", ["10 - 14"]), ("15-19", ["15 - 19"]), ("20-24", ["20 - 24"]),
    ("25-49", ["25 - 49"]), ("50+", ["49+", "50+"]),
]

REFERRAL_COLS = [
    "referred_safe_house", "referred_medical", "referred_psychosocial",
    "referred_police", "referred_legal", "referred_child_protection",
    "referred_livelihood",
]

CAMPOS_CRITICOS = [
    "case_id", "violence_type", "identification_date", "age_group", "sex", "district",
]


def _sim(v) -> bool:
    return str(v).strip().lower() in ("sim", "yes", "true", "1")


def fmt_violence(v):
    if not v:
        return None
    vl = str(v).lower().strip()
    for chave, rotulo in VIOLENCE_SHORT_MAP.items():
        if chave in vl:
            return rotulo
    return v


def classify_age(age_group):
    if not age_group:
        return "Desconhecido"
    for rotulo, padroes in AGE_BANDS:
        if any(p in str(age_group) for p in padroes):
            return rotulo
    return "Desconhecido"


def parse_date(val):
    if val in (None, "", "NaT"):
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(val)[:len(fmt) + 2].strip(), fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00")).date()
    except Exception:
        return None


def parse_epoch_ms(val):
    """_lastEditTime vem da API como epoch em milissegundos."""
    if val in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(val) / 1000, tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def pseudonimizar(nome) -> str | None:
    """Substitui o nome do gestor por um identificador estável e não reversível.

    O sal vive numa variável de ambiente; sem ele o valor não é atribuível a
    ninguém. Permite análise de carga de trabalho sem armazenar nomes.
    """
    if not nome:
        return None
    bruto = f"{config.PSEUDONYM_SALT}::{str(nome).strip().lower()}"
    return "GC-" + hashlib.sha256(bruto.encode()).hexdigest()[:10].upper()


def compute_risk_score(linha: dict, estado_emocional: str | None) -> int:
    """Pontuação 0-100. O estado emocional entra no cálculo mas não é guardado."""
    score = VIOLENCE_RISK_WEIGHTS.get(linha.get("violence_type_short"), 4) / 10 * 40

    if linha.get("age_band") in ("10-14", "15-19"):
        score += 20
    if str(linha.get("is_safe", "")).strip().lower() in ("não", "nao", "no"):
        score += 20
    if estado_emocional and any(
        p in str(estado_emocional).lower() for p in ("pânico", "panico", "suicid", "terror", "dissoc")
    ):
        score += 10
    if _sim(linha.get("disability")):
        score += 5
    if _sim(linha.get("previous_incident")):
        score += 5

    return min(int(score), 100)


def compute_priority(score: int) -> str:
    if score >= 85: return "CRÍTICO"
    if score >= 65: return "ALTO"
    if score >= 40: return "MÉDIO"
    return "BAIXO"


def transform_row(bruto: dict) -> dict:
    """Um registo da API → um registo pronto para a base de dados."""
    linha = {}
    for origem, destino in config.COLUMN_MAP.items():
        if origem in bruto:
            linha[destino] = bruto[origem]

    # O estado emocional é lido mas nunca armazenado
    estado_emocional = bruto.get(config.CAMPO_ESTADO_EMOCIONAL)

    # Pseudonimização do gestor
    linha["case_manager_ref"] = pseudonimizar(linha.pop("_case_manager_nome", None))

    # Datas
    for campo in config.CAMPOS_DATA:
        linha[campo] = parse_date(linha.get(campo))
    linha["last_edit_time"] = parse_epoch_ms(linha.get("last_edit_time"))

    # Classificações
    linha["violence_type_short"] = fmt_violence(linha.get("violence_type"))
    linha["age_band"] = classify_age(linha.get("age_group"))

    # Tempos
    hoje = date.today()
    d_id, d_fecho = linha.get("identification_date"), linha.get("closure_date")
    linha["days_to_closure"] = (d_fecho - d_id).days if d_fecho and d_id else None
    linha["days_since_id"] = (hoje - d_id).days if d_id else None
    linha["is_open_over_90d"] = bool(
        str(linha.get("case_status", "")).strip().lower() == "aberto"
        and linha["days_since_id"] is not None
        and linha["days_since_id"] > 90
    )

    # Encaminhamentos
    encaminhados = [c for c in REFERRAL_COLS if _sim(linha.get(c))]
    linha["has_any_referral"] = len(encaminhados) > 0
    linha["referral_count"] = len(encaminhados)
    linha["referral_types"] = "; ".join(c.replace("referred_", "") for c in encaminhados)

    # Lacuna crítica: violação ou agressão sexual sem encaminhamento médico
    linha["possible_service_gap"] = bool(
        linha.get("violence_type_short") in ("Violação", "Agressão Sexual")
        and not _sim(linha.get("referred_medical"))
    )

    # Risco
    linha["technical_risk_score"] = compute_risk_score(linha, estado_emocional)
    linha["operational_priority"] = compute_priority(linha["technical_risk_score"])

    # Qualidade
    em_falta = [c for c in CAMPOS_CRITICOS if not linha.get(c)]
    linha["data_quality_score"] = round((1 - len(em_falta) / len(CAMPOS_CRITICOS)) * 100, 1)
    linha["data_quality_issues"] = "; ".join(em_falta)

    return {c: linha.get(c) for c in config.COLUNAS_BD}


def transform_all(brutos: list[dict]) -> list[dict]:
    return [transform_row(r) for r in brutos]
