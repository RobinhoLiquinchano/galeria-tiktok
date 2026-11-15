"""
Galería de videos estilo TikTok / Douyin
Kivy 2.3.x + ffpyplayer

Controles (igual que en la captura de Douyin):
  - Botón de play central cuando el video está en pausa
  - Fila de 7 botones circulares: candado, volumen, repetir, ajuste, +10 s, solo audio, siguiente
  - Barra de progreso fina con tiempo actual (izquierda) y duración (derecha)
  - Tira de miniaturas abajo, con borde blanco en el video actual
  - Gestos: toque = play/pausa, deslizar arriba = siguiente, abajo = anterior
"""
import os
import threading
import time

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Quad, Rectangle, RoundedRectangle, Triangle
from kivy.graphics.texture import Texture
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.video import Video
from kivy.uix.widget import Widget
from kivy.utils import platform

# Solo simulamos tamaño de móvil en el escritorio (en Android se ignora)
if platform != 'android':
    Window.size = (360, 640)

ACENTO = (1.0, 0.25, 0.40, 1)      # color de botón activo
EXTENSIONES = ('.mp4', '.mkv', '.mov')
MAX_MINIATURAS = 40                # cuántas miniaturas se generan (para no saturar el móvil)
TILE_W, TILE_H = dp(40), dp(52)    # tamaño de cada miniatura


def formatear_tiempo(segundos):
    segundos = max(0, int(segundos or 0))
    return f"{segundos // 60:02d}:{segundos % 60:02d}"


# ----------------------------------------------------------------------------
# Botón circular con icono dibujado en canvas (no usa emojis: Kivy no los pinta)
# ----------------------------------------------------------------------------
class BotonIcono(ButtonBehavior, Widget):
    icono = StringProperty('')
    texto = StringProperty('')
    activo = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(size_hint=(None, None), size=(dp(42), dp(42)), **kwargs)
        self._lbl = Label(size_hint=(None, None), font_size=sp(12), bold=True)
        self.add_widget(self._lbl)
        self.bind(pos=self._dibujar, size=self._dibujar, icono=self._dibujar,
                  texto=self._dibujar, activo=self._dibujar)
        self._dibujar()

    def _dibujar(self, *args):
        cx, cy = self.center
        s = self.width / 2
        color = ACENTO if self.activo else (1, 1, 1, 1)
        self.canvas.before.clear()
        with self.canvas.before:
            Color(0, 0, 0, 0.45)
            Ellipse(pos=self.pos, size=self.size)
            Color(*color)
            fn = getattr(self, '_ic_' + self.icono, None)
            if fn:
                fn(cx, cy, s)
        self._lbl.pos = self.pos
        self._lbl.size = self.size
        self._lbl.text = self.texto
        self._lbl.color = color

    # --- iconos ---
    def _ic_candado(self, cx, cy, s):
        Line(rounded_rectangle=(cx - .27 * s, cy - .02 * s, .54 * s, .58 * s, .27 * s), width=dp(1.6))
        RoundedRectangle(pos=(cx - .42 * s, cy - .50 * s), size=(.84 * s, .60 * s), radius=[dp(2)])

    def _altavoz(self, cx, cy, s):
        Rectangle(pos=(cx - .55 * s, cy - .17 * s), size=(.25 * s, .34 * s))
        Quad(points=[cx - .30 * s, cy + .17 * s, cx + .05 * s, cy + .50 * s,
                     cx + .05 * s, cy - .50 * s, cx - .30 * s, cy - .17 * s])

    def _ic_volumen(self, cx, cy, s):
        self._altavoz(cx, cy, s)
        Line(circle=(cx + .05 * s, cy, .30 * s, 40, 140), width=dp(1.4))
        Line(circle=(cx + .05 * s, cy, .55 * s, 40, 140), width=dp(1.4))

    def _ic_mute(self, cx, cy, s):
        self._altavoz(cx, cy, s)
        Line(points=[cx + .20 * s, cy + .25 * s, cx + .65 * s, cy - .25 * s], width=dp(1.5))
        Line(points=[cx + .20 * s, cy - .25 * s, cx + .65 * s, cy + .25 * s], width=dp(1.5))

    def _ic_repetir(self, cx, cy, s):
        Line(rounded_rectangle=(cx - .50 * s, cy - .28 * s, 1.0 * s, .56 * s, .22 * s), width=dp(1.5))
        Triangle(points=[cx + .10 * s, cy + .42 * s, cx + .10 * s, cy + .14 * s, cx + .36 * s, cy + .28 * s])
        Triangle(points=[cx - .10 * s, cy - .14 * s, cx - .10 * s, cy - .42 * s, cx - .36 * s, cy - .28 * s])

    def _ic_ajuste(self, cx, cy, s):
        Line(rounded_rectangle=(cx - .48 * s, cy - .48 * s, .96 * s, .96 * s, .14 * s), width=dp(1.5))
        Line(points=[cx - .20 * s, cy + .16 * s, cx - .36 * s, cy, cx - .20 * s, cy - .16 * s], width=dp(1.5))
        Line(points=[cx + .20 * s, cy + .16 * s, cx + .36 * s, cy, cx + .20 * s, cy - .16 * s], width=dp(1.5))

    def _ic_audio(self, cx, cy, s):
        Line(circle=(cx, cy - .02 * s, .46 * s, -90, 90), width=dp(1.6))
        Rectangle(pos=(cx - .58 * s, cy - .38 * s), size=(.24 * s, .42 * s))
        Rectangle(pos=(cx + .34 * s, cy - .38 * s), size=(.24 * s, .42 * s))

    def _ic_siguiente(self, cx, cy, s):
        Triangle(points=[cx - .30 * s, cy + .35 * s, cx - .30 * s, cy - .35 * s, cx + .25 * s, cy])
        Rectangle(pos=(cx + .30 * s, cy - .35 * s), size=(.10 * s, .70 * s))


# ----------------------------------------------------------------------------
# Triángulo de play grande (centro de la pantalla, visible solo en pausa)
# ----------------------------------------------------------------------------
class PlayCentral(Widget):
    def __init__(self, **kwargs):
        super().__init__(size_hint=(None, None), size=(dp(72), dp(72)),
                         pos_hint={'center_x': .5, 'center_y': .5}, **kwargs)
        self.bind(pos=self._dibujar, size=self._dibujar)

    def _dibujar(self, *args):
        cx, cy = self.center
        s = self.width / 2
        self.canvas.clear()
        with self.canvas:
            Color(1, 1, 1, .95)
            Triangle(points=[cx - .35 * s, cy + .55 * s, cx - .35 * s, cy - .55 * s, cx + .60 * s, cy])


# ----------------------------------------------------------------------------
# Barra de progreso fina (línea + punto al arrastrar)
# ----------------------------------------------------------------------------
class BarraProgreso(Widget):
    valor = NumericProperty(0)            # 0..1
    arrastrando = BooleanProperty(False)

    def __init__(self, al_mover=None, al_soltar=None, **kwargs):
        super().__init__(**kwargs)
        self.al_mover = al_mover
        self.al_soltar = al_soltar
        self.bind(pos=self._dibujar, size=self._dibujar, valor=self._dibujar,
                  arrastrando=self._dibujar)

    def _dibujar(self, *args):
        g = dp(5) if self.arrastrando else dp(3)
        y = self.center_y - g / 2
        self.canvas.clear()
        with self.canvas:
            Color(1, 1, 1, .30)
            RoundedRectangle(pos=(self.x, y), size=(self.width, g), radius=[g / 2])
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=(self.x, y), size=(max(self.width * self.valor, g), g), radius=[g / 2])
            if self.arrastrando:
                Ellipse(pos=(self.x + self.width * self.valor - dp(7), self.center_y - dp(7)),
                        size=(dp(14), dp(14)))

    def _fraccion(self, touch):
        if self.width <= 0:
            return 0
        return max(0., min(1., (touch.x - self.x) / self.width))

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.grab(self)
            self.arrastrando = True
            self.valor = self._fraccion(touch)
            if self.al_mover:
                self.al_mover(self.valor)
            return True
        return False

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            self.valor = self._fraccion(touch)
            if self.al_mover:
                self.al_mover(self.valor)
            return True
        return False

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self.arrastrando = False
            if self.al_soltar:
                self.al_soltar(self.valor)
            return True
        return False


# ----------------------------------------------------------------------------
# Miniatura de la tira inferior (borde blanco si es el video actual)
# ----------------------------------------------------------------------------
class Miniatura(ButtonBehavior, Widget):
    activa = BooleanProperty(False)

    def __init__(self, indice, **kwargs):
        super().__init__(size_hint=(None, None), size=(TILE_W, TILE_H), **kwargs)
        self.indice = indice
        self.textura = None
        self.bind(pos=self._dibujar, size=self._dibujar, activa=self._al_activar)
        self._dibujar()

    def _al_activar(self, *args):
        self.width = TILE_W + dp(14) if self.activa else TILE_W
        self._dibujar()

    def poner_textura(self, textura):
        self.textura = textura
        self._dibujar()

    def _dibujar(self, *args):
        self.canvas.clear()
        with self.canvas:
            if self.textura:
                Color(1, 1, 1, 1)
                RoundedRectangle(pos=self.pos, size=self.size, texture=self.textura, radius=[dp(6)])
            else:
                Color(.22, .22, .28, 1)
                RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(6)])
            if self.activa:
                Color(1, 1, 1, 1)
                Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(6)), width=dp(2))


def extraer_fotograma(ruta):
    """Devuelve (ancho, alto, bytes RGBA) del primer fotograma, o None."""
    from ffpyplayer.player import MediaPlayer
    player = MediaPlayer(ruta, ff_opts={'an': True, 'out_fmt': 'rgba', 'vf': 'scale=120:-2'})
    try:
        for _ in range(80):
            frame, val = player.get_frame()
            if val == 'eof':
                return None
            if frame is not None:
                imagen, _pts = frame
                w, h = imagen.get_size()
                return w, h, bytes(imagen.to_bytearray()[0])
            time.sleep(0.05)
    finally:
        player.close_player()
    return None


# ----------------------------------------------------------------------------
# Reproductor completo (un solo widget Video reutilizado para todos los archivos)
# ----------------------------------------------------------------------------
class Reproductor(FloatLayout):
    def __init__(self, rutas, **kwargs):
        super().__init__(**kwargs)
        self.rutas = rutas
        self.indice = 0
        self.bloqueado = False
        self.controles_visibles = True
        self.repetir = True
        self.silenciado = False
        self.solo_audio = False
        self._ev_ocultar = None

        # Fondo negro
        with self.canvas.before:
            Color(0, 0, 0, 1)
            self._fondo = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *a: setattr(self._fondo, 'pos', self.pos),
                  size=lambda *a: setattr(self._fondo, 'size', self.size))

        # 1) Video (fit_mode es una PROPIEDAD del widget, no va dentro de options)
        self.video = Video(state='stop', options={'eos': 'stop'}, fit_mode='contain',
                           size_hint=(1, 1))
        self.video.bind(position=self._al_posicion, duration=self._al_duracion, eos=self._al_eos)
        self.add_widget(self.video)

        # 2) Play central
        self.icono_play = PlayCentral(opacity=0)
        self.add_widget(self.icono_play)

        # 3) Título arriba a la izquierda
        self.lbl_titulo = Label(text='', size_hint=(1, None), height=dp(30),
                                pos_hint={'x': 0, 'top': .98}, halign='left', valign='middle',
                                font_size=sp(13), padding_x=dp(12))
        self.lbl_titulo.bind(size=lambda i, s: setattr(i, 'text_size', (s[0] - dp(24), s[1])))
        self.add_widget(self.lbl_titulo)

        # 4) Panel inferior: botones, barra, tiempos, miniaturas
        self.panel = BoxLayout(orientation='vertical', size_hint=(1, None),
                               pos_hint={'x': 0, 'y': 0},
                               padding=[dp(14), dp(6), dp(14), dp(10)], spacing=dp(2))
        self.panel.bind(minimum_height=self.panel.setter('height'))

        # 4a) Fila de botones circulares
        self.btn_candado = BotonIcono(icono='candado')
        self.btn_volumen = BotonIcono(icono='volumen')
        self.btn_repetir = BotonIcono(icono='repetir', activo=True)
        self.btn_ajuste = BotonIcono(icono='ajuste')
        self.btn_salto = BotonIcono(texto='+10')
        self.btn_audio = BotonIcono(icono='audio')
        self.btn_siguiente = BotonIcono(icono='siguiente')
        botones = [self.btn_candado, self.btn_volumen, self.btn_repetir, self.btn_ajuste,
                   self.btn_salto, self.btn_audio, self.btn_siguiente]

        self.btn_candado.bind(on_release=lambda *a: self.alternar_bloqueo())
        self.btn_volumen.bind(on_release=lambda *a: self.alternar_silencio())
        self.btn_repetir.bind(on_release=lambda *a: self.alternar_repetir())
        self.btn_ajuste.bind(on_release=lambda *a: self.alternar_ajuste())
        self.btn_salto.bind(on_release=lambda *a: self.saltar(10))
        self.btn_audio.bind(on_release=lambda *a: self.alternar_solo_audio())
        self.btn_siguiente.bind(on_release=lambda *a: self.cargar(self.indice + 1))

        fila_botones = BoxLayout(orientation='horizontal', size_hint=(1, None), height=dp(44))
        for i, b in enumerate(botones):
            fila_botones.add_widget(b)
            if i < len(botones) - 1:
                fila_botones.add_widget(Widget())      # espaciador elástico
        self.panel.add_widget(fila_botones)

        # 4b) Barra de progreso
        self.barra = BarraProgreso(al_mover=self._barra_mueve, al_soltar=self._barra_suelta,
                                   size_hint=(1, None), height=dp(26))
        self.panel.add_widget(self.barra)

        # 4c) Tiempos (izquierda: actual, derecha: total)
        self.fila_tiempos = BoxLayout(orientation='horizontal', size_hint=(1, None), height=dp(18))
        self.lbl_actual = self._etiqueta_tiempo('left')
        self.lbl_total = self._etiqueta_tiempo('right')
        self.fila_tiempos.add_widget(self.lbl_actual)
        self.fila_tiempos.add_widget(self.lbl_total)
        self.panel.add_widget(self.fila_tiempos)

        # 4d) Tira de miniaturas
        self.scroll = ScrollView(size_hint=(1, None), height=dp(60), do_scroll_y=False, bar_width=0)
        self.tira = BoxLayout(orientation='horizontal', size_hint=(None, 1), spacing=dp(6))
        self.tira.bind(minimum_width=self.tira.setter('width'))
        self.miniaturas = []
        for i in range(len(self.rutas)):
            m = Miniatura(i)
            m.bind(on_release=lambda inst: self.cargar(inst.indice))
            self.miniaturas.append(m)
            self.tira.add_widget(m)
        self.scroll.add_widget(self.tira)
        self.panel.add_widget(self.scroll)

        self.add_widget(self.panel)

        # Todo lo que se oculta al bloquear (el candado siempre queda)
        self._normales = [self.btn_volumen, self.btn_repetir, self.btn_ajuste, self.btn_salto,
                          self.btn_audio, self.btn_siguiente, self.barra, self.fila_tiempos,
                          self.scroll, self.lbl_titulo]

        Clock.schedule_once(lambda dt: self.cargar(0), 0)
        threading.Thread(target=self._hilo_miniaturas, daemon=True).start()

    def _etiqueta_tiempo(self, alineacion):
        lbl = Label(text='00:00', font_size=sp(11), color=(1, 1, 1, .85), halign=alineacion,
                    valign='middle')
        lbl.bind(size=lambda i, s: setattr(i, 'text_size', s))
        return lbl

    # ---------------------------------------------------------------- carga
    def cargar(self, indice):
        if not self.rutas:
            return
        self.indice = indice % len(self.rutas)
        self.video.state = 'stop'
        self.video.source = self.rutas[self.indice]
        self.video.state = 'play'
        self.video.volume = 0 if self.silenciado else 1

        self.barra.valor = 0
        self.lbl_actual.text = '00:00'
        self.lbl_total.text = '00:00'
        self.lbl_titulo.text = f"{self.indice + 1}/{len(self.rutas)}   {os.path.basename(self.rutas[self.indice])}"
        self.icono_play.opacity = 0

        for i, m in enumerate(self.miniaturas):
            m.activa = (i == self.indice)
        Clock.schedule_once(self._centrar_miniatura, 0.1)

        if not self.solo_audio:
            self.video.opacity = 0.2
            Animation(opacity=1, d=0.25).start(self.video)
        self.mostrar_controles()

    def _centrar_miniatura(self, dt):
        if not self.miniaturas:
            return
        m = self.miniaturas[self.indice]
        visible, total = self.scroll.width, self.tira.width
        if total <= visible:
            return
        centro = (m.x - self.tira.x) + m.width / 2
        objetivo = max(0., min(1., (centro - visible / 2) / (total - visible)))
        Animation(scroll_x=objetivo, d=0.25).start(self.scroll)

    # ------------------------------------------------------------ miniaturas
    def _hilo_miniaturas(self):
        for i, ruta in enumerate(self.rutas[:MAX_MINIATURAS]):
            try:
                datos = extraer_fotograma(ruta)
            except Exception as e:
                print('Miniatura fallida:', ruta, e)
                datos = None
            if datos:
                Clock.schedule_once(lambda dt, i=i, d=datos: self._poner_miniatura(i, d))

    def _poner_miniatura(self, i, datos):
        w, h, buf = datos
        tex = Texture.create(size=(w, h), colorfmt='rgba')
        tex.blit_buffer(buf, colorfmt='rgba', bufferfmt='ubyte')
        tex.flip_vertical()
        # recorte centrado para llenar el recuadro sin deformar
        rel = TILE_W / TILE_H
        if w / h > rel:
            nw = int(h * rel)
            tex = tex.get_region((w - nw) // 2, 0, nw, h)
        else:
            nh = int(w / rel)
            tex = tex.get_region(0, (h - nh) // 2, w, nh)
        self.miniaturas[i].poner_textura(tex)

    # ------------------------------------------------ eventos del video
    def _al_posicion(self, inst, pos):
        dur = self.video.duration
        if dur and dur > 0 and not self.barra.arrastrando:
            self.barra.valor = max(0., min(1., pos / dur))
            self.lbl_actual.text = formatear_tiempo(pos)

    def _al_duracion(self, inst, dur):
        if dur and dur > 0:
            self.lbl_total.text = formatear_tiempo(dur)

    def _al_eos(self, inst, eos):
        if not eos:
            return
        if self.repetir:
            Clock.schedule_once(self._reiniciar, 0)
        else:
            Clock.schedule_once(lambda dt: self.cargar(self.indice + 1), 0)

    def _reiniciar(self, dt):
        self.video.state = 'stop'
        self.video.state = 'play'

    # ------------------------------------------------------- barra de progreso
    def _barra_mueve(self, valor):
        dur = self.video.duration
        if dur and dur > 0:
            self.lbl_actual.text = formatear_tiempo(valor * dur)
        self.mostrar_controles()

    def _barra_suelta(self, valor):
        if self.video.duration and self.video.duration > 0:
            self.video.seek(valor)
        self.mostrar_controles()

    # ------------------------------------------------------------- acciones
    def alternar_pausa(self):
        self.video.state = 'pause' if self.video.state == 'play' else 'play'
        self.icono_play.opacity = 1 if self.video.state == 'pause' else 0
        self.mostrar_controles()

    def alternar_bloqueo(self):
        self.bloqueado = not self.bloqueado
        self.btn_candado.activo = self.bloqueado
        self.mostrar_controles()

    def alternar_silencio(self):
        self.silenciado = not self.silenciado
        self.video.volume = 0 if self.silenciado else 1
        self.btn_volumen.icono = 'mute' if self.silenciado else 'volumen'
        self.btn_volumen.activo = self.silenciado
        self.mostrar_controles()

    def alternar_repetir(self):
        self.repetir = not self.repetir
        self.btn_repetir.activo = self.repetir      # activo = repetir; apagado = pasar al siguiente
        self.mostrar_controles()

    def alternar_ajuste(self):
        cubrir = self.video.fit_mode != 'cover'
        self.video.fit_mode = 'cover' if cubrir else 'contain'
        self.btn_ajuste.activo = cubrir
        self.mostrar_controles()

    def saltar(self, segundos):
        dur = self.video.duration
        if dur and dur > 0:
            self.video.seek(max(0., min(1., (self.video.position + segundos) / dur)))
        self.mostrar_controles()

    def alternar_solo_audio(self):
        self.solo_audio = not self.solo_audio
        self.video.opacity = 0 if self.solo_audio else 1
        self.btn_audio.activo = self.solo_audio
        self.mostrar_controles()

    # ------------------------------------------------- visibilidad de controles
    def mostrar_controles(self):
        self.controles_visibles = True
        self._aplicar_visibilidad()
        if self._ev_ocultar:
            self._ev_ocultar.cancel()
        self._ev_ocultar = Clock.schedule_once(self._ocultar, 3.5)

    def _ocultar(self, dt):
        # En pausa se quedan visibles (como en Douyin), salvo que esté bloqueado
        if self.barra.arrastrando:
            return
        if self.video.state == 'play' or self.bloqueado:
            self.controles_visibles = False
            self._aplicar_visibilidad()

    def _aplicar_visibilidad(self):
        vis = self.controles_visibles
        normales = vis and not self.bloqueado
        for w in self._normales:
            w.opacity = 1 if normales else 0
            w.disabled = not normales
        self.btn_candado.opacity = 1 if vis else 0
        self.btn_candado.disabled = not vis

    # ----------------------------------------------------------------- gestos
    def on_touch_down(self, touch):
        # Si los controles están visibles, ellos tienen prioridad
        if self.controles_visibles and super().on_touch_down(touch):
            return True
        if not self.collide_point(*touch.pos):
            return False
        touch.grab(self)
        touch.ud['inicio'] = (touch.x, touch.y)
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            x0, y0 = touch.ud.get('inicio', (touch.x, touch.y))
            dx, dy = touch.x - x0, touch.y - y0
            if abs(dy) > dp(60) and abs(dy) > 1.5 * abs(dx):
                if not self.bloqueado:                      # arriba = siguiente, abajo = anterior
                    self.cargar(self.indice + (1 if dy > 0 else -1))
            elif abs(dx) < dp(15) and abs(dy) < dp(15):
                if self.bloqueado:
                    self.mostrar_controles()                # solo reaparece el candado
                else:
                    self.alternar_pausa()
            return True
        return super().on_touch_up(touch)


# ----------------------------------------------------------------------------
# App
# ----------------------------------------------------------------------------
class GaleriaTikTokApp(App):
    def build(self):
        Window.clearcolor = (0, 0, 0, 1)
        self.raiz = FloatLayout()
        self.reproductor = None

        if platform == 'android':
            from android.permissions import request_permissions
            request_permissions(
                ['android.permission.READ_EXTERNAL_STORAGE',
                 'android.permission.READ_MEDIA_VIDEO'],
                lambda permisos, resultados: Clock.schedule_once(lambda dt: self.cargar_biblioteca(), 0)
            )
        else:
            self.cargar_biblioteca()
        return self.raiz

    def ruta_carpeta(self):
        if platform == 'android':
            from android.storage import primary_external_storage_path
            return os.path.join(primary_external_storage_path(), 'DCIM', 'Camera')
        return 'videos'

    def cargar_biblioteca(self):
        self.raiz.clear_widgets()
        carpeta = self.ruta_carpeta()
        rutas = []
        if os.path.exists(carpeta):
            rutas = sorted(os.path.join(carpeta, f) for f in os.listdir(carpeta)
                           if f.lower().endswith(EXTENSIONES))

        if not rutas:
            self.raiz.add_widget(Label(
                text=f"No se encontraron videos en:\n{carpeta}\n\nAñade archivos .mp4 a la carpeta.",
                halign='center', font_size=sp(16)))
            return

        self.reproductor = Reproductor(rutas)
        self.raiz.add_widget(self.reproductor)

    def on_pause(self):
        if self.reproductor and self.reproductor.video.state == 'play':
            self.reproductor.alternar_pausa()
        return True

    def on_resume(self):
        pass


if __name__ == '__main__':
    GaleriaTikTokApp().run()
