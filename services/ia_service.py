import json
import re

from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

from config import (
    AI_PROVIDER,
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    GEMINI_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
)


def _resolver_cliente():
    provider = (AI_PROVIDER or "openai").lower()

    if provider == "openrouter":
        if not OPENROUTER_API_KEY:
            return None, OPENROUTER_MODEL, "OPENROUTER_API_KEY", "OpenRouter"
        return (
            OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL),
            OPENROUTER_MODEL,
            "OPENROUTER_API_KEY",
            "OpenRouter",
        )

    if provider == "gemini":
        if not GEMINI_API_KEY:
            return None, GEMINI_MODEL, "GEMINI_API_KEY", "Gemini"
        return (
            OpenAI(api_key=GEMINI_API_KEY, base_url=GEMINI_BASE_URL),
            GEMINI_MODEL,
            "GEMINI_API_KEY",
            "Gemini",
        )

    if provider == "ollama":
        return (
            OpenAI(api_key="ollama", base_url=OLLAMA_BASE_URL),
            OLLAMA_MODEL,
            "N/A",
            "Ollama",
        )

    if not OPENAI_API_KEY:
        return None, OPENAI_MODEL, "OPENAI_API_KEY", "OpenAI"
    return OpenAI(api_key=OPENAI_API_KEY), OPENAI_MODEL, "OPENAI_API_KEY", "OpenAI"


def _to_float(value, default=0.0):
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return float(default)


def _clamp(value, lower=0, upper=100):
    return max(lower, min(upper, int(round(_to_float(value)))))


def _normalizar_prioridade(prioridade):
    prioridade_txt = str(prioridade or "").strip().lower()
    if prioridade_txt in ("alta", "critica", "urgente", "critical", "high", "1"):
        return "alta"
    if prioridade_txt in ("media", "medium", "2"):
        return "media"
    return "baixa"


def _situacao_por_score(score):
    if score >= 75:
        return "Saudavel"
    if score >= 45:
        return "Atencao"
    return "Critico"


def _build_payload(
    *,
    projeto,
    provider,
    model,
    fonte,
    score,
    situacao,
    recomendacao,
    confidence,
    schedule_risk,
    cost_risk,
    resource_risk,
    actions,
    tendencia,
    aviso=None,
):
    score = _clamp(score)
    confidence = _clamp(confidence)
    schedule_risk = _clamp(schedule_risk)
    cost_risk = _clamp(cost_risk)
    resource_risk = _clamp(resource_risk)
    risco_geral = _clamp((schedule_risk + cost_risk + resource_risk) / 3.0)
    budget_efficiency = _clamp(100 - cost_risk)
    execution_velocity = _clamp(projeto["progresso"] - (schedule_risk * 0.35) + 40)

    situacao_color = {
        "Saudavel": "success",
        "Atencao": "warning",
        "Critico": "danger",
    }.get(situacao, "warning")

    return {
        "projeto": projeto,
        "provider": provider,
        "model": model,
        "fonte": fonte,
        "aviso": aviso or "",
        "sumario": (
            f"{situacao}: score {score}/100, risco geral {risco_geral}% e "
            f"confianca {confidence}% para apoio a decisao."
        ),
        "metricas": {
            "score": score,
            "situacao": situacao,
            "situacao_color": situacao_color,
            "recomendacao": recomendacao,
            "confianca": confidence,
            "tendencia": tendencia,
            "risco_cronograma": schedule_risk,
            "risco_custo": cost_risk,
            "risco_recursos": resource_risk,
            "risco_geral": risco_geral,
            "eficiencia_orcamentaria": budget_efficiency,
            "velocidade_execucao": execution_velocity,
        },
        "acoes_recomendadas": actions[:4],
        "graficos": {
            "radar_labels": [
                "Cronograma",
                "Custo",
                "Recursos",
                "Eficiencia",
                "Execucao",
                "Confianca",
            ],
            "radar_values": [
                _clamp(100 - schedule_risk),
                _clamp(100 - cost_risk),
                _clamp(100 - resource_risk),
                budget_efficiency,
                execution_velocity,
                confidence,
            ],
            "risco_labels": ["Cronograma", "Custo", "Recursos"],
            "risco_values": [schedule_risk, cost_risk, resource_risk],
        },
    }


def _analise_local_payload(nome, progresso, custo, prioridade, provider, model, aviso):
    progresso_num = _to_float(progresso, 0)
    prioridade_norm = _normalizar_prioridade(prioridade)
    penalidade_prioridade = 25 if prioridade_norm == "alta" else 10 if prioridade_norm == "media" else 0
    score = _clamp(progresso_num - penalidade_prioridade + 30)
    situacao = _situacao_por_score(score)

    recomendacao = {
        "Saudavel": "Manter o plano atual, com checkpoints quinzenais e controle de escopo.",
        "Atencao": "Revisar cronograma base, redistribuir recursos criticos e tratar riscos de curto prazo.",
        "Critico": "Abrir plano de acao executivo com dono, prazo e revisao semanal de recuperacao.",
    }[situacao]

    risco_cronograma = _clamp(100 - progresso_num + (20 if prioridade_norm == "alta" else 8))
    risco_custo = _clamp(55 if prioridade_norm == "alta" else 40 if prioridade_norm == "media" else 28)
    risco_recursos = _clamp(60 if prioridade_norm == "alta" else 45 if prioridade_norm == "media" else 30)

    return _build_payload(
        projeto={
            "nome": nome,
            "progresso": _clamp(progresso_num),
            "custo": _to_float(custo, 0),
            "prioridade": prioridade,
        },
        provider=provider,
        model=model,
        fonte="fallback_local",
        score=score,
        situacao=situacao,
        recomendacao=recomendacao,
        confidence=66,
        schedule_risk=risco_cronograma,
        cost_risk=risco_custo,
        resource_risk=risco_recursos,
        actions=[
            "Ajustar marcos do cronograma dos proximos 30 dias.",
            "Repriorizar entregas de maior impacto operacional.",
            "Revisar capacidade da equipe e gargalos tecnicos.",
            "Executar reuniao de risco com patrocinador do projeto.",
        ],
        tendencia="estavel",
        aviso=aviso,
    )


def _extrair_json(texto):
    if not texto:
        return None

    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", texto)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def analisar_projeto(nome, progresso, custo, prioridade):
    provider_name = "IA"
    model_name = "modelo_desconhecido"
    env_key_name = "OPENAI_API_KEY"
    projeto = {
        "nome": nome,
        "progresso": _clamp(progresso),
        "custo": _to_float(custo, 0),
        "prioridade": prioridade,
    }

    try:
        client, model_name, env_key_name, provider_name = _resolver_cliente()
        if client is None:
            return _analise_local_payload(
                nome,
                progresso,
                custo,
                prioridade,
                provider_name,
                model_name,
                (
                    f"Chave {env_key_name} nao configurada. Defina no arquivo .env para habilitar IA online."
                ),
            )

        prompt = f"""
Voce e um PMO analyst senior.
Analise o projeto abaixo e responda SOMENTE em JSON valido.

Projeto:
- nome: {nome}
- progresso_percentual: {progresso}
- custo_estimado: {custo}
- prioridade: {prioridade}

Retorne exatamente este schema:
{{
  "score": 0-100,
  "situacao": "Saudavel|Atencao|Critico",
  "recomendacao": "texto curto",
  "confianca": 0-100,
  "tendencia": "melhora|estavel|queda",
  "riscos": {{
    "cronograma": 0-100,
    "custo": 0-100,
    "recursos": 0-100
  }},
  "acoes_recomendadas": ["acao1","acao2","acao3","acao4"]
}}
"""

        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.choices[0].message.content if response.choices else ""
        parsed = _extrair_json(content)

        if not isinstance(parsed, dict):
            return _analise_local_payload(
                nome,
                progresso,
                custo,
                prioridade,
                provider_name,
                model_name,
                "Resposta da IA em formato invalido. Aplicado fallback local estruturado.",
            )

        riscos = parsed.get("riscos") or {}
        return _build_payload(
            projeto=projeto,
            provider=provider_name,
            model=model_name,
            fonte="ia_online",
            score=parsed.get("score", 55),
            situacao=parsed.get("situacao", _situacao_por_score(parsed.get("score", 55))),
            recomendacao=parsed.get("recomendacao", "Revisar plano executivo e riscos prioritarios."),
            confidence=parsed.get("confianca", 70),
            schedule_risk=riscos.get("cronograma", 45),
            cost_risk=riscos.get("custo", 45),
            resource_risk=riscos.get("recursos", 45),
            actions=parsed.get("acoes_recomendadas")
            or [
                "Revisar marcos criticos do cronograma.",
                "Refinar plano de custos e contingencias.",
                "Ajustar alocacao de recursos essenciais.",
                "Realizar checkpoint executivo semanal.",
            ],
            tendencia=parsed.get("tendencia", "estavel"),
        )

    except RateLimitError as exc:
        erro_txt = str(exc).lower()
        aviso = (
            f"Cota da API esgotada ({provider_name}). Verifique billing e limites do projeto."
            if "insufficient_quota" in erro_txt or "exceeded your current quota" in erro_txt
            else "Limite de requisicoes da IA atingido temporariamente."
        )
        return _analise_local_payload(nome, progresso, custo, prioridade, provider_name, model_name, aviso)

    except AuthenticationError:
        return _analise_local_payload(
            nome,
            progresso,
            custo,
            prioridade,
            provider_name,
            model_name,
            f"Falha de autenticacao da chave {env_key_name}.",
        )

    except APIConnectionError:
        aviso = (
            f"Nao foi possivel conectar ao Ollama em {OLLAMA_BASE_URL}."
            if provider_name == "Ollama"
            else "Falha de conexao com a API de IA."
        )
        return _analise_local_payload(nome, progresso, custo, prioridade, provider_name, model_name, aviso)

    except APIStatusError:
        return _analise_local_payload(
            nome,
            progresso,
            custo,
            prioridade,
            provider_name,
            model_name,
            "Servico de IA retornou erro de status temporario.",
        )

    except Exception:
        return _analise_local_payload(
            nome,
            progresso,
            custo,
            prioridade,
            provider_name,
            model_name,
            "Erro inesperado na analise inteligente. Aplicado fallback local.",
        )
