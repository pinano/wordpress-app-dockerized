# 🤖 Wordpress Telegram Bot

Este directorio contiene el código fuente completo del Bot de Telegram en Python, integrado dentro de la arquitectura Docker de este proyecto.

El propósito principal de este bot es permitir al usuario autorizado publicar entradas en el blog de WordPress cómodamente desde cualquier parte, manejando automáticamente la subida, compresión, y conversión de archivos multimedia de todo tipo (fotos, notas de voz, vídeos) utilizando **FFmpeg** y **WP-CLI**.

---

## 🏗️ Arquitectura y Flujo

El bot está programado de forma asíncrona usando la librería moderna [python-telegram-bot](https://python-telegram-bot.org/) (versión 21+). Utiliza **Long-polling** (conexión constante) para no depender de puertos expuestos ni URLs públicas para recibir Webhooks.

### ¿Cómo se comunica con WordPress?
El bot **no** utiliza plugins REST de WordPress, **no** ataca base de datos de manera directa y **no** necesita usuarios administradores HTTP de WP.

En su lugar, usa un puente inter-contenedor (vía `wp_cli.py`). Cuando el bot necesita interactuar con la web (crear un borrador, asignarle una imagen), lanza internamente un subproceso que hace:

```bash
docker exec --user www-data wordpress-app wp post ...
```
Esto garantiza la absoluta seguridad de tu blog y una integración instantánea. Además, todos los archivos descargados desde los servidores de Telegram se guardan en el volumen compartido protegido `/var/bot-media/`.

---

## 🛠️ Comandos Disponibles

A continuación se detalla toda la funcionalidad exhaustiva:

### 1. `/start` y `/ayuda`
Son comandos de información pasiva. Al invocarlos, el bot responderá con un bloque de texto que explica brevemente las instrucciones de publicación.

### 2. `/blog` (El publicador interactivo)
Este comando desencadena la maquinaria principal. Inicia un *Conversation Handler* en el que el bot tomará de tu mano durante sencillos pasos.

**Paso 1: El Título (Obligatorio)**
El bot te pedirá el título. Cualquier texto que envíes será usado para generar un post vacío en estado «**Borrador**» (`draft`) en WordPress.

**Paso 2: El Texto (Opcional)**
Te pedirá el contenido de la entrada. Puedes escribir un párrafo, varios o presionar el botón «**SALTAR**».

**Paso 3: La Ubicación (Opcional)**
Te pedirá enviar una chincheta GPS de tu móvil. Si lo haces, fabricará automáticamente un Enlace Inteligente a Google Maps anidado en tu Texto. Si no la necesitas, pulsa «**SALTAR**».

**Paso Especial: Modo Galería**
Si iniciaste el comando como `/blog gallery`, el bot entrará en modo acumulación. En lugar de publicar al recibir el primer medio, te permitirá enviar hasta **15 fotos** (una a una o en álbum) y solo publicará cuando pulses el botón **"✅ FINALIZAR Y PUBLICAR"**. Se asignará el formato `post-format-gallery` a la entrada.

**Paso 4: El Archivo Adjunto Multimedia (Obligatorio)**
Llegados aquí debes adjuntar el material principal de la entrada:

*   📷 **Foto comprimida**: El bot usará WP-CLI para importarla como *Featured Image* (Imagen destacada) y publicar el post.
*   🖼️ **Foto/Documento como Archivo**: Si adjuntas desde Telegram algo como "Enviar Extensión / Archivo", lo tratará y publicará como documento.
*   🎥 **Vídeo (MP4 o MOV)**: Si envías un vídeo grabado con el móvil, el bot iniciará una conversión.
    *   Extraerá un fotograma de alta calidad del primer segundo de vídeo para usarlo de **Carátula**.
    *   Verificará el formato y, si no es amigable para web, lo re-empaquetará.
    *   Insertará un _shortcode_ de vídeo en el cuerpo de tu entrada para que cualquier navegador lo reproduzca elegantemente.
*   🎤 **Nota de voz o Música**: FFmpeg interceptará el formato nativo `.ogg` o `.m4a` del micrófono de Telegram y lo convertirá a un `.mp3` VBR antes de inyectarlo en WP con etiquetas HTML5 de `<audio>`.

Una vez recibido **uno** de estos medios, se limpiarán cachés, el post pasará a estado publicado (`publish`) y recibirás un resumen final enriquecido en Telegram listando URLs, IDs y tu carátula.

### 3. `/fecha`
Permite modificar la fecha de publicación del último post creado. El bot leerá automáticamente el desfase horario de tu WordPress (`gmt_offset`) para que la fecha coincida exactamente con lo que ves en el panel. Al cambiar la fecha del post, también se actualiza la fecha de todos sus medios asociados (fotos de la galería, etc.).

### 4. `/borrar` (El botón del Pánico)
Si detectas alguna errata inaceptable o escogiste el vídeo equivocado un milisegundo después de terminar con el comando `/blog`, solo escribe `/borrar`.

El bot tiene una memoria volátil inteligente (`user_data["last_published"]`) donde retiene la identidad matemática del **último** contenido que creó. Usando `/borrar`, purgará sin piedad:
1. El archivo o archivos principales (El vídeo o la lista de fotos de la galería).
2. El archivo de Carátula (La miniatura del vídeo).
3. El borrador entero en forma de Entrada de WordPress.

*(Si ejecutas dos veces `/deshacer`, fallará con gusto, ya que la orden se auto-consume evitando que borres tu blog accidentalmente).*

---

## 🔒 Seguridad

El principal pilar de este script es el **Muro de Identidad**:

Al principio del proceso, la función privada `_allowed(user_id)` verifica si el identificador matemático inmutable de Telegram del usuario que habla con el bot figura explícitamente dentro de la lista de tu variable de entorno en texto plano `BOT_ALLOWED_USERS` (`.env`).

Si otra persona descubre el Nombre de Usuario `@tu_bot_secreto` de tu bot y le lanza un `/start` o `/blog`, el servidor le cortará en seco la comunicación de inmediato. **Solo tú tienes el poder de publicarle contenido a la máquina.**

---

## 💻 Desarrollo Local

Para añadir funciones extra en este código en un futuro, sigue estos pasos:

1. Modifica la lógica en los archivos `.py`.
2. Lanza el comando rápido: `docker compose restart bot`
3. Al carecer de bases de datos temporales, los cambios se cargarán de inmediato (¡y el bot estará en funcionamiento pasados ​​0.5 segundos!).
4. No necesitas redes de traefik, SSLs ni certificados proxy en local para que esto funcione porque ataca de abajo a arriba usando conexiones cURL directas a la API general de Telegram.
