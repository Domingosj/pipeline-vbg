"""Configuração central do pipeline ETL de indicadores de VBG."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── Credenciais (nunca escrever valores aqui — só ler do ambiente) ──────────
ACTIVITYINFO_TOKEN = os.environ.get("ACTIVITYINFO_TOKEN")
DATABASE_URL       = os.environ.get("DATABASE_URL")
PSEUDONYM_SALT     = os.environ.get("PSEUDONYM_SALT", "")

FORM_ID = "ck0nbfrmg0iku4c1hdk"
API_URL = f"https://www.activityinfo.org/resources/query/v43/form/{FORM_ID}"

# ── Limiares de validação ───────────────────────────────────────────────────
# Um pipeline que "corre bem" e traz zero registos é mais perigoso do que um
# que falha, porque passa despercebido. Abaixo deste número, aborta.
MIN_REGISTOS_ESPERADOS = 1000

# ── Campos que NUNCA saem da extracção ──────────────────────────────────────
# Texto livre narrativo sobre incidentes de VBG. Sem uso analítico e é a
# informação mais sensível do sistema. Descartado assim que a resposta chega,
# antes de qualquer transformação, persistência ou registo em log.
CAMPOS_EXCLUIDOS = [
    # Narrativa do incidente
    "Descrição  do incidente",
    "Relato do incidente / Descrição do incidente",
    "Porque não",
    "Que medidas foram tomadas para garantir a segurança do sobrevivente?",
    "Outra medida tomada",
    "Ficha inicial de acompanhamento Psicossocial",
    # NOMES DE PESSOAS — nunca saem da extracção
    "Nome do Beneficiario/a",          # nome da sobrevivente
    "nome_gestor",                     # objecto do gestor (a variante .Name é pseudonimizada)
    "Quem esta a Gerir o Caso",
    # Texto livre que pode conter elementos identificáveis
    "Detalhes da referencia:",
    "Detalhes da referência",
    "Detalhes da referência:",
    "Especifcique o motivo de encerramento",
    "Especifica",
    "Especificar",
]

# O estado emocional é usado no cálculo do risco mas não é armazenado:
# entra no cálculo e é descartado, guardando-se apenas a pontuação.
CAMPO_ESTADO_EMOCIONAL = "Descreva o estado emocional do sobrevivente no início da entrevista:"

# ── Mapeamento ActivityInfo → nomes internos ────────────────────────────────
COLUMN_MAP = {
    "_id":                                                        "record_id",
    "_lastEditTime":                                              "last_edit_time",
    "ID do Incidente":                                            "case_id",
    "Qual projeto":                                               "project",
    "Parceiro":                                                   "partner",
    "nome_gestor.Name":                                           "_case_manager_nome",  # pseudonimizado
    "data_incident":                                              "incident_date",
    "data_identf":                                                "identification_date",
    "data_entrev":                                                "interview_date",
    "Data do encerramento":                                       "closure_date",
    "Faixa etaria da sobrevivente":                               "age_group",
    "sexo":                                                       "sex",
    "Estado Civil":                                               "marital_status",
    "Pessoa com deficiência":                                     "disability",
    "Necessidades específicas / Vulnerabilidades":                "vulnerabilities",
    "distrito.Province.name":                                     "province",
    "distrito.Name":                                              "district",
    "País de origem do sobrevivente":                             "origin_country",
    "tipo_viol":                                                  "violence_type",
    "Número de alegado(s) perpetrador(es)":                       "perpetrator_count",
    "sexo_do_alegado_prepetrador":                                "perpetrator_sex",
    "Idade":                                                      "perpetrator_age",
    "Relação do alegado perpetrador com o sobrevivente":          "perpetrator_relationship",
    "Foi sobrevivente encaminhado para uma casa/abrigo seguro?":  "referred_safe_house",
    "O sobrevivente foi encaminhado para serviços médicos?":      "referred_medical",
    "O sobrevivente foi encaminhado para serviços psicossociais?":"referred_psychosocial",
    "O sobrevivente foi encaminhado para um serviço de polícia/segurança?": "referred_police",
    "O sobrevivente foi encaminhado para serviços jurídicos?":    "referred_legal",
    "O sobrevivente foi encaminhado para serviços de protecção de menores?": "referred_child_protection",
    "O sobrevivente foi encaminhado para serviços de subsistência?": "referred_livelihood",
    "Data de encaminhado para uma casa/abrigo seguro":            "date_referred_safe_house",
    "Data de encaminhamento para serviçoes médicos":              "date_referred_medical",
    "Data de encaminhado para serviços psicossociais":            "date_referred_psychosocial",
    "Data de encaminhado para um serviço de polícia/segurança":   "date_referred_police",
    "Será que o sobrevivente estará seguro quando ele ou ela partir?": "is_safe",
    "Estado do caso":                                             "case_status",
    "Motivos do encerramento":                                    "closure_reason",
    "O Caso foi Validado":                                        "validated",
    "Consentimento":                                              "consent",
    "Proveniencia":                                               "source",
    "Gostaria de dar seguimento ao caso?":                        "wants_followup",
    "O sobrevivente relatou este incidente em algum outro lugar?":"reported_elsewhere",
    "O sobrevivente teve algum incidente anterior de VBG perpetrado contra ele?": "previous_incident",
    "Quem lhe encaminhou este sobrevivente?":                     "referred_by",

    # ── Acrescentados a 7 Set 2026 após inspecção dos campos da fonte ──────
    # Risco atribuído pelo ActivityInfo — referência externa para validar o
    # technical_risk_score calculado pelo pipeline
    "Nível de Risco":                                             "source_risk_level",
    "Nível de Risco Actual do Caso":                              "source_risk_level_current",

    # Consentimento da sobrevivente (relevante para a secção de ética)
    "O sobrevivente deu o seu consentimento para partilhar os seus dados não identificáveis nos seus relatórios?": "consent_share_data",

    # Características do incidente
    "Este incidente foi uma prática tradicional nociva?":         "harmful_traditional_practice",
    "Houve troca de dinheiro, bens, benefícios e/ou serviços em relação a este incidente?": "transactional_exchange",
    "Período do dia do Incidente":                                "incident_time_of_day",
    "local_incid":                                                "incident_location",

    # Deslocamento — central no contexto de Cabo Delgado
    "Etapa de deslocamento no momento do incidente":              "displacement_stage_incident",
    "Estado do deslocamento no momento do relatório":             "displacement_status_report",

    # Perfil
    "O/A Sobrevivente  é Chefe do Agregado?":                     "head_of_household",
    "Ocupação principal do alegado perpetrador":                  "perpetrator_occupation",

    # Encaminhamento e seguimento
    "O sobrevivente foi encaminhado para receber NFIs (Produtos não alimentares)?": "referred_nfi",
    "Chegada Confirmada ao Serviço?":                             "service_arrival_confirmed",
    "Data do Encaminhamento":                                     "referral_date",
    "Data da Validacão":                                          "validation_date",
    "Ha necessidade de um proximo seguimento?":                   "needs_followup",
    "Data do proximo Segmento":                                   "next_followup_date",

    # Resultado
    "Os objectivos do Plano de Acção foram alcançados?":          "action_plan_achieved",
    "No geral, quão satisfeito/a o cliente ficou com os serviços  recebidos durante a gestão de casos?": "client_satisfaction",
}

# Colunas da tabela public.casos, pela ordem do INSERT
COLUNAS_BD = [
    "record_id", "case_id", "last_edit_time", "project", "partner", "case_manager_ref",
    "incident_date", "identification_date", "interview_date", "closure_date",
    "age_group", "age_band", "sex", "marital_status", "disability", "vulnerabilities",
    "province", "district", "origin_country",
    "violence_type", "violence_type_short",
    "perpetrator_count", "perpetrator_sex", "perpetrator_age", "perpetrator_relationship",
    "referred_safe_house", "referred_medical", "referred_psychosocial", "referred_police",
    "referred_legal", "referred_child_protection", "referred_livelihood",
    "date_referred_safe_house", "date_referred_medical",
    "date_referred_psychosocial", "date_referred_police",
    "is_safe", "case_status", "closure_reason", "validated", "consent", "source",
    "wants_followup", "reported_elsewhere", "previous_incident", "referred_by",
    "days_to_closure", "days_since_id", "is_open_over_90d",
    "has_any_referral", "referral_count", "referral_types", "possible_service_gap",
    "technical_risk_score", "operational_priority",
    "data_quality_score", "data_quality_issues",
    # acrescentados a 7 Set 2026
    "source_risk_level", "source_risk_level_current", "consent_share_data",
    "harmful_traditional_practice", "transactional_exchange",
    "incident_time_of_day", "incident_location",
    "displacement_stage_incident", "displacement_status_report",
    "head_of_household", "perpetrator_occupation",
    "referred_nfi", "service_arrival_confirmed",
    "referral_date", "validation_date",
    "needs_followup", "next_followup_date",
    "action_plan_achieved", "client_satisfaction",
]

CAMPOS_DATA = [
    "incident_date", "identification_date", "interview_date", "closure_date",
    "date_referred_safe_house", "date_referred_medical",
    "date_referred_psychosocial", "date_referred_police",
    "referral_date", "validation_date", "next_followup_date",
]
