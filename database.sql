-- PMO APP - Evolucao de estrutura para gestao estrategica
-- Execute no PostgreSQL conectado ao banco definido em DB_NAME.

CREATE SCHEMA IF NOT EXISTS pmo;
SET search_path TO pmo;

CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(120) NOT NULL,
    email VARCHAR(160) NOT NULL UNIQUE,
    senha VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS projetos (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(140) NOT NULL,
    progresso NUMERIC(5,2) NOT NULL DEFAULT 0,
    custo_estimado NUMERIC(14,2) NOT NULL DEFAULT 0,
    prioridade VARCHAR(20) NOT NULL DEFAULT 'media'
);

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
);

ALTER TABLE projetos ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'planejado';
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS area_estrategica VARCHAR(80);
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS gerente_responsavel VARCHAR(120);
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS patrocinador VARCHAR(120);
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS data_inicio_prevista DATE;
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS data_fim_prevista DATE;
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS risco_nivel VARCHAR(20) NOT NULL DEFAULT 'medio';
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS beneficio_esperado VARCHAR(600);
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS descricao TEXT;
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS criado_por_user_id INTEGER;
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS criado_por_nome VARCHAR(120);
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW();
ALTER TABLE projetos ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW();

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_projetos_progresso_range'
    ) THEN
        ALTER TABLE projetos
            ADD CONSTRAINT chk_projetos_progresso_range
            CHECK (progresso >= 0 AND progresso <= 100);
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_projetos_prioridade'
    ) THEN
        ALTER TABLE projetos
            ADD CONSTRAINT chk_projetos_prioridade
            CHECK (LOWER(prioridade) IN ('baixa', 'media', 'alta', 'critica'));
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_projetos_status'
    ) THEN
        ALTER TABLE projetos
            ADD CONSTRAINT chk_projetos_status
            CHECK (LOWER(status) IN ('planejado', 'execucao', 'atrasado', 'concluido', 'cancelado'));
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_projetos_risco'
    ) THEN
        ALTER TABLE projetos
            ADD CONSTRAINT chk_projetos_risco
            CHECK (LOWER(risco_nivel) IN ('baixo', 'medio', 'alto'));
    END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_projetos_prioridade ON projetos (LOWER(prioridade));
CREATE INDEX IF NOT EXISTS idx_projetos_status ON projetos (LOWER(status));
CREATE INDEX IF NOT EXISTS idx_projetos_risco ON projetos (LOWER(risco_nivel));
CREATE INDEX IF NOT EXISTS idx_projetos_progresso ON projetos (progresso);
CREATE INDEX IF NOT EXISTS idx_historico_projeto_id ON historico_projetos (projeto_id);
CREATE INDEX IF NOT EXISTS idx_historico_data_hora ON historico_projetos (data_hora DESC);

CREATE OR REPLACE FUNCTION set_updated_at_projetos()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_set_updated_at_projetos ON projetos;
CREATE TRIGGER trg_set_updated_at_projetos
BEFORE UPDATE ON projetos
FOR EACH ROW
EXECUTE FUNCTION set_updated_at_projetos();
