from contextlib import contextmanager
import re

import psycopg2

from config import (
    DB_CONNECT_TIMEOUT,
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_SCHEMA,
    DB_USER,
)


def get_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT,
        connect_timeout=DB_CONNECT_TIMEOUT,
    )

    cursor = conn.cursor()
    schema = DB_SCHEMA if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", DB_SCHEMA or "") else "public"
    cursor.execute(f"SET search_path TO {schema}")
    cursor.close()

    return conn


def ensure_database_structure():
    schema = DB_SCHEMA if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", DB_SCHEMA or "") else "public"
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            cur.execute(f"SET search_path TO {schema}")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(120) NOT NULL,
                    email VARCHAR(160) NOT NULL UNIQUE,
                    senha VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS projetos (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(140) NOT NULL,
                    progresso NUMERIC(5,2) NOT NULL DEFAULT 0,
                    custo_estimado NUMERIC(14,2) NOT NULL DEFAULT 0,
                    prioridade VARCHAR(20) NOT NULL DEFAULT 'media'
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS historico_projetos (
                    id SERIAL PRIMARY KEY,
                    projeto_id INTEGER NOT NULL,
                    acao VARCHAR(40) NOT NULL,
                    usuario_id INTEGER,
                    usuario_nome VARCHAR(120),
                    data_hora TIMESTAMP NOT NULL DEFAULT NOW(),
                    detalhes TEXT,
                    CONSTRAINT fk_historico_projeto
                        FOREIGN KEY (projeto_id)
                        REFERENCES projetos(id)
                        ON DELETE CASCADE
                )
                """
            )

            evolution_statements = [
                "ALTER TABLE projetos ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'planejado'",
                "ALTER TABLE projetos ADD COLUMN IF NOT EXISTS area_estrategica VARCHAR(80)",
                "ALTER TABLE projetos ADD COLUMN IF NOT EXISTS gerente_responsavel VARCHAR(120)",
                "ALTER TABLE projetos ADD COLUMN IF NOT EXISTS patrocinador VARCHAR(120)",
                "ALTER TABLE projetos ADD COLUMN IF NOT EXISTS data_inicio_prevista DATE",
                "ALTER TABLE projetos ADD COLUMN IF NOT EXISTS data_fim_prevista DATE",
                "ALTER TABLE projetos ADD COLUMN IF NOT EXISTS risco_nivel VARCHAR(20) NOT NULL DEFAULT 'medio'",
                "ALTER TABLE projetos ADD COLUMN IF NOT EXISTS beneficio_esperado VARCHAR(600)",
                "ALTER TABLE projetos ADD COLUMN IF NOT EXISTS descricao TEXT",
                "ALTER TABLE projetos ADD COLUMN IF NOT EXISTS criado_por_user_id INTEGER",
                "ALTER TABLE projetos ADD COLUMN IF NOT EXISTS criado_por_nome VARCHAR(120)",
                "ALTER TABLE projetos ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW()",
                "ALTER TABLE projetos ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW()",
            ]
            for stmt in evolution_statements:
                cur.execute(stmt)

            # Compatibilidade com estruturas legadas onde essas colunas podem nao estar em texto.
            cur.execute("ALTER TABLE projetos ALTER COLUMN prioridade TYPE VARCHAR(20) USING prioridade::text")
            cur.execute("ALTER TABLE projetos ALTER COLUMN status TYPE VARCHAR(20) USING status::text")
            cur.execute("ALTER TABLE projetos ALTER COLUMN risco_nivel TYPE VARCHAR(20) USING risco_nivel::text")

            cur.execute("CREATE INDEX IF NOT EXISTS idx_projetos_prioridade ON projetos (LOWER(prioridade::text))")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_projetos_status ON projetos (LOWER(status::text))")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_projetos_risco ON projetos (LOWER(risco_nivel::text))")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_projetos_progresso ON projetos (progresso)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_historico_projeto_id ON historico_projetos (projeto_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_historico_data_hora ON historico_projetos (data_hora DESC)")

            cur.execute(
                """
                CREATE OR REPLACE FUNCTION set_updated_at_projetos()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql
                """
            )
            cur.execute("DROP TRIGGER IF EXISTS trg_set_updated_at_projetos ON projetos")
            cur.execute(
                """
                CREATE TRIGGER trg_set_updated_at_projetos
                BEFORE UPDATE ON projetos
                FOR EACH ROW
                EXECUTE FUNCTION set_updated_at_projetos()
                """
            )
            conn.commit()
        finally:
            cur.close()


@contextmanager
def get_cursor(commit=False):
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
