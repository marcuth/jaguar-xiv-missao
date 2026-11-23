# Configuração

Tudo vem do `.env` (copie de `.env.example`, que traz todas as variáveis comentadas). A leitura é feita por `config.py::Settings` (pydantic-settings): nomes **não** diferenciam maiúsculas, variáveis desconhecidas são ignoradas e listas são separadas por vírgula.

Valores vazios em caminhos (`WATERMARK_PATH=`) significam "desligado".

## Fontes

| Variável | Padrão | Descrição |
|---|---|---|
| `SOURCE_LIVE_PLAYLIST_IDS` | vazio | IDs `UULV…` (ou `UC…`) das lives dos canais monitorados |
| `POLL_INTERVAL_SECONDS` | 900 | Intervalo do comando `watch` |
| `SOURCE_MAX_AGE_HOURS` | 48 | Ignora lives mais antigas que isso |
| `SOURCE_FALLBACK_LIMIT` | 5 | Lives lidas via yt-dlp se o RSS falhar; 0 desliga |
| `SOURCE_MIN_DURATION_SECONDS` | 600 | Vídeo-fonte mais curto é ignorado |
| `SOURCE_MAX_DURATION_SECONDS` | 36000 | Vídeo-fonte mais longo é ignorado |
| `LIVE_CAPTION_WAIT_MINUTES` | 90 | Espera pela legenda antes de recorrer ao Whisper |

## Relevância

| Variável | Padrão | Descrição |
|---|---|---|
| `TARGET_KEYWORDS` | nomes do MBL/Missão | Termos que tornam um vídeo candidato (sem acento nem caixa) |
| `MIN_KEYWORD_MENTIONS` | 3 | Menções mínimas na transcrição |
| `TRIAGE_MIN_SCORE` | 0,7 | Nota mínima da triagem para gastar Whisper |

## Cortes

| Variável | Padrão | Descrição |
|---|---|---|
| `CLIP_MIN_SECONDS` | 600 | Duração mínima |
| `CLIP_MAX_SECONDS` | 2400 | Duração máxima |
| `CLIP_TARGET_SECONDS` | 1320 | Duração ideal informada à IA |
| `CLIP_MIN_SCORE` | 0,6 | Nota mínima (0 a 1) |
| `MAX_CLIPS_PER_VIDEO` | 3 | Máximo de cortes por live |
| `CLIP_EDGE_PADDING_SECONDS` | 0,5 | Folga em cada ponta |
| `SELECTION_WINDOW_SECONDS` | 3600 | Tamanho da janela de análise |
| `SELECTION_WINDOW_OVERLAP_SECONDS` | 300 | Sobreposição entre janelas |

## Silêncio

| Variável | Padrão | Descrição |
|---|---|---|
| `SILENCE_CUT_ENABLED` | true | Liga o corte de silêncio |
| `SILENCE_THRESHOLD_DB` | −35 | Abaixo disso é silêncio |
| `SILENCE_MIN_DURATION_SECONDS` | 0,8 | Só pausas maiores são encurtadas |
| `SILENCE_KEEP_PADDING_SECONDS` | 0,25 | Parte da pausa mantida em cada ponta |

## Overlays, CTA e outro

| Variável | Padrão | Descrição |
|---|---|---|
| `WATERMARK_PATH` | vazio | PNG com transparência |
| `WATERMARK_FIT` | width | `width` ou `stretch` (moldura em tela cheia) |
| `WATERMARK_POSITION` | top-right | Posição (ignorada em `stretch`) |
| `WATERMARK_WIDTH_PCT` | 0,14 | Largura relativa (ignorada em `stretch`) |
| `WATERMARK_OPACITY` | 0,85 | Opacidade |
| `WATERMARK_MARGIN_PX` | 24 | Margem (ignorada em `stretch`) |
| `CTA_VIDEO_PATH` | vazio | Vídeo inserido no meio do corte |
| `CTA_POSITION_PCT` | 0,5 | Ponto do corte (0 a 1) onde o CTA entra |
| `CTA_MIN_CLIP_SECONDS` | 480 | Cortes mais curtos não recebem CTA |
| `OUTRO_PATH` | vazio | Vídeo anexado ao fim |

## Render

| Variável | Padrão | Descrição |
|---|---|---|
| `RENDER_ENGINE` | ffmpeg | `ffmpeg` (rápido) ou `moviepy` (reserva lenta) |
| `RENDER_FPS` | 30 | Quadros por segundo |
| `RENDER_PRESET` | medium | Preset do x264 (mais lento = arquivo menor) |
| `RENDER_CRF` | 21 | Qualidade (menor = melhor e maior) |
| `RENDER_THREADS` | 4 | Threads do x264 |
| `RENDER_VIDEO_ENCODER` | h264_nvenc | `h264_nvenc` (GPU NVIDIA) ou `libx264` (CPU) |
| `MAX_SOURCE_HEIGHT` | 1080 | Altura máxima do download |

## IA

Veja [ai.md](ai.md).

| Variável | Padrão |
|---|---|
| `AI_PROVIDER` | openai |
| `AI_BASE_URL` | vazio |
| `AI_API_KEY` | vazio |
| `AI_PROTOCOL` | auto |
| `AI_MODEL` | gpt-4.1-mini |
| `AI_TEMPERATURE` | 0,3 |
| `AI_MAX_RETRIES` | 0 |
| `AI_RETRY_DELAY_SECONDS` | 5 |
| `AI_RETRY_MAX_DELAY_SECONDS` | 60 |

## Transcrição

| Variável | Padrão | Descrição |
|---|---|---|
| `TRANSCRIPT_LANGUAGES` | pt,pt-BR | Idiomas da legenda |
| `WHISPER_MODEL` | small | Modelo do faster-whisper |
| `WHISPER_DEVICE` | auto | `auto`, `cpu` ou `cuda` |
| `WHISPER_COMPUTE_TYPE` | int8 | Precisão do cálculo |

## Metadados

| Variável | Descrição |
|---|---|
| `TITLE_MAX_CHARS` | Limite do título (100) |
| `FIXED_TAGS` | Tags sempre presentes |
| `FIXED_HASHTAGS` | Hashtags no fim da descrição |
| `DESCRIPTION_HEADER` | Texto no **início** da descrição (ex.: aviso de canal de cortes) |
| `DESCRIPTION_FOOTER` | Texto no **fim** da descrição, antes das hashtags |
| `WATCH_MORE_LABEL`, `WATCH_MORE_URL` | Linha "Quer saber mais?" com link |
| `SOCIAL_LINKS` | Linhas `Rótulo: url`, separadas por vírgula |

## Publicação e fila

| Variável | Padrão | Descrição |
|---|---|---|
| `PUBLISH_MODE` | dry_run | `dry_run` ou `youtube` |
| `YOUTUBE_PRIVACY_STATUS` | private | `private`, `unlisted` ou `public` (ignorada com a fila ligada) |
| `YOUTUBE_CATEGORY_ID` | 25 | Notícias e política |
| `YOUTUBE_CLIENT_SECRETS_FILE` | secrets/client_secret.json | Credencial OAuth |
| `YOUTUBE_TOKEN_FILE` | secrets/youtube_token.json | Token salvo |
| `MAX_PUBLISH_PER_DAY` | 5 | Limite de envios por dia |
| `PUBLISH_SCHEDULE_ENABLED` | false | Liga a fila de postagem |
| `PUBLISH_TIMEZONE` | America/Sao_Paulo | Fuso dos horários |
| `PUBLISH_SLOTS` | vazio | Horários fixos `HH:MM` |
| `PUBLISH_WINDOW_START` / `PUBLISH_WINDOW_END` | 09:00 / 22:00 | Janela da distribuição automática |
| `PUBLISH_MIN_LEAD_MINUTES` | 30 | Antecedência mínima do horário |
| `PUBLISH_QUEUE_DAYS` | 3 | Dias à frente que a fila aceita |

## Thumbnails

Veja [thumbnails.md](thumbnails.md): `THUMBNAIL_PROVIDER`, `THUMBNAIL_SAMPLE_COUNT`, `THUMBNAIL_FACE_MIN_CONFIDENCE`, `THUMBNAIL_MAX_ZOOM`, `THUMBNAIL_ACCENT_COLOR`, `THUMBNAIL_FONT_PATH`, `THUMBNAIL_LOGO_PATH`.

## Outros

| Variável | Padrão | Descrição |
|---|---|---|
| `DATA_DIR` | data | Raiz de banco, cortes e downloads |
| `NOTIFY_WEBHOOK_URL` | vazio | Webhook (Discord/Slack) |
| `LOG_LEVEL` | INFO | Nível de log |

## Checklist para produção

1. `AI_API_KEY` (e `AI_MODEL`, `AI_BASE_URL` se não for OpenAI).
2. `SOURCE_LIVE_PLAYLIST_IDS` com os canais desejados.
3. `secrets/client_secret.json` + `auth-youtube` rodado uma vez.
4. `PUBLISH_MODE=youtube` e, no começo, `YOUTUBE_PRIVACY_STATUS=private`.
5. `MAX_PUBLISH_PER_DAY` e a fila (`PUBLISH_SCHEDULE_ENABLED`) conforme a cota.
6. `pip install -e .[whisper]` se quiser transcrever lives sem legenda.
7. Um runtime JavaScript (deno ou node) instalado para o yt-dlp.
8. Testar um ciclo completo em `dry_run` antes de publicar.
