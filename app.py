from datetime import date
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

from config import AI_PROVIDER, APP_SECRET_KEY, FLASK_DEBUG
from db import ensure_database_structure, get_cursor
from services.ia_service import analisar_projeto

app = Flask(__name__)
app.secret_key = APP_SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

try:
    ensure_database_structure()
except Exception:
    app.logger.exception("Falha ao validar estrutura do banco na inicializacao.")

CRITERIO_CRITICO = (
    "Prioridade alta/crítica, risco alto ou projeto em execução com progresso abaixo de 40%."
)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            flash("Sessão expirada. Faça login para continuar.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def normalizar_custo(valor):
    if valor is None:
        return Decimal("0")

    texto = str(valor).strip().replace("R$", "").replace(" ", "")
    if not texto:
        return Decimal("0")

    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        return Decimal(texto)
    except InvalidOperation:
        return Decimal("0")


def formatar_moeda_brl(valor):
    numero = float(valor or 0)
    return "R$ {:,.2f}".format(numero).replace(",", "X").replace(".", ",").replace("X", ".")


def normalizar_prioridade(valor):
    raw = str(valor or "").strip().lower()
    mapa = {
        "alta": "alta",
        "critica": "critica",
        "urgente": "critica",
        "high": "alta",
        "critical": "critica",
        "media": "media",
        "medium": "media",
        "baixa": "baixa",
        "low": "baixa",
    }
    return mapa.get(raw, raw)


def normalizar_risco(valor):
    raw = str(valor or "").strip().lower()
    mapa = {"alto": "alto", "high": "alto", "medio": "medio", "medium": "medio", "baixo": "baixo", "low": "baixo"}
    return mapa.get(raw, raw)


def normalizar_status(valor):
    raw = str(valor or "").strip().lower()
    mapa = {
        "planejado": "planejado",
        "execucao": "execucao",
        "atrasado": "atrasado",
        "concluido": "concluido",
        "cancelado": "cancelado",
        "planning": "planejado",
        "in_progress": "execucao",
        "delayed": "atrasado",
        "done": "concluido",
    }
    return mapa.get(raw, raw)


def parse_data_iso(valor):
    texto = str(valor or "").strip()
    if not texto:
        return None
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return None


def validar_dados_projeto(form):
    nome_limpo = str(form.get("nome", "")).strip()
    if len(nome_limpo) < 3:
        return None, "Nome do projeto deve ter pelo menos 3 caracteres."
    if len(nome_limpo) > 140:
        return None, "Nome do projeto deve ter no máximo 140 caracteres."

    try:
        progresso_num = float(str(form.get("progresso", "")).replace(",", "."))
    except (TypeError, ValueError):
        return None, "Progresso deve ser numérico."

    if progresso_num < 0 or progresso_num > 100:
        return None, "Progresso deve estar entre 0 e 100."

    custo_num = normalizar_custo(form.get("custo"))
    if custo_num < 0:
        return None, "Custo não pode ser negativo."

    prioridade_norm = normalizar_prioridade(form.get("prioridade"))
    if prioridade_norm not in ("baixa", "media", "alta", "critica"):
        return None, "Prioridade inválida."

    risco_nivel = normalizar_risco(form.get("risco_nivel"))
    if risco_nivel not in ("baixo", "medio", "alto"):
        return None, "Risco inválido."

    status = normalizar_status(form.get("status"))
    if status not in ("planejado", "execucao", "atrasado", "concluido", "cancelado"):
        return None, "Status inválido."

    data_inicio = parse_data_iso(form.get("data_inicio_prevista"))
    data_fim = parse_data_iso(form.get("data_fim_prevista"))
    if data_inicio and data_fim and data_fim < data_inicio:
        return None, "Data fim não pode ser menor que data início."

    return {
        "nome": nome_limpo,
        "progresso": Decimal(str(round(progresso_num, 2))),
        "custo_estimado": custo_num,
        "prioridade": prioridade_norm,
        "status": status,
        "area_estrategica": str(form.get("area_estrategica", "")).strip()[:80] or None,
        "gerente_responsavel": str(form.get("gerente_responsavel", "")).strip()[:120] or None,
        "patrocinador": str(form.get("patrocinador", "")).strip()[:120] or None,
        "data_inicio_prevista": data_inicio,
        "data_fim_prevista": data_fim,
        "risco_nivel": risco_nivel,
        "beneficio_esperado": str(form.get("beneficio_esperado", "")).strip()[:600] or None,
        "descricao": str(form.get("descricao", "")).strip()[:1600] or None,
    }, None


def query_criticos():
    return """
        (
            LOWER(COALESCE(prioridade::text, '')) IN ('alta', 'critica', 'urgente', 'critical', 'high', '1')
            OR LOWER(COALESCE(risco_nivel::text, '')) = 'alto'
            OR (
                LOWER(COALESCE(status::text, '')) IN ('execucao', 'atrasado')
                AND COALESCE(progresso, 0) < 40
            )
        )
    """


def gerar_resumo_portfolio(total, ativos, criticos, progresso_medio, custo_total, por_status):
    status_partes = []
    for item in por_status:
        status_nome = (item[0] or "não informado").capitalize()
        status_partes.append(f"{status_nome}: {int(item[1] or 0)}")
    status_txt = "; ".join(status_partes) if status_partes else "Sem distribuição por status."

    return (
        f"O portfólio atual possui {total} projeto(s), com {ativos} ativo(s) e {criticos} crítico(s). "
        f"Progresso médio de {progresso_medio:.1f}% e custo total estimado de {formatar_moeda_brl(custo_total)}. "
        f"Distribuição por status: {status_txt}."
    )


@app.route("/health")
def health():
    return jsonify({"status": "ok", "ai_provider": AI_PROVIDER})


@app.route("/", methods=["GET", "POST"])
def login():
    if session.get("user"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        senha = request.form.get("senha", "").strip()
        if not email or not senha:
            flash("Informe e-mail e senha.", "warning")
            return render_template("login.html")

        try:
            with get_cursor() as cur:
                cur.execute(
                    "SELECT id, nome FROM usuarios WHERE email=%s AND senha=%s",
                    (email, senha),
                )
                user = cur.fetchone()
        except Exception:
            flash("Falha ao autenticar. Verifique o banco de dados.", "danger")
            return render_template("login.html")

        if user:
            session["user"] = user[1]
            session["user_id"] = user[0]
            return redirect(url_for("dashboard"))

        flash("Credenciais inválidas.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    critico_filter = query_criticos()
    try:
        with get_cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS total_projetos,
                    COUNT(*) FILTER (WHERE COALESCE(progresso, 0) < 100) AS projetos_ativos,
                    COUNT(*) FILTER (WHERE {critico_filter}) AS projetos_criticos,
                    COALESCE(ROUND(AVG(COALESCE(progresso, 0))::numeric, 1), 0) AS progresso_medio,
                    COALESCE(SUM(COALESCE(custo_estimado, 0)), 0) AS custo_total,
                    COUNT(*) FILTER (
                        WHERE COALESCE(progresso, 0) >= 70
                        AND LOWER(COALESCE(prioridade::text, '')) NOT IN ('alta', 'critica')
                    ) AS projetos_estaveis
                FROM projetos
                """
            )
            indicadores = cur.fetchone() or (0, 0, 0, 0, 0, 0)
    except Exception:
        app.logger.exception("Falha ao carregar indicadores estratégicos.")
        indicadores = (0, 0, 0, 0, 0, 0)

    return render_template(
        "dashboard.html",
        total_projetos=int(indicadores[0] or 0),
        projetos_ativos=int(indicadores[1] or 0),
        projetos_criticos=int(indicadores[2] or 0),
        progresso_medio=float(indicadores[3] or 0),
        custo_total=formatar_moeda_brl(indicadores[4] or 0),
        projetos_estaveis=int(indicadores[5] or 0),
        criterio_critico=CRITERIO_CRITICO,
    )


@app.route("/portfolio")
@login_required
def portfolio():
    critico_filter = query_criticos()
    try:
        with get_cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS total_projetos,
                    COUNT(*) FILTER (WHERE COALESCE(progresso, 0) < 100) AS projetos_ativos,
                    COUNT(*) FILTER (WHERE {critico_filter}) AS projetos_criticos,
                    COALESCE(ROUND(AVG(COALESCE(progresso, 0))::numeric, 1), 0) AS progresso_medio,
                    COALESCE(SUM(COALESCE(custo_estimado, 0)), 0) AS custo_total
                FROM projetos
                """
            )
            resumo = cur.fetchone() or (0, 0, 0, 0, 0)

            cur.execute(
                """
                SELECT LOWER(COALESCE(status::text, 'não informado')) AS status, COUNT(*)
                FROM projetos
                GROUP BY LOWER(COALESCE(status::text, 'não informado'))
                ORDER BY COUNT(*) DESC, status ASC
                """
            )
            por_status = cur.fetchall()

            cur.execute(
                f"""
                SELECT id, nome, status, progresso, prioridade, risco_nivel, custo_estimado
                FROM projetos
                WHERE {critico_filter}
                ORDER BY COALESCE(progresso, 0) ASC, id DESC
                LIMIT 5
                """
            )
            top_criticos = cur.fetchall()

            cur.execute(
                f"""
                SELECT
                    id,
                    nome,
                    COALESCE(status::text, '-') AS status,
                    COALESCE(progresso, 0) AS progresso,
                    COALESCE(custo_estimado, 0) AS custo_estimado,
                    COALESCE(prioridade::text, '-') AS prioridade,
                    COALESCE(risco_nivel::text, '-') AS risco_nivel,
                    COALESCE(area_estrategica, '-') AS area_estrategica,
                    COALESCE(gerente_responsavel, '-') AS gerente_responsavel,
                    COALESCE(data_inicio_prevista::text, '-') AS data_inicio_prevista,
                    COALESCE(data_fim_prevista::text, '-') AS data_fim_prevista,
                    COALESCE(beneficio_esperado, '-') AS beneficio_esperado,
                    CASE
                        WHEN {critico_filter} THEN 'Crítico'
                        WHEN COALESCE(progresso, 0) < 70 THEN 'Atenção'
                        ELSE 'Estável'
                    END AS faixa_criticidade,
                    (
                        CASE
                            WHEN LOWER(COALESCE(prioridade::text, '')) IN ('alta', 'critica', '1') THEN 40
                            WHEN LOWER(COALESCE(prioridade::text, '')) IN ('media', '2') THEN 20
                            ELSE 10
                        END
                        +
                        CASE
                            WHEN LOWER(COALESCE(risco_nivel::text, '')) = 'alto' THEN 40
                            WHEN LOWER(COALESCE(risco_nivel::text, '')) = 'medio' THEN 20
                            ELSE 10
                        END
                        +
                        CASE
                            WHEN COALESCE(progresso, 0) < 40 THEN 20
                            WHEN COALESCE(progresso, 0) < 70 THEN 10
                            ELSE 0
                        END
                    ) AS score_criticidade
                FROM projetos
                ORDER BY score_criticidade DESC, COALESCE(progresso, 0) ASC, id DESC
                """
            )
            portfolio_detalhado = cur.fetchall()

            cur.execute(
                """
                SELECT
                    COALESCE(area_estrategica, 'Não informada') AS area_estrategica,
                    COUNT(*) AS quantidade,
                    COALESCE(SUM(COALESCE(custo_estimado, 0)), 0) AS custo_total
                FROM projetos
                GROUP BY COALESCE(area_estrategica, 'Não informada')
                ORDER BY quantidade DESC, area_estrategica
                """
            )
            por_area = cur.fetchall()
    except Exception:
        flash("Falha ao gerar resumo do portfólio.", "danger")
        resumo = (0, 0, 0, 0, 0)
        por_status = []
        top_criticos = []
        portfolio_detalhado = []
        por_area = []

    return render_template(
        "portfolio.html",
        total_projetos=int(resumo[0] or 0),
        projetos_ativos=int(resumo[1] or 0),
        projetos_criticos=int(resumo[2] or 0),
        progresso_medio=float(resumo[3] or 0),
        custo_total=formatar_moeda_brl(resumo[4] or 0),
        por_status=por_status,
        top_criticos=top_criticos,
        portfolio_detalhado=portfolio_detalhado,
        por_area=por_area,
        resumo_portfolio=gerar_resumo_portfolio(
            int(resumo[0] or 0),
            int(resumo[1] or 0),
            int(resumo[2] or 0),
            float(resumo[3] or 0),
            resumo[4] or 0,
            por_status,
        ),
        criterio_critico=CRITERIO_CRITICO,
    )


@app.route("/projetos", methods=["GET"])
@login_required
def projetos():
    filtro = (request.args.get("filtro") or "").strip().lower()
    where_clause = ""
    titulo_lista = "Lista de Projetos"
    if filtro == "criticos":
        where_clause = f"WHERE {query_criticos()}"
        titulo_lista = "Projetos Críticos"
    elif filtro == "ativos":
        where_clause = "WHERE COALESCE(progresso, 0) < 100"
        titulo_lista = "Projetos Ativos"
    elif filtro == "total":
        titulo_lista = "Total de Projetos"

    try:
        with get_cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    id, nome, progresso, prioridade, custo_estimado, status,
                    area_estrategica, gerente_responsavel, risco_nivel
                FROM projetos
                {where_clause}
                ORDER BY id DESC
                """
            )
            lista = cur.fetchall()
    except Exception:
        flash("Não foi possível carregar a lista de projetos.", "danger")
        lista = []

    return render_template(
        "projetos.html",
        projetos=lista,
        filtro=filtro,
        titulo_lista=titulo_lista,
        criterio_critico=CRITERIO_CRITICO,
    )


@app.route("/projetos/novo", methods=["GET", "POST"])
@login_required
def novo_projeto():
    if request.method == "POST":
        dados, erro = validar_dados_projeto(request.form)
        if erro:
            flash(erro, "warning")
            return redirect(url_for("novo_projeto"))

        dados["criado_por_user_id"] = session.get("user_id")
        dados["criado_por_nome"] = (session.get("user") or "").strip()[:120] or None

        try:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO projetos (
                        nome, progresso, custo_estimado, prioridade, status, area_estrategica,
                        gerente_responsavel, patrocinador, data_inicio_prevista, data_fim_prevista,
                        risco_nivel, beneficio_esperado, descricao, criado_por_user_id, criado_por_nome
                    )
                    VALUES (
                        %(nome)s, %(progresso)s, %(custo_estimado)s, %(prioridade)s, %(status)s, %(area_estrategica)s,
                        %(gerente_responsavel)s, %(patrocinador)s, %(data_inicio_prevista)s, %(data_fim_prevista)s,
                        %(risco_nivel)s, %(beneficio_esperado)s, %(descricao)s, %(criado_por_user_id)s, %(criado_por_nome)s
                    )
                    RETURNING id
                    """,
                    dados,
                )
                novo_projeto_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO historico_projetos (
                        projeto_id, acao, usuario_id, usuario_nome, detalhes
                    )
                    VALUES (
                        %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        novo_projeto_id,
                        "criacao",
                        dados["criado_por_user_id"],
                        dados["criado_por_nome"],
                        "Projeto cadastrado via modulo Novo Projeto.",
                    ),
                )
            flash("Projeto cadastrado com sucesso.", "success")
            return redirect(url_for("projetos"))
        except Exception:
            flash("Não foi possível salvar o projeto. Execute as queries de evolução do banco.", "danger")
            return redirect(url_for("novo_projeto"))

    return render_template("novo_projeto.html")


@app.route("/mapa-criticidade")
@login_required
def mapa_criticidade():
    critico_filter = query_criticos()
    try:
        with get_cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    id, nome, status, progresso, prioridade, risco_nivel, custo_estimado,
                    CASE WHEN {critico_filter} THEN 'critico' ELSE 'monitoramento' END AS faixa
                FROM projetos
                ORDER BY
                    CASE
                        WHEN LOWER(COALESCE(risco_nivel::text, '')) = 'alto' THEN 1
                        WHEN LOWER(COALESCE(risco_nivel::text, '')) = 'medio' THEN 2
                        ELSE 3
                    END,
                    COALESCE(progresso, 0) ASC,
                    id DESC
                """
            )
            projetos = cur.fetchall()

            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE LOWER(COALESCE(prioridade::text, '')) IN ('alta', 'critica', '1')) AS prioridade_alta,
                    COUNT(*) FILTER (WHERE LOWER(COALESCE(prioridade::text, '')) IN ('media', '2')) AS prioridade_media,
                    COUNT(*) FILTER (WHERE LOWER(COALESCE(prioridade::text, '')) IN ('baixa', '3')) AS prioridade_baixa,
                    COUNT(*) FILTER (WHERE LOWER(COALESCE(risco_nivel::text, '')) = 'alto') AS risco_alto,
                    COUNT(*) FILTER (WHERE LOWER(COALESCE(risco_nivel::text, '')) = 'medio') AS risco_medio,
                    COUNT(*) FILTER (WHERE LOWER(COALESCE(risco_nivel::text, '')) = 'baixo') AS risco_baixo
                FROM projetos
                """
            )
            visao = cur.fetchone() or (0, 0, 0, 0, 0, 0)
    except Exception:
        flash("Falha ao carregar o mapa de criticidade.", "danger")
        projetos = []
        visao = (0, 0, 0, 0, 0, 0)

    return render_template(
        "mapa_criticidade.html",
        projetos=projetos,
        prioridade_alta=int(visao[0] or 0),
        prioridade_media=int(visao[1] or 0),
        prioridade_baixa=int(visao[2] or 0),
        risco_alto=int(visao[3] or 0),
        risco_medio=int(visao[4] or 0),
        risco_baixo=int(visao[5] or 0),
        criterio_critico=CRITERIO_CRITICO,
    )


@app.route("/projetos/<int:id>")
@login_required
def detalhes_projeto(id):
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT
                    id, nome, progresso, prioridade, custo_estimado, status,
                    area_estrategica, gerente_responsavel, patrocinador,
                    data_inicio_prevista, data_fim_prevista, risco_nivel,
                    beneficio_esperado, descricao, created_at, updated_at,
                    criado_por_user_id, criado_por_nome
                FROM projetos
                WHERE id=%s
                """,
                (id,),
            )
            projeto = cur.fetchone()
    except Exception:
        projeto = None

    if not projeto:
        flash("Projeto não encontrado.", "warning")
        return redirect(url_for("projetos"))

    return render_template(
        "projeto_detalhes.html",
        projeto=projeto,
        custo_formatado=formatar_moeda_brl(projeto[4]),
    )


@app.route("/projetos/excluir/<int:id>", methods=["POST"])
@login_required
def excluir_projeto(id):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM projetos WHERE id=%s", (id,))
            if cur.rowcount == 0:
                flash("Projeto não encontrado para exclusão.", "warning")
            else:
                flash("Projeto excluído com sucesso.", "info")
    except Exception:
        flash("Falha ao excluir projeto.", "danger")
    return redirect(url_for("projetos"))


@app.route("/analisar/<int:id>")
@login_required
def analisar(id):
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT nome, progresso, custo_estimado, prioridade FROM projetos WHERE id=%s",
                (id,),
            )
            projeto = cur.fetchone()
    except Exception:
        flash("Falha ao consultar dados do projeto.", "danger")
        projeto = None

    if not projeto:
        return render_template(
            "analise.html",
            projeto_nome="Projeto não encontrado",
            progresso_percentual=0,
            custo_formatado=formatar_moeda_brl(0),
            analise={
                "fonte": "fallback_local",
                "aviso": "Não foi possível localizar o projeto solicitado.",
                "sumario": "Sem dados para análise.",
                "metricas": {
                    "score": 0,
                    "situacao": "Atenção",
                    "situacao_color": "warning",
                    "recomendacao": "Selecione um projeto válido.",
                    "confianca": 0,
                    "tendencia": "estavel",
                    "risco_geral": 0,
                },
                "acoes_recomendadas": [
                    "Voltar para a lista de projetos.",
                    "Verificar se o ID consultado existe.",
                ],
                "graficos": {
                    "radar_labels": ["Cronograma", "Custo", "Recursos", "Eficiência", "Execução", "Confiança"],
                    "radar_values": [0, 0, 0, 0, 0, 0],
                    "risco_labels": ["Cronograma", "Custo", "Recursos"],
                    "risco_values": [0, 0, 0],
                },
            },
        )

    analise = analisar_projeto(*projeto)
    return render_template(
        "analise.html",
        projeto_nome=projeto[0],
        analise=analise,
        custo_formatado=formatar_moeda_brl(projeto[2]),
        progresso_percentual=int(float(projeto[1] or 0)),
    )


if __name__ == "__main__":
    app.run(debug=FLASK_DEBUG)
