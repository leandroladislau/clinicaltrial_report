# Procedimento da rotina mensal — Relatório HER2+

Executado pela sessão executora do Claude Code (que tem este repositório como fonte, com push) todo dia 1º
do mês. Não crie análises nem coletas novas: apenas execute o pipeline existente.

## Regras invioláveis

- Nunca apague, renomeie ou sobrescreva `relatorio_*.pdf`, `relatorio_*.txt` ou `.kpis_*.json` existentes.
- Sem force-push, sem reescrever histórico, sem PR. Publique **direto na `main`**.
- Sem dados simulados e sem `--skip-fetch`.

## Passos (a partir da raiz do repositório clonado na sessão)

1. `git fetch origin main && git checkout main && git pull --ff-only origin main`.
   Se o `--ff-only` falhar, PARE e informe (não force).
2. `uv sync` (sempre `uv`; nunca `pip`).
3. `uv run scripts/monthly_update.py`. Códigos de saída:
   - `0` ok
   - `10` PDF do dia já existe (não use `--force`; apenas informe)
   - `11` fetch falhou
   - `12` banco sem a coleta de hoje
   - `13` geração/validação do relatório falhou
   - `14` histórico alterado

   Em QUALQUER código diferente de 0: NÃO commite nem faça push; restaure alterações indevidas com
   `git checkout -- <arquivo>`, remova arquivos novos não rastreados criados pela execução e reporte o erro.
   Se o fetch falhar com 403/erro de rede para `clinicaltrials.gov`, informe que a política de rede do
   ambiente precisa liberar esse host (Network access → Allowed domains).
4. Se exit 0, `git status --short` deve listar SOMENTE `her2_breast_cancer_trials.db` (modificado),
   `relatorio_her2_inteligencia_competitiva_AAAA-MM-DD.pdf` e `.kpis_AAAA-MM-DD.json` (novos).
   Qualquer outra mudança: investigue antes de commitar.
5. `git add` desses 3 arquivos. Commit em pt-BR:
   `update AAAA-MM: relatório HER2+ mensal (coleta AAAA-MM-DD, N estudos)`, terminando com as linhas de
   atribuição fornecidas pelo ambiente. Depois `git push origin main` (falha de rede: até 4 tentativas com
   espera de 2s/4s/8s/16s; rejeição por divergência: `git pull --rebase origin main` e repita; nunca force).
6. Confirme com `git ls-remote origin main` que o hash remoto é o do seu commit. Se o push for recusado
   (403, proteção de branch) ou o hash não bater, NÃO diga que deu certo: o commit só existe no contêiner;
   informe que NÃO foi publicado e envie PushNotification.
7. Resposta final curta em pt-BR: data da coleta, nº de estudos, tabela de KPIs (esta edição vs. anterior,
   com variação), nome do PDF e hash do commit PUBLICADO. Seja honesto sobre qualquer falha ou etapa pulada.
