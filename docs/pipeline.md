# Pipeline

`pipeline.py::Pipeline` orquestra tudo. `run_once()` percorre os vídeos da fonte e chama `process()` para cada um que o estado ainda não considera concluído.

## Fluxo de um vídeo

```
source.latest()                       (RSS, ou yt-dlp se o RSS falhar)
  └─ store.seen(id)?  sim → pula (exceto failed/waiting)
  └─ process(video)
       1. downloader.enrich      duração, descrição, data, live_status
       2. live em andamento?     → VideoWaiting, SEM gravar no estado
       3. _reject_reason         não é live / antigo demais / curto / longo → skipped
       4. _transcribe            legenda → (espera) → triagem → Whisper
       5. _mentions_enough       menções mínimas aos alvos → senão skipped
       6. selector.select        IA sugere + regras fixas
       7. para cada candidato:
            limite diário atingido?     → retorna sem marcar o vídeo
            fila de postagem cheia?     → retorna sem marcar o vídeo
            já feito (clip_done)?       → pula
            baixa o vídeo completo (1x)
            _make_clip                  silêncio, CTA, render, metadados, thumbnail, publicação
       8. cleanup do download; marca o vídeo como done
```

Qualquer exceção em `process` marca o vídeo como `failed`, publica `PipelineError` e a rodada segue para o próximo.

## Etapas em detalhe

### 1. `enrich`
O RSS não traz duração nem estado de live. O `yt-dlp` (sem baixar) completa `duration`, `description`, `channel`, `live_status` e a data de publicação (`release_timestamp` ou `timestamp`) quando a fonte não a trouxe.

### 2. Live em andamento
`is_upcoming`, `is_live` e `post_live` retornam sem gravar nada: a próxima rodada reavalia sozinha.

### 3. Filtros de elegibilidade (`_reject_reason`)
Aplicados na ordem. Com `force=True` (comando `process`) as duas primeiras regras são ignoradas.

| Regra | Motivo registrado |
|---|---|
| `live_status != was_live` | `não é uma live` |
| Mais velho que `SOURCE_MAX_AGE_HOURS` | `antigo demais (Nh)` |
| Duração < `SOURCE_MIN_DURATION_SECONDS` | `muito curto (Ns)` |
| Duração > `SOURCE_MAX_DURATION_SECONDS` | `muito longo (Ns)` |

### 4. Transcrição
Detalhes em [transcription-and-relevance.md](transcription-and-relevance.md). Resumo: tenta a legenda do YouTube; se não existir e a live acabou há pouco, espera `LIVE_CAPTION_WAIT_MINUTES`; depois a IA faz triagem e só então o Whisper local transcreve.

### 5. Pré-filtro de menções
Conta menções de `TARGET_KEYWORDS` no título, na descrição e na transcrição. Menos que `MIN_KEYWORD_MENTIONS` → `poucas menções aos alvos`. É um filtro barato que evita gastar IA em lives sem relação.

### 6. Seleção
Detalhes em [clip-selection.md](clip-selection.md).

### 7. Fabricação de cada corte (`_make_clip`)
1. **Silêncio:** se `SILENCE_CUT_ENABLED`, detecta pausas no trecho e planeja os trechos a manter. Senão, mantém o trecho inteiro.
2. **CTA:** se há `CTA_VIDEO_PATH` e o corte tem pelo menos `CTA_MIN_CLIP_SECONDS`, escolhe o ponto de inserção ([video-editing.md](video-editing.md)).
3. **Render:** `renderer.render(source, keep, out, insert_at)` produz `data/clips/<id>_<ini>_<fim>.mp4`.
4. **Metadados:** título, descrição, tags e texto da thumbnail ([metadata.md](metadata.md)).
5. **Thumbnail:** opcional; uma falha é registrada e a publicação segue sem ela.
6. **Publicação:** pede o próximo horário livre se a fila estiver ligada, envia, grava o corte em `clips` e publica `ClipPublished`.

## Estados de um vídeo

| Estado | Significado | `seen()` | Volta a ser processado? |
|---|---|---|---|
| (nenhum) | Live em andamento ou limite diário/fila cheia | falso | Sim, na próxima rodada |
| `waiting` | Live encerrada sem legenda, aguardando | falso | Sim, até passar `LIVE_CAPTION_WAIT_MINUTES` |
| `skipped` | Descartado com motivo | verdadeiro | Não |
| `done` | Todos os cortes processados | verdadeiro | Não |
| `failed` | Exceção durante o processamento | falso | Sim, na próxima rodada |

Lives agendadas que o `yt-dlp` ainda não consegue abrir são reconhecidas como `is_upcoming` e ficam em espera; não são registradas como falha.

`mark_waiting` não altera `updated_at` se o vídeo já estava esperando, então o relógio da espera não é reiniciado a cada rodada.

## Limites que interrompem sem marcar o vídeo

- `MAX_PUBLISH_PER_DAY` (contado pelos **envios** feitos hoje, protege a cota da API).
- Fila de postagem cheia dentro de `PUBLISH_QUEUE_DAYS`.

Nos dois casos o loop de candidatos para, o vídeo não é marcado como `done`, e a rodada seguinte retoma os cortes que ainda faltam (`clip_done` evita repetir os já publicados).

## Download e limpeza

O vídeo é baixado **inteiro uma vez** (até `MAX_SOURCE_HEIGHT`), pois baixar trechos é muito mais lento pelo limite de velocidade do YouTube. Os cortes são locais. O bloco `finally` chama `cleanup(video_id)`, que apaga o vídeo, o áudio e partes. Consequência: se o envio falhar, uma nova tentativa baixa e renderiza tudo de novo.

## Reprocessamento manual

`python -m jaguar_xiv_missao process <url-ou-id>` marca o vídeo como `failed` ("reprocessamento manual") para liberá-lo e roda `process(force=True)`, ignorando as regras de live e de idade.
