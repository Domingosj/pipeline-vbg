# Pipeline ETL — Indicadores de VBG

Extrai casos de VBG do ActivityInfo, transforma-os e carrega-os numa base
PostgreSQL alojada no Supabase, que serve de fonte ao dashboard Power BI.

Componente técnica do TCC do MBA Data Science & Analytics, USP/Esalq.

## Arquitectura

```
ActivityInfo ──> Python ──> PostgreSQL (Supabase) ──> Power BI
                    │
            GitHub Actions, 8×/dia
```

Carga total a cada execução, com upsert por `record_id`. Registos que
desaparecem da fonte são marcados como inactivos, não eliminados.

## Módulos

| Ficheiro | Função |
|---|---|
| `etl/config.py` | Configuração, mapeamento de campos, campos excluídos |
| `etl/extract.py` | Chamada à API, repetição com recuo, validação da resposta |
| `etl/transform.py` | Limpeza, classificação etária, risk score, pseudonimização |
| `etl/tests.py` | Testes de qualidade antes da carga |
| `etl/load.py` | Upsert em PostgreSQL, soft delete, registo de execuções |
| `etl/pipeline.py` | Orquestra os quatro passos |

## Correr localmente

```bash
cp .env.example .env      # preencher os três valores
pip install -r requirements.txt
cd etl && python pipeline.py
```

## Automação

`.github/workflows/pipeline.yml` corre oito vezes por dia e pode ser
accionado à mão no separador **Actions**.

Segredos necessários no repositório (Settings → Secrets and variables → Actions):
`ACTIVITYINFO_TOKEN`, `DATABASE_URL`, `PSEUDONYM_SALT`.

## Protecção de dados

- Texto livre narrativo sobre incidentes é descartado na extracção e nunca
  persistido: descrição do incidente, relato, motivo de insegurança e medidas
  de segurança.
- O estado emocional entra no cálculo do risco e é descartado; guarda-se
  apenas a pontuação.
- O nome do gestor de casos é substituído por um identificador pseudonimizado.
- O Power BI consome apenas vistas agregadas, nunca a tabela de casos.
- Repositório privado. Segredos apenas em variáveis de ambiente.
