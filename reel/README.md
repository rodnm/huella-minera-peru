# Reel: guion → voz clonada → video 9:16

Estas herramientas convierten un guion (`guion.json`) y un visual por escena en un video vertical de 1080 × 1920 con:

- narración generada con IA a partir de la voz del autor (Qwen3-TTS);
- subtítulos karaoke sincronizados y un archivo `.srt`;
- música de fondo con licencia, entre 18 y 20 dB por debajo de la voz;
- el aviso «VOZ GENERADA CON IA» visible durante todo el video;
- la fuente de los datos en el pie y una tarjeta final de créditos y fuentes.

Se basa en el pipeline de la [sesión 15 del curso](https://github.com/d2cml-ai/Data-Science-Python/tree/main/sessions/15-texto-a-reel) (`reel.py`, `hacer_reel.py`).

## Pasos

| Paso | Qué hace | Archivo |
|---|---|---|
| 1. Referencia de voz | Transcribe la grabación del autor con Whisper y recorta un tramo de 15 a 25 s que termina en una frase completa | `preparar_voz.py` → `voz/referencia.wav`, `voz/referencia.txt` |
| 2. Guion | Escenas con `frase`, `cifra`, `etiqueta` y `visual` (ver el esquema abajo) | `guion.json` |
| 3. Revisión del diseño | Dibuja el reel con tiempos estimados, sin voz, para revisar textos y visuales | `hacer_reel.py --solo-visual` |
| 4. Narración | Qwen3-TTS 0.6B narra cada escena con la voz clonada; se guarda en caché por escena | `reelkit/narration.py` |
| 5. Control de calidad | Whisper transcribe cada escena sin ver el guion y mide el WER; si pasa de 0.25, la escena se genera otra vez | `reelkit/asr.py` |
| 6. Subtítulos | Tiempos por palabra de Whisper, en bloques de hasta 4 palabras | `salidas/subtitulos.srt` |
| 7. Mezcla | Música bajo la voz; sonoridad final de −14 LUFS y picos limitados a −1.5 dBFS | `reelkit/audio.py` |
| 8. Video | Cuadros con Pillow y codificación H.264 + AAC 48 kHz con ffmpeg | `salidas/reel.mp4`, `salidas/portada.png` |

## Entorno

El reel tiene su propio entorno, separado del `pyproject.toml` de la raíz, porque `qwen-tts` fija `transformers==4.57.3`.

```bash
cd reel
uv sync                           # Python 3.12; instala torch para CPU, qwen-tts, faster-whisper, etc.
uv run python -m reelkit.fonts    # opcional: baja las tipografías (el render también lo hace)
uv run pytest -q                  # pruebas sin red ni modelos
```

La primera narración descarga unos 2.4 GB del modelo de voz y 1.6 GB de Whisper en la caché de Hugging Face. `ffmpeg` viene dentro de `imageio-ffmpeg`. En la consola, `qwen-tts` avisa que faltan SoX y flash-attn; no hacen falta en CPU.

## Uso

```bash
# 1. Referencia de voz (una sola vez). La grabación no se copia ni se sube: solo se lee.
uv run python preparar_voz.py --voz "C:/ruta/a/mi_voz.m4a"
uv run python preparar_voz.py --voz "C:/ruta/a/mi_voz.m4a" --inicio 42.5 --fin 61.0   # tramo elegido a mano

# 2. Revisión rápida del diseño, sin voz (unos 12 s para 16 s de video)
uv run python hacer_reel.py --guion guion.json --solo-visual --autor "Nombre Apellido"

# 3. Reel completo
uv run python hacer_reel.py --guion guion.json --musica recursos/musica/pista.mp3 --autor "Nombre Apellido"
```

Opciones de `hacer_reel.py`:

| Opción | Uso |
|---|---|
| `--guion` | Guion JSON. Las rutas de `visual` son relativas a `reel/`. |
| `--autor` | Nombre que aparece en el pie y en la tarjeta de créditos. |
| `--musica` | Pista con licencia (mp3, wav, m4a u ogg). Sin ella, el reel se genera sin música y se muestra un aviso. |
| `--solo-visual` | Sin voz ni modelos: tiempos estimados a 2.6 palabras por segundo. Escribe `reel_visual.mp4` y `portada_visual.png`. |
| `--voz` | Referencia de voz (por defecto `voz/referencia.wav`, con su `.txt` al lado). |
| `--musica-db` | Distancia de la música bajo la voz mientras habla, en dB (por defecto 19). |
| `--max-wer` | Umbral para regenerar una escena (por defecto 0.25). |
| `--salidas` | Carpeta de salida (por defecto `salidas/`). |

Salidas en `salidas/`, que git ignora:

| Archivo | Contenido |
|---|---|
| `reel.mp4` | Video final, 1080 × 1920, 30 fps, H.264 y AAC 48 kHz estéreo |
| `subtitulos.srt` | Subtítulos con los mismos tiempos que el audio |
| `portada.png` | Cuadro de la primera escena, sin subtítulos, para la miniatura |
| `informe.json` | WER y transcripción de Whisper por escena, duraciones, sonoridad medida y avisos |
| `cache/tts/` | Audio de cada escena; al cambiar una frase solo esa escena se vuelve a narrar |

Al final, el script imprime la resolución y la duración del video, la sonoridad medida y avisos si el reel no cumple los 45 a 75 s o las 5 a 7 escenas que pide la tarea.

El video publicado está en [`reel.mp4`](reel.mp4), con sus subtítulos en [`subtitulos.srt`](subtitulos.srt). Es el render de `salidas/` con la música mezclada en un editor de video, por eso no se regenera idéntico con este script.

## Escenas

Los visuales de `guion.json` no se versionan: se generan desde los datos del proyecto, con el entorno de la raíz.

```bash
uv run python -m scripts.construir_escenas      # mapas y gráficos
python scripts/capturar_dashboard.py            # última escena; requiere Playwright y la app corriendo
```

## Guion

```json
{
  "titulo": "La huella de la minería en el Perú",
  "fuente": "Fuente: MapBiomas Perú (Col. 4) y Amazon Mining Watch",
  "creditos": [
    "Datos: MapBiomas Perú y Amazon Mining Watch (enlaces en el repositorio)",
    "Música: «Título» de Autor (Pixabay Content License)",
    "Voz generada con IA a partir de la voz del autor"
  ],
  "escenas": [
    {
      "frase": "Visto desde el espacio, el Perú minero se encendió en solo doce años.",
      "cifra": "12 años",
      "etiqueta": "Una noche por año, de 2013 a 2024",
      "visual": "escenas/01_peru_se_enciende/",
      "encaje": "contener",
      "zoom": 0.04
    }
  ]
}
```

- `frase`: lo que dice la voz. Los números van en palabras («doce años», «ocho punto siete») para que la voz los pronuncie bien; el script avisa si encuentra dígitos.
- `cifra`: la cifra en pantalla, con dígitos y corta. Puede quedar vacía; entonces la etiqueta se muestra en grande.
- `etiqueta`: de 3 a 8 palabras.
- `visual`: una imagen PNG o JPG, o una carpeta de PNG numerados (`0001.png`, `0002.png`…), que se reproduce a lo largo de la escena y sostiene el último cuadro en el 20 % final. El tamaño ideal es 1080 × 960. Los degradados oscuros y lisos se ven en franjas al codificar en H.264; un grano leve (ruido de ±1 nivel) lo evita.
- `encaje` (opcional): `contener` (por defecto, nunca recorta) o `cubrir` (llena el recuadro y recorta los bordes).
- `zoom` (opcional): acercamiento lento sobre imágenes fijas, de 0 a 0.3 (por defecto 0.04).
- Las cifras de cada frase deben salir de los hallazgos del análisis (S5).

## Diseño del cuadro

| Zona (px, de arriba abajo) | Contenido |
|---|---|
| 92–100 | Barra de avance |
| 116–186 | Título (Fraunces) |
| 200–252 | Aviso «VOZ GENERADA CON IA», en todos los cuadros |
| 272–1232 | Visual de la escena, a lo ancho (la mitad del cuadro); ningún texto se dibuja encima |
| 1256–1508 | Cifra (IBM Plex Sans Condensed) y etiqueta |
| 1528–1690 | Subtítulos karaoke (IBM Plex Sans), con la palabra dicha resaltada |
| 1706–1800 | Fuente de los datos y autor |

Los colores salen de `../design/tokens.json`, el mismo archivo que usan el dashboard y los gráficos: el fondo, el panel y los textos de `surface`, el acento de `series.mining` y el resaltado del último tono de `ramps.radiance`. Cada texto se mide con `textbbox` y se achica, se parte en líneas o se recorta con «…» hasta que entra en su zona. Entre escenas, los visuales se funden en 0.45 s; la cifra y la etiqueta aparecen con un fundido corto. La tarjeta de créditos dura 4 s y ocupa el recuadro del visual.

## Música y licencias

- No se descarga música. El autor elige una pista con licencia de uso, por ejemplo de [Pixabay Music](https://pixabay.com/music/) bajo la [Pixabay Content License](https://pixabay.com/service/license-summary/), y la guarda en `recursos/musica/` (git la ignora, porque esa licencia no permite redistribuir el archivo suelto).
- Anoten el título, el autor, el enlace y la licencia en `recursos/CREDITOS.md` y en `creditos` del guion. Si se usa `--musica` y ningún crédito empieza con «Música:», el script lo avisa.
- La música queda 19 dB por debajo de la voz mientras se habla (configurable entre 18 y 20) y sube a 8 dB por debajo solo en silencios de más de un segundo: el inicio y la tarjeta de créditos. Si la pista es más corta que el video, se repite con un fundido. El valor medido aparece en la consola y en `informe.json`.
- Tipografías y modelos: ver `recursos/CREDITOS.md`.

## Voz

- La tarea pide «Grabar entre 15 y 25 segundos de su propia voz como referencia». `preparar_voz.py` busca, entre los segmentos de Whisper, el tramo más claro de 15 a 25 s sin pausas largas que termina en punto, signo de interrogación o exclamación, y vuelve a transcribir ese recorte para que `referencia.txt` diga exactamente lo que suena.
- La grabación es un dato biométrico: el script solo la lee desde donde está, no imprime su transcripción y escribe en `voz/`, que git ignora.
- Clonen solo su propia voz.

## Tiempos medidos en este equipo

Ryzen 5 5600G (6 núcleos), 31 GB de RAM, sin GPU; guion de prueba de 2 escenas (`guion_prueba.json`).

| Paso | Tiempo |
|---|---|
| `preparar_voz.py` con una grabación de 131 s | 51 a 53 s |
| `--solo-visual`, 15.8 s de video (476 cuadros) | 12 a 35 s, según cuánto detalle tengan los visuales |
| Carga de Qwen3-TTS 0.6B (ya descargado) | 13 a 14 s |
| Voz: escenas de 4 a 6 s | 31 a 35 s por escena, unas 7 veces la duración del audio |
| Whisper: WER y tiempos por palabra de 2 escenas | 27 a 31 s |
| Cuadros y codificación de 15.6 s de video | 11 a 28 s |
| Reel completo, primera vez (2 escenas, 15.6 s) | 117 a 130 s |
| Reel completo con las escenas en caché | 31 s |

Para el reel final (unas 150 palabras y 55 s de voz) cabe esperar unos 7 minutos de voz, 3 de Whisper y 2 de video en la primera corrida; después, cambiar una frase solo vuelve a narrar esa escena. La sonoridad medida del video de prueba fue de −14.2 LUFS sin música y −14.4 LUFS con música, con picos de −1.5 dBTP.

## Pruebas

`uv run pytest -q` cubre, sin red ni modelos: el formato de tiempos del `.srt`, los bloques de subtítulos de hasta 4 palabras, la normalización de números antes del WER, la elección del tramo de 15 a 25 s, que el texto nunca se salga de su zona ni pise el visual, que la música quede al menos 18 dB bajo la voz, la resolución de `visual` (imagen o carpeta) y que audio y subtítulos compartan la misma línea de tiempo.

## Archivos

| Archivo | Qué hace |
|---|---|
| `hacer_reel.py` | Punto de entrada: guion → voz → subtítulos → mezcla → video |
| `preparar_voz.py` | Recorte de la referencia de voz |
| `generar_prueba.py` | Visuales de relleno para `guion_prueba.json` |
| `reelkit/config.py` | Rutas, colores de los tokens e hilos de CPU |
| `reelkit/script.py` | Lectura y validación del guion |
| `reelkit/narration.py` | Qwen3-TTS, caché por escena y reintento por WER |
| `reelkit/asr.py` | Whisper: transcripción, tiempos por palabra y WER |
| `reelkit/text.py` | Bloques de subtítulos, `.srt` y normalización de números |
| `reelkit/timeline.py` | Una sola línea de tiempo para audio, cuadros y subtítulos |
| `reelkit/audio.py` | Mezcla de la música bajo la voz |
| `reelkit/layout.py` | Zonas del cuadro, ajuste de textos, capas fijas y tarjeta de créditos |
| `reelkit/visuals.py` | Imagen fija con zoom o carpeta de cuadros |
| `reelkit/render.py` | Cuadros con Pillow y codificación con ffmpeg |
| `reelkit/media.py` | ffmpeg: decodificar, remuestrear, medir sonoridad y leer la resolución |
| `reelkit/fonts.py` | Descarga y verificación de las tipografías |
