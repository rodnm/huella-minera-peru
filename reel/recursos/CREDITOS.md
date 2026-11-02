# Créditos y licencias de los recursos del reel

## Tipografías

Se descargan con `uv run python -m reelkit.fonts` desde el repositorio [google/fonts](https://github.com/google/fonts), fijado en el commit `9862abc066c9b83bf84c3e8ed1fc2d8d48f9bbf0`. Cada archivo se verifica con el SHA-256 fijado en `reelkit/fonts.py`. Quedan en `recursos/fuentes/`, que git ignora, junto con el texto de cada licencia.

| Familia | Uso en el reel | Archivo | Licencia |
|---|---|---|---|
| Fraunces (Undercase Type) | Título y etiquetas sin cifra | [`ofl/fraunces/Fraunces[SOFT,WONK,opsz,wght].ttf`](https://raw.githubusercontent.com/google/fonts/9862abc066c9b83bf84c3e8ed1fc2d8d48f9bbf0/ofl/fraunces/Fraunces%5BSOFT,WONK,opsz,wght%5D.ttf) | [SIL Open Font License 1.1](https://raw.githubusercontent.com/google/fonts/9862abc066c9b83bf84c3e8ed1fc2d8d48f9bbf0/ofl/fraunces/OFL.txt) |
| IBM Plex Sans (IBM) | Subtítulos, etiquetas, pie y créditos | [`ofl/ibmplexsans/IBMPlexSans[wdth,wght].ttf`](https://raw.githubusercontent.com/google/fonts/9862abc066c9b83bf84c3e8ed1fc2d8d48f9bbf0/ofl/ibmplexsans/IBMPlexSans%5Bwdth,wght%5D.ttf) | [SIL Open Font License 1.1](https://raw.githubusercontent.com/google/fonts/9862abc066c9b83bf84c3e8ed1fc2d8d48f9bbf0/ofl/ibmplexsans/OFL.txt) |
| IBM Plex Sans Condensed (IBM) | Cifras grandes | [`IBMPlexSansCondensed-SemiBold.ttf`](https://raw.githubusercontent.com/google/fonts/9862abc066c9b83bf84c3e8ed1fc2d8d48f9bbf0/ofl/ibmplexsanscondensed/IBMPlexSansCondensed-SemiBold.ttf), [`IBMPlexSansCondensed-Bold.ttf`](https://raw.githubusercontent.com/google/fonts/9862abc066c9b83bf84c3e8ed1fc2d8d48f9bbf0/ofl/ibmplexsanscondensed/IBMPlexSansCondensed-Bold.ttf) | [SIL Open Font License 1.1](https://raw.githubusercontent.com/google/fonts/9862abc066c9b83bf84c3e8ed1fc2d8d48f9bbf0/ofl/ibmplexsanscondensed/OFL.txt) |

La OFL permite usar las fuentes en videos e imágenes sin atribución obligatoria; igual se citan aquí.

## Modelos

| Modelo | Uso | Licencia |
|---|---|---|
| [Qwen/Qwen3-TTS-12Hz-0.6B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base) (Alibaba) | Narración con la voz clonada del autor | Apache 2.0 |
| [faster-whisper large-v3-turbo](https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo) (OpenAI Whisper, conversión CTranslate2) | Recorte de la referencia, control de WER y subtítulos | MIT |

## Música

La pista no se descarga ni se versiona: la elige el autor y la guarda en `recursos/musica/`, que git ignora, porque estas licencias no están pensadas para redistribuir el archivo suelto. Antes de publicar, anoten aquí el título, el autor, el enlace y la licencia, y copien la misma línea en `creditos` del guion, por ejemplo `"Música: «Título» de Autor (Pixabay Content License)"`.

| Pista | Autor | Enlace | Licencia | Fecha de descarga |
|---|---|---|---|---|
| «Secret Garden», primeros 30 s, repetidos bajo la voz en un editor de video | Eugenio Mininni | <https://mixkit.co/free-stock-music/> | [Mixkit Stock Music Free License](https://mixkit.co/license/#musicFree) | 2026-11-01 |

## Código base

El pipeline se basa en la sesión 15 del curso, [d2cml-ai/Data-Science-Python, `sessions/15-texto-a-reel`](https://github.com/d2cml-ai/Data-Science-Python/tree/main/sessions/15-texto-a-reel) (`reel.py`, `hacer_reel.py`).
