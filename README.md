Aplicativo PMO

Aplicação web desenvolvida em Flask para gestão de portfólio de projetos, permitindo cadastro, acompanhamento e priorização de iniciativas estratégicas. Possui dashboard executivo, mapa de criticidade e análise inteligente com IA, com fallback local para garantir resiliência.

A arquitetura é baseada em backend server-side em Flask, banco de dados PostgreSQL com criação e evolução automática de schema, e frontend utilizando templates Jinja com CSS. A integração com IA é desacoplada, permitindo uso de múltiplos provedores.

A stack inclui Python 3.12, Flask, psycopg2, OpenAI SDK, dotenv e unittest.

O projeto conta com pipeline de CI/CD no GitHub Actions, que realiza validações automáticas e execução de testes a cada push, pull request e execuções manuais, garantindo qualidade e estabilidade da aplicação.
