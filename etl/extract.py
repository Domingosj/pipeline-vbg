"""Extracção — ActivityInfo API REST.

Carga total: extrai todos os registos a cada execução. À escala deste projecto
(~1.600 registos) demora segundos e trata correctamente edições tardias e
eliminações, que uma carga incremental perderia.
"""
import base64
import time
import requests

import config


def _headers() -> dict:
    if not config.ACTIVITYINFO_TOKEN:
        raise RuntimeError(
            "ACTIVITYINFO_TOKEN não definido. Defina-o no .env (local) "
            "ou nos GitHub Secrets (automação)."
        )
    auth = base64.b64encode(f"user:{config.ACTIVITYINFO_TOKEN}".encode()).decode()
    return {"Authorization": f"Basic {auth}"}


def _descartar_campos_sensiveis(registos: list[dict]) -> list[dict]:
    """Remove texto livre narrativo imediatamente após a recepção.

    Corre antes de qualquer transformação, escrita ou log, para que estes
    campos não sejam persistidos em lado nenhum do sistema.
    """
    for r in registos:
        for campo in config.CAMPOS_EXCLUIDOS:
            r.pop(campo, None)
    return registos


def fetch_raw(max_retries: int = 3, timeout: int = 60) -> list[dict]:
    """Extrai todos os registos, com repetição e recuo exponencial."""
    ultima_excepcao = None
    for tentativa in range(max_retries):
        try:
            resp = requests.get(config.API_URL, headers=_headers(), timeout=timeout)
            resp.raise_for_status()
            dados = resp.json()
            if not isinstance(dados, list):
                raise ValueError(f"Resposta inesperada da API: {type(dados)}")
            return _descartar_campos_sensiveis(dados)
        except Exception as e:
            ultima_excepcao = e
            if tentativa == max_retries - 1:
                break
            espera = 2 ** tentativa
            print(f"  [aviso] tentativa {tentativa+1}/{max_retries} falhou: {e}")
            print(f"  [aviso] a aguardar {espera}s antes de repetir...")
            time.sleep(espera)
    raise RuntimeError(f"Extracção falhou após {max_retries} tentativas") from ultima_excepcao


def validar_resposta(dados: list[dict]) -> None:
    """Falha ruidosamente em vez de carregar dados vazios ou de formato errado."""
    if not dados:
        raise ValueError("A API devolveu zero registos.")

    if len(dados) < config.MIN_REGISTOS_ESPERADOS:
        raise ValueError(
            f"Apenas {len(dados)} registos extraídos, abaixo do mínimo esperado "
            f"({config.MIN_REGISTOS_ESPERADOS}). Possível token expirado, alteração "
            f"de permissões ou formulário errado. Carga abortada."
        )

    esperados = ["ID do Incidente", "tipo_viol", "Estado do caso", "distrito.Name", "data_identf"]
    amostra = dados[0]
    if not any(c in amostra for c in esperados):
        raise ValueError(
            f"Formato inesperado. Campos recebidos: {list(amostra.keys())[:8]}"
        )

    # Evolução de esquema: avisar sem falhar
    conhecidos = set(config.COLUMN_MAP) | set(config.CAMPOS_EXCLUIDOS) | {config.CAMPO_ESTADO_EMOCIONAL}
    novos = set(amostra) - conhecidos
    if novos:
        print(f"  [aviso] campos novos na fonte, não mapeados: {sorted(novos)}")
