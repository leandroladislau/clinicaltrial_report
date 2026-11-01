# Inteligência Competitiva HER2+ — Ensaios Clínicos

Plataforma de coleta de dados e geração de relatórios de **inteligência competitiva e
regulatória** sobre ensaios clínicos de **câncer de mama HER2-positivo**, a partir dos
dados públicos do [ClinicalTrials.gov](https://clinicaltrials.gov).

O projeto faz duas coisas:

1. **Coleta** os estudos da API v2 do ClinicalTrials.gov e os armazena num banco SQLite.
2. **Gera** um relatório PDF executivo, em pt-BR, com a identidade visual da
   [Pesquisa e Dados](https://www.pesquisaedados.com) — gráficos, infográficos, heatmaps,
   treemaps e tiles de KPI, voltado a executivos da indústria farmacêutica.

---

## Sumário

- [Visão geral](#visão-geral)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Como atualizar o banco de dados](#como-atualizar-o-banco-de-dados)
- [Como gerar o relatório](#como-gerar-o-relatório)
- [Esquema do banco de dados](#esquema-do-banco-de-dados)
- [Metodologia e limitações](#metodologia-e-limitações)

---

## Visão geral

O universo analisado são ensaios **intervencionais**, **fases 2 a 4**, com status **ativo
ou em recrutamento** (`RECRUITING`, `ACTIVE_NOT_RECRUITING`, `NOT_YET_RECRUITING`,
`ENROLLING_BY_INVITATION`), encontrados pelo termo de busca `"HER2-positive Breast Cancer"`.

A coleta mais recente do banco versionado contém **700 estudos** (data de coleta:
**2026-06-12**).

O relatório usa uma **taxonomia clínica em dois eixos**:

- **Subtipo molecular**: HER2+/HR+, HER2+/HR−, HR+/HER2−, TNBC;
- **Estágio da doença**: Metastático, Inicial/(Neo)adjuvante, Misto, SNC, N/E.

A classificação é feita por processamento textual (condições + título + resumo + fármacos
+ sinal de fármaco anti-HER2), o que reduz a fatia de "não especificado" para ~4%.

---

## Estrutura do projeto

| Arquivo / pasta | Descrição |
| --- | --- |
| `fetch_trials.py` | Coleta os estudos da API v2 do ClinicalTrials.gov e (re)cria o banco SQLite. |
| `her2_breast_cancer_trials.db` | Banco SQLite com os snapshots dos estudos (versionado). |
| `generate_report_updated.py` | **Script atual** de geração do relatório PDF (taxonomia refinada, geografia, índice, infográficos). |
| `generate_report.py` | Versão anterior do gerador de relatório (mantida como referência). |
| `generate_report_v2.py` | Protótipo/versão intermediária do gerador (referência). |
| `REPORT_PROMPT.md` | Prompt reutilizável que descreve fonte de dados, branding, taxonomia e as páginas do relatório. |
| `email_marketing_her2.html` | Peça de e-mail marketing com o resumo da inteligência HER2+. |
| `fonts/` | Fontes Prompt e Oswald (Google Fonts) usadas no PDF. |
| `relatorio_her2_inteligencia_competitiva_*.pdf` | Relatórios gerados (saídas por data). |
| `pyproject.toml` / `uv.lock` | Definição do projeto e dependências (gerenciadas com `uv`). |
| `scripts/monthly_update.py` | Orquestrador da atualização mensal (fetch → relatório → verificação → trava de histórico). |
| `scripts/run_weekly_report.py` | Gera o PDF datado + `.kpis_*.json` e valida o artefato. |
| `scripts/verify_pdf_artifact.py` | Verificação estrutural do PDF (tamanho, 13–15 páginas, tokens do sumário). |
| `.kpis_YYYY-MM-DD.json` | KPIs de cada edição (histórico para comparação). |
| `main.py` | Stub gerado pelo `uv init` (não usado no fluxo principal). |

---

## Pré-requisitos

- **Python 3.13+**
- **[uv](https://docs.astral.sh/uv/)** para gerenciamento de pacotes e execução
  (este projeto usa `uv` — **não** use `pip`/`pip3`).

Dependências principais (declaradas em `pyproject.toml`): `matplotlib`, `numpy`, `pandas`,
`pillow`, `pymupdf`, `reportlab`, `squarify`. O `fetch_trials.py` usa `requests` (também declarado em `pyproject.toml`).

---

## Instalação

```bash
# Sincroniza o ambiente virtual com base no pyproject.toml / uv.lock
uv sync
```

> Se faltar alguma dependência de runtime, adicione-a com `uv add <pacote>`.

---

## Como atualizar o banco de dados

A atualização do banco é feita pelo script `fetch_trials.py`, que busca **todos** os
estudos da API v2 do ClinicalTrials.gov para o termo configurado, aplica os filtros e
grava os resultados em `her2_breast_cancer_trials.db`.

### Passo a passo

```bash
uv run fetch_trials.py
```

O script vai:

1. Conectar (ou criar) o banco em `her2_breast_cancer_trials.db`.
2. **Recriar a tabela `trial_snapshots`** (`DROP TABLE IF EXISTS` seguido de `CREATE`).
3. Paginar a API v2 (100 estudos por página) até esgotar os resultados.
4. Filtrar para manter apenas: status ativo/recrutando, fases 2–4 e tipo intervencional.
5. Remover o bloco de `locations` de cada estudo (para reduzir o tamanho do banco).
6. Gravar cada estudo como uma linha com o JSON completo (menos `locations`), carimbando
   a `collection_date` com a **data de execução** (`YYYY-MM-DD`).

Ao final, o script imprime quantos estudos foram salvos.

### ⚠️ Pontos de atenção

- **A atualização é uma substituição completa, não incremental.** O `fetch_trials.py`
  faz `DROP TABLE IF EXISTS trial_snapshots` antes de inserir. Cada execução apaga o
  snapshot anterior e grava um novo com a data de hoje. Se quiser **preservar o histórico
  de snapshots** (comparar coletas ao longo do tempo), faça um backup do `.db` antes de
  rodar, ou remova a linha do `DROP TABLE` para acumular snapshots por `collection_date`.

  ```bash
  cp her2_breast_cancer_trials.db her2_breast_cancer_trials.$(date +%F).bak.db
  uv run fetch_trials.py
  ```

- **Filtros e termo de busca** ficam no topo do `fetch_trials.py` (constantes
  `TARGET_STATUSES`, `TARGET_PHASES`, `TARGET_TYPE` e o `query.term`). Ajuste-os ali se
  precisar mudar o universo da coleta.

- **`DB_PATH`** do `fetch_trials.py` agora é relativo ao projeto (pode ser sobrescrito com a
  variável de ambiente `HER2_DB_PATH`). A API é consultada **antes** de tocar no banco; se falhar,
  ou se a coleta vier com menos de 50% do snapshot anterior, o banco não é substituído.

- **O bloco `locations` é descartado** na coleta. Por isso a análise geográfica e de
  presença no Brasil é necessariamente conservadora (heurística por nome de patrocinador +
  busca textual). Para uma análise geográfica real, edite `parse_study()` para **não**
  remover `contactsLocationsModule.locations` (o banco ficará maior).

- O relatório usa a **coleta mais recente** presente no banco (maior `collection_date`).
  Depois de atualizar o banco, gere o relatório novamente para refletir os novos dados.

---

## Como gerar o relatório

```bash
uv run generate_report_updated.py
```

O script:

1. Carrega os estudos do banco (`load_data()`), usando a coleta mais recente.
2. Renderiza gráficos (treemap, heatmap subtipo×estágio, donuts, análise regional) com
   matplotlib.
3. Monta o PDF com ReportLab e a identidade visual da Pesquisa e Dados.
4. Salva o arquivo definido em `PDF_PATH` (constante no topo do script).

> **Renomeie a saída por data** ajustando `PDF_PATH` no script (ex.:
> `relatorio_her2_inteligencia_competitiva_2026-06-12.pdf`) para não sobrescrever
> relatórios anteriores.

---

## Atualização mensal automatizada

Uma rotina agendada (Claude Code na nuvem) roda **todo dia 1º do mês** e executa:

```bash
uv sync
uv run scripts/monthly_update.py
```

O `scripts/monthly_update.py`:

1. registra o hash de todo o **histórico** (`relatorio_*.pdf`, `relatorio_*.txt`, `.kpis_*.json`);
2. roda `fetch_trials.py` (se a API falhar, o banco anterior é **preservado**);
3. confirma que o banco ficou com a coleta do dia;
4. gera `relatorio_her2_inteligencia_competitiva_YYYY-MM-DD.pdf` + `.kpis_YYYY-MM-DD.json`
   (`scripts/run_weekly_report.py`) e valida o PDF (`scripts/verify_pdf_artifact.py`);
5. imprime os KPIs vs. a edição anterior;
6. falha (exit 14) se qualquer arquivo de histórico tiver sido alterado ou removido.

Depois, a rotina faz `commit` + `push` do `.db`, do novo PDF e do novo `.kpis_*.json`. **Nada do
histórico é apagado**: cada edição é um arquivo novo datado, e o git guarda as versões anteriores do `.db`.

> ⚠️ O `.db` guarda só o **snapshot mais recente** (o `fetch_trials.py` substitui a tabela). O histórico
> de coletas vive nos PDFs, nos `.kpis_*.json` e no histórico do git.

> 🌐 O ambiente da rotina precisa de acesso de rede a **`clinicaltrials.gov`** (política de rede do
> ambiente do Claude Code na nuvem). Sem isso, o `fetch_trials.py` falha e nada é commitado.

Para rodar manualmente (ou testar sem consultar a API): `uv run scripts/monthly_update.py [--skip-fetch] [--force]`.

---

## Esquema do banco de dados

Tabela principal: **`trial_snapshots`**

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `nct_id` | TEXT | Identificador NCT do estudo. |
| `collection_date` | TEXT | Data da coleta (`YYYY-MM-DD`). |
| `status` | TEXT | Status geral (overallStatus). |
| `phase` | TEXT | Fase(s) do estudo. |
| `full_data_json` | TEXT | Objeto do estudo da API v2 (JSON), sem `locations`. |

> Chave primária: (`nct_id`, `collection_date`).

O `full_data_json` é o objeto `protocolSection.*` do ClinicalTrials.gov — toda a análise
do relatório é derivada dele.

> Obs.: o arquivo `.db` também contém uma tabela legada `trials` (esquema tabular
> simplificado), não utilizada pelo fluxo atual.

---

## Metodologia e limitações

- **Fonte:** ClinicalTrials.gov (U.S. National Library of Medicine), API v2.
- **Filtros:** Fases 2/3/4, tipo Interventional, status ativo/recrutando.
- **Classificação clínica:** processamento textual (não é curadoria manual); espere uma
  pequena fração de "não especificado".
- **Geografia:** o módulo de localizações é removido na coleta; a presença geográfica
  (incluindo Brasil) é estimada por heurística de patrocinador + busca textual e deve ser
  lida com cautela.
- **Fontes:** Prompt e Oswald não possuem alguns glifos (emoji, `●`, `▸`); o gerador usa
  `•` e `→` para evitar caracteres ausentes (tofu) no PDF.

---

*Relatório de uso interno — Pesquisa e Dados · www.pesquisaedados.com*
