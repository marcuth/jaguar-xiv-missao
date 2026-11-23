# Edição de vídeo

Código: `editing/` (`silence.py`, `insertion.py`, `overlay.py`, `ffmpeg_renderer.py`, `renderer.py`, `render_factory.py`).

## Visão geral

Para cada candidato, a edição acontece nesta ordem:

```
trecho [start, end] do vídeo completo
  → detecção de silêncio (ffmpeg silencedetect)
  → plano de trechos a manter (plan_keep_ranges)
  → ponto de inserção do CTA (choose_insert_point)
  → render: trim + concat → moldura → [CTA no meio] → [outro no fim]
```

## Corte de silêncio

Objetivo: encurtar pausas longas sem destruir o ritmo natural da fala (o canal-alvo preserva o ritmo).

1. `FfmpegSilenceDetector.detect` roda `silencedetect` no trecho (`SILENCE_THRESHOLD_DB`, padrão −35 dB) e lê as pausas da saída do ffmpeg.
2. `plan_keep_ranges` considera só pausas com pelo menos `SILENCE_MIN_DURATION_SECONDS` (padrão 0,8 s). De cada pausa, mantém `SILENCE_KEEP_PADDING_SECONDS` (0,25 s) em cada ponta e remove o miolo.
3. O resultado é a lista de trechos a manter, em tempo relativo; o pipeline soma `candidate.start` para obter tempos absolutos.

`SILENCE_CUT_ENABLED=false` mantém o trecho inteiro (`NullSilenceDetector`). Como o silêncio é removido, a duração final do corte pode ficar abaixo do mínimo configurado (um corte de 9,6 min a partir de 10 min, por exemplo).

## Moldura (overlay em tela cheia)

Um PNG com transparência desenhado sobre **o corpo do vídeo** (nunca sobre o CTA nem o outro).

| `WATERMARK_FIT` | Comportamento |
|---|---|
| `width` | Largura = `WATERMARK_WIDTH_PCT` do vídeo, aspecto mantido, posicionado por `WATERMARK_POSITION` e `WATERMARK_MARGIN_PX` |
| `stretch` | O PNG é esticado à largura e altura do vídeo, em qualquer resolução (moldura). Ignora posição, largura e margem |

Configuração típica de moldura em tela cheia:

```
WATERMARK_PATH=assets/images/moldura.png
WATERMARK_POSITION=center
WATERMARK_WIDTH_PCT=1.0
WATERMARK_OPACITY=1
WATERMARK_MARGIN_PX=0
WATERMARK_FIT=stretch
```

Com `stretch`, um vídeo de 720p recebe a moldura redimensionada para 1280×720 automaticamente. Se a proporção da moldura for diferente da do vídeo, ela será deformada; use uma moldura 16:9.

## CTA como vídeo no meio do corte

`CTA_VIDEO_PATH` aponta um vídeo curto (chamada para ação, anúncio) inserido **dentro** do corte, como uma inserção de anúncio. Ele substitui o antigo overlay de imagem.

### Quando entra
Só em cortes com duração `>= CTA_MIN_CLIP_SECONDS` (padrão 480 s). Cortes curtos não recebem.

### Onde entra (`choose_insert_point`)
Decisão determinística, em código:

1. Alvo = ponto do corte em `CTA_POSITION_PCT` (padrão 0,5, o meio).
2. Candidatos = fins de frase da transcrição dentro de uma janela de ±20% do corte em torno do alvo (ignorando o primeiro e o último segundo).
3. Prefere o fim de frase seguido da **maior pausa**, contando a pausa só até 2 s. Empate vai para o mais próximo do alvo.
4. Se nenhum fim de frase cair na janela, usa o mais próximo do alvo. Sem fronteira nenhuma, não insere.

`to_relative` converte esse tempo absoluto para o tempo do corte já sem os silêncios, e o renderer ainda exige uma margem mínima de 0,5 s das pontas.

### Tratamento do CTA e do outro
- Esticados ao tamanho do corte, mesmo fps, áudio estéreo a 48 kHz.
- Se não têm áudio, é gerado silêncio da mesma duração para o concat não perder a sincronia.
- Não recebem moldura.

## Outro (encerramento)

`OUTRO_PATH` é um vídeo opcional anexado ao fim de todo corte, com o mesmo tratamento do CTA.

## Renderização com ffmpeg (padrão)

`FfmpegRenderer` monta **um único `filter_complex`**, sem passar frames pelo Python:

```
[0:v] split → trim/setpts por trecho → concat → scale/fps → overlay (moldura) → format
[0:a] asplit → atrim/asetpts por trecho → concat → aresample/aformat
corpo → (split em dois com CTA entre eles) → (+ outro) → concat final → libx264 + aac
```

Pontos importantes:
- **Janela de entrada:** `-ss`/`-t` decodificam só o trecho do corte; os tempos viram relativos a ele.
- **Script do grafo em arquivo:** cortes com centenas de trechos estourariam o limite da linha de comando. O grafo vai para um arquivo temporário (`-/filter_complex` no ffmpeg ≥ 7, com `-filter_complex_script` como alternativa para versões antigas).
- **ffmpeg embutido:** `ffmpeg_exe()` usa o binário do `imageio-ffmpeg`; se indisponível, o `ffmpeg` do PATH.
- **Sem `ffprobe`:** `probe()` lê tamanho, duração e presença de áudio da saída de `ffmpeg -i`.
- **Requisito:** o vídeo-fonte precisa ter áudio; sem áudio o render falha de propósito.
- **Saída:** `h264_nvenc` (GPU NVIDIA, padrão) ou `libx264` (CPU), `yuv420p`, `aac 192k`, `+faststart`. NVENC usa preset `p4` e qualidade constante `RENDER_CRF` via `-cq`; x264 mantém `RENDER_PRESET`, `RENDER_CRF` e `RENDER_THREADS`.
- NVENC requer um FFmpeg no PATH compilado com suporte a `h264_nvenc` e driver NVIDIA compatível. Se indisponível, o render falha com o erro do FFmpeg; configure `RENDER_VIDEO_ENCODER=libx264` para usar CPU.

Desempenho observado: ~12 s com ffmpeg contra ~228 s com moviepy para o mesmo corte, com saída equivalente.

## Reserva: moviepy

`RENDER_ENGINE=moviepy` usa `ClipRenderer`, que passa cada frame pelo Python e leva dezenas de minutos em cortes longos. Existe só como alternativa; aceita as mesmas entradas (`insert_at`, CTA, outro, overlays).

## Variáveis relacionadas

`SILENCE_*`, `WATERMARK_*`, `CTA_VIDEO_PATH`, `CTA_POSITION_PCT`, `CTA_MIN_CLIP_SECONDS`, `OUTRO_PATH`, `RENDER_*`, `MAX_SOURCE_HEIGHT`.
