from __future__ import annotations
import sys, time
from pathlib import Path
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QFrame,QComboBox,QGridLayout,QSizePolicy,QPushButton,QFileDialog,QScrollArea,QCheckBox
from .bridge import detect_game, live_editor_status, clear_live_session_markers, elevation_mismatch
from . import elevation
from .engine_controller import start as start_engine, stop as stop_engine, health as engine_health, ensure_running
from .settings_store import load as load_settings, save as save_settings
from .overlay_host import ensure_running as ensure_overlay_host, stop as stop_overlay_host
from .ui_theme import desktop_stylesheet
from .live_editor_integration import discover_live_editor_root, discover_live_editor_data_root, ensure_autorun_installed, all_live_editor_data_roots
from fc27_academy.transaction_store import lifecycle as runtime_lifecycle, detach as detach_runtime

class Launcher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings=load_settings()
        self._game_was_running=False
        self._syncing_controls=False
        self.setWindowTitle('FC27 Academy Engine')
        # Keep a sensible minimum, but make the content scroll-safe for users
        # running Windows display scaling or smaller logical resolutions.
        self.setMinimumSize(860,650)

        shell=QWidget(); self.setCentralWidget(shell)
        shell_layout=QVBoxLayout(shell); shell_layout.setContentsMargins(0,0,0,0); shell_layout.setSpacing(0)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        w=QWidget(); scroll.setWidget(w); shell_layout.addWidget(scroll)
        self._launcher_scroll=scroll
        l=QVBoxLayout(w); l.setContentsMargins(30,28,30,28); l.setSpacing(18)

        hero=QFrame(); hero.setObjectName('heroCard')
        hl=QVBoxLayout(hero); hl.setContentsMargins(22,18,22,18); hl.setSpacing(3)
        b=QLabel('FC27 ACADEMY ENGINE'); b.setObjectName('brand'); hl.addWidget(b)
        s=QLabel('IN-GAME COMPANION  •  LAUNCHER & ENGINE HOST'); s.setObjectName('brandAccent'); hl.addWidget(s)
        desc=QLabel('Keep this launcher open while playing. Academy Engine runs automatically and its interface is rendered by a separate overlay process above FC27.')
        desc.setWordWrap(True); desc.setObjectName('muted'); hl.addSpacing(5); hl.addWidget(desc)
        l.addWidget(hero)

        card=QFrame(); card.setObjectName('card')
        cl=QGridLayout(card); cl.setContentsMargins(20,18,20,18); cl.setHorizontalSpacing(18); cl.setVerticalSpacing(12)
        title=QLabel('Connection status'); title.setObjectName('sectionTitle'); cl.addWidget(title,0,0,1,2)
        self.game=self._status_label(); self.engine=self._status_label(); self.overlay=self._status_label(); self.career=self._status_label()
        labels=[('FC27',self.game),('Engine host',self.engine),('External overlay',self.overlay),('Career Mode',self.career)]
        for row,(name,val) in enumerate(labels,1):
            key=QLabel(name); key.setObjectName('muted'); key.setMinimumWidth(130)
            cl.setRowMinimumHeight(row,34)
            cl.addWidget(key,row,0); cl.addWidget(val,row,1)
        cl.setColumnMinimumWidth(0,140)
        cl.setColumnStretch(1,1)
        self.overlay_detail=QLabel(''); self.overlay_detail.setObjectName('muted'); self.overlay_detail.setWordWrap(True); cl.addWidget(self.overlay_detail,5,1)
        self._next_le_try=0.0; self._next_logs_check=0.0; self._logs_found=True
        self.integration=QLabel('Live Editor bridge: preparing…'); self.integration.setObjectName('muted'); self.integration.setWordWrap(True); cl.addWidget(self.integration,6,0,1,2)
        # v1.0.1: FC27 running as administrator while Academy Engine is not.
        self.elev_row=QWidget(); er=QHBoxLayout(self.elev_row); er.setContentsMargins(0,0,0,0); er.setSpacing(14)
        self.elev_btn=QPushButton('Restart Academy Engine as administrator'); self.elev_btn.clicked.connect(self.restart_elevated)
        self.elev_auto=QCheckBox('Always do this when FC27 runs as administrator')
        self.elev_auto.setChecked(bool(self.settings.get('auto_elevate',False))); self.elev_auto.toggled.connect(self._set_auto_elevate)
        er.addWidget(self.elev_btn); er.addWidget(self.elev_auto); er.addStretch(1)
        self.elev_row.setVisible(False); cl.addWidget(self.elev_row,7,0,1,2)
        self._elevate_attempted=False; self._elev_note=''; self._restarting=False
        l.addWidget(card)

        prefs=QFrame(); prefs.setObjectName('card')
        pl=QVBoxLayout(prefs); pl.setContentsMargins(20,16,20,18); pl.setSpacing(10)
        pt=QLabel('Overlay preferences'); pt.setObjectName('sectionTitle'); pl.addWidget(pt)
        # v1.24.14: hotkey, theme and controller options share one row.
        prow=QHBoxLayout(); prow.setSpacing(10)
        prow.addWidget(QLabel('Hotkey'))
        self.hot=QComboBox(); self.hot.setMinimumWidth(96); self.hot.setMinimumHeight(38); self.hot.addItems([f'F{i}' for i in range(1,13)])
        self.hot.setCurrentText(self.settings.get('overlay_hotkey','F8')); self.hot.currentTextChanged.connect(self.save_hotkey); prow.addWidget(self.hot)
        prow.addSpacing(14); prow.addWidget(QLabel('Theme'))
        self.theme=QComboBox(); self.theme.setMinimumWidth(120); self.theme.setMinimumHeight(38); self.theme.addItem('Dark','dark'); self.theme.addItem('Light','light')
        idx=self.theme.findData(self.settings.get('ui_theme','dark')); self.theme.setCurrentIndex(max(0,idx))
        self.theme.currentIndexChanged.connect(lambda _:self.save_theme(self.theme.currentData())); prow.addWidget(self.theme)
        # Controller support (XInput): enable/disable and open combo.
        prow.addSpacing(14)
        self.ctl_on=QCheckBox('Controller'); self.ctl_on.setChecked(bool(self.settings.get('controller_enabled',True)))
        self.ctl_on.setToolTip('Xbox-style (XInput) controller support for the overlay')
        self.ctl_on.toggled.connect(self.save_controller); prow.addWidget(self.ctl_on)
        prow.addSpacing(6); prow.addWidget(QLabel('Open combo'))
        from .controller import PRESETS, normalize_combo
        self.ctl_combo=QComboBox(); self.ctl_combo.setEditable(True); self.ctl_combo.setMinimumWidth(200); self.ctl_combo.setMinimumHeight(38)
        self.ctl_combo.addItems(list(PRESETS)); self.ctl_combo.setCurrentText(normalize_combo(self.settings.get('controller_combo','L3+R3')) or 'L3+R3')
        self.ctl_combo.setToolTip('Two to four of: A B X Y LB RB LT RT VIEW MENU L3 R3 UP DOWN LEFT RIGHT, joined with +')
        self.ctl_combo.lineEdit().editingFinished.connect(self.save_controller); self.ctl_combo.activated.connect(lambda _:self.save_controller())
        prow.addWidget(self.ctl_combo); prow.addStretch(); pl.addLayout(prow)
        self.ctl_hint=QLabel(''); self.ctl_hint.setObjectName('muted'); self.ctl_hint.setWordWrap(True); pl.addWidget(self.ctl_hint)
        self._update_ctl_hint()   # v1.24.30: shown from the start, not only after a change
        ph=QLabel('Press the configured hotkey while FC27 is focused to show or hide Academy Engine. The overlay runs outside FC27 and only receives complete, validated career generations.')
        ph.setWordWrap(True); ph.setObjectName('muted'); pl.addWidget(ph)
        l.addWidget(prefs)

        # v1.24.31: faces for generated players from the user's own regen-face library
        # (v1.24.37: hidden for now; see fc27_academy.faces.faces_visible).
        from fc27_academy.faces import faces_visible
        if faces_visible(): self._build_face_card(l)


        footer=QLabel('The engine starts with this launcher and shuts down when the launcher closes.')
        footer.setAlignment(Qt.AlignCenter); footer.setObjectName('muted'); l.addWidget(footer); l.addStretch()

        self.timer=QTimer(self); self.timer.timeout.connect(self.poll); self.timer.start(750)
        self.apply_theme(); self._prepare_live_editor_bridge(); start_engine(); self.poll()

    def _status_label(self):
        q=QLabel('Checking…')
        q.setObjectName('statusChipLabel')
        q.setProperty('kind','muted')
        q.setMinimumHeight(30)
        q.setMinimumWidth(360)
        q.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        return q

    def _set_status(self,q,text,kind):
        q.setText(text); q.setProperty('kind',kind); q.style().unpolish(q); q.style().polish(q)

    def _prepare_live_editor_bridge(self):
        try:
            binary=discover_live_editor_root(self.settings.get('live_editor_root') or None)
            data=discover_live_editor_data_root(self.settings.get('live_editor_data_root') or None,binary_root=binary)
            result=ensure_autorun_installed(data,all_live_editor_data_roots(self.settings.get('live_editor_data_root') or None,binary_root=binary))
            if result.get('ok'):
                where=f" • {data}" if data else ''
                note=''
                if result.get('updated'):
                    from .bridge import live_editor_process
                    note=' • autorun updated'+(' — restart Live Editor to load it' if live_editor_process() else '')
                self.integration.setText('Live Editor bridge: ready'+where+note)
                if binary:self.settings['live_editor_root']=str(binary)
                if data:self.settings['live_editor_data_root']=str(data)
                save_settings(self.settings)
            else:
                # v1.0.2: no folder pickers. Live Editor is found automatically once it has run.
                self.integration.setText('Live Editor bridge: not set up yet. Start FC27 through Live Editor at least once '
                                         'so Academy Engine can find Live Editor and connect to it. This is detected automatically.')
        except Exception as exc:
            self.integration.setText('Live Editor bridge: setup error — '+str(exc))

    def _build_face_card(self,l):
        fcard=QFrame(); fcard.setObjectName('card')
        fl=QGridLayout(fcard); fl.setContentsMargins(20,16,20,18); fl.setHorizontalSpacing(12); fl.setVerticalSpacing(9)
        ft=QLabel('Player faces'); ft.setObjectName('sectionTitle'); fl.addWidget(ft,0,0,1,3)
        fd=QLabel('Choose the folder that holds your regen faces: one folder per region for men, and a WF folder with region folders for women. Faces are matched to each player\'s nationality and gender, saved with the career and shown in Player Details. Your images are only read, never copied or changed.')
        fd.setWordWrap(True); fd.setObjectName('muted'); fl.addWidget(fd,1,0,1,3)
        self.face_on=QCheckBox('Give players faces'); self.face_on.setChecked(bool(self.settings.get('face_enabled',False)))
        self.face_on.toggled.connect(self.save_faces); fl.addWidget(self.face_on,2,0,1,2,Qt.AlignLeft)
        self.face_lib=QLabel(self.settings.get('face_library_path') or 'Not selected'); self.face_lib.setObjectName('muted'); self.face_lib.setWordWrap(True)
        fb=QPushButton('Browse face folder…'); fb.clicked.connect(self.choose_face_library)
        fl.addWidget(QLabel('Face folder'),3,0); fl.addWidget(self.face_lib,3,1); fl.addWidget(fb,3,2)
        self.face_info=QLabel(''); self.face_info.setObjectName('muted'); self.face_info.setWordWrap(True); fl.addWidget(self.face_info,4,1,1,2)
        self.face_game=QCheckBox('Also write faces into FC27 (experimental — Live Editor 27.1.x does not show them in-game yet)')
        self.face_game.setChecked(bool(self.settings.get('face_write_ingame',False))); self.face_game.toggled.connect(self.save_faces)
        fl.addWidget(self.face_game,5,0,1,3,Qt.AlignLeft)
        fl.setColumnStretch(1,1); l.addWidget(fcard)
        self._update_face_info()

    def choose_face_library(self):
        start=self.settings.get('face_library_path') or str(Path.home())
        chosen=QFileDialog.getExistingDirectory(self,'Select your regen face folder',start)
        if not chosen:return
        self.face_info.setText('Scanning face folder…'); QApplication.processEvents()
        self.settings['face_library_path']=chosen; save_settings(self.settings); self.face_lib.setText(chosen)
        self._update_face_info()

    def save_faces(self,*_):
        if self._syncing_controls:return
        self.settings['face_enabled']=self.face_on.isChecked(); self.settings['face_write_ingame']=self.face_game.isChecked()
        save_settings(self.settings); self._update_face_info()

    def _update_face_info(self):
        lib=str(self.settings.get('face_library_path') or '').strip()
        if not lib: self.face_info.setText('No face folder chosen yet.'); return
        try:
            from fc27_academy.faces import load_library, library_summary
            if not Path(lib).is_dir(): self.face_info.setText('Folder not found — choose it again.'); return
            idx=load_library(lib)
            if not idx.get('count'): self.face_info.setText('No face images found (PNG, JPG, WEBP, BMP or DDS inside region folders).'); return
            extra='' if self.face_on.isChecked() else '  •  Turn on “Give players faces” to use it.'
            if not idx.get('F'): extra+='  •  No WF folder found, so women keep no face.'
            self.face_info.setText(library_summary(idx).capitalize()+'. New faces appear after the next checkpoint.'+extra)
        except Exception as exc:
            self.face_info.setText('Could not read the face folder: '+str(exc))

    def apply_theme(self):
        light=str(self.settings.get('ui_theme','dark')).lower()=='light'
        arrow=(Path(__file__).resolve().parents[1]/'assets'/('chevron_down_dark.svg' if light else 'chevron_down_light.svg')).as_posix()
        extra=f"""
QComboBox{{min-height:30px;padding:7px 38px 7px 12px;font-weight:650;border-radius:9px}}
QComboBox::drop-down{{subcontrol-origin:padding;subcontrol-position:top right;width:34px;border:0;border-left:1px solid {'#bdceda' if light else '#203b4f'}}}
QComboBox::down-arrow{{image:url("{arrow}");width:12px;height:8px}}
QComboBox QAbstractItemView{{padding:6px;border:1px solid {'#a9becd' if light else '#29475b'};selection-background-color:{'#d7edf8' if light else '#173c56'};outline:0}}
QLabel#statusChipLabel{{padding:7px 12px;font-size:12px}}
"""
        self.setStyleSheet(desktop_stylesheet(self.settings.get('ui_theme','dark')) + extra)

    def save_hotkey(self,v):
        if self._syncing_controls:return
        self.settings['overlay_hotkey']=v; save_settings(self.settings)

    def save_controller(self,*_):
        if self._syncing_controls:return
        from .controller import normalize_combo
        combo=normalize_combo(self.ctl_combo.currentText())
        if not combo:
            self.ctl_hint.setText('Combo not recognised — use 2 to 4 buttons such as L3+R3 or VIEW+RB. Previous combo kept.')
            self.ctl_combo.setCurrentText(normalize_combo(self.settings.get('controller_combo','L3+R3')) or 'L3+R3'); return
        self.ctl_combo.setCurrentText(combo)
        self.settings['controller_enabled']=self.ctl_on.isChecked(); self.settings['controller_combo']=combo; save_settings(self.settings)
        self._update_ctl_hint()

    def _update_ctl_hint(self):
        from .controller import normalize_combo, controller_help_text
        combo=normalize_combo(self.ctl_combo.currentText()) or normalize_combo(self.settings.get('controller_combo','L3+R3')) or 'L3+R3'
        self.ctl_hint.setText(controller_help_text(combo,self.ctl_on.isChecked()))

    def save_theme(self,v):
        if self._syncing_controls:return
        self.settings['ui_theme']=v; save_settings(self.settings); self.apply_theme()

    def poll(self):
        latest=load_settings()
        if any(latest.get(k)!=self.settings.get(k) for k in ('overlay_hotkey','ui_theme','controller_enabled','controller_combo','face_enabled','face_write_ingame','face_library_path')):
            old_theme=self.settings.get('ui_theme'); self.settings=latest; self._syncing_controls=True
            try:
                self.hot.setCurrentText(self.settings.get('overlay_hotkey','F8'))
                idx=self.theme.findData(self.settings.get('ui_theme','dark')); self.theme.setCurrentIndex(max(0,idx))
                self.ctl_on.setChecked(bool(self.settings.get('controller_enabled',True)))
                self.ctl_combo.setCurrentText(str(self.settings.get('controller_combo','L3+R3')))
                self._update_ctl_hint()
                if hasattr(self,'face_on'):
                    self.face_on.setChecked(bool(self.settings.get('face_enabled',False))); self.face_game.setChecked(bool(self.settings.get('face_write_ingame',False)))
                    self.face_lib.setText(self.settings.get('face_library_path') or 'Not selected'); self._update_face_info()
            finally:self._syncing_controls=False
            if old_theme!=self.settings.get('ui_theme'): self.apply_theme()
        if 'bridge: ready' not in self.integration.text() and time.monotonic()>=self._next_le_try:
            self._next_le_try=time.monotonic()+5.0        # detection reads the registry and logs: retry every 5 s
            self._prepare_live_editor_bridge()
        h=engine_health(); g=bool(detect_game())
        # v1.0.3: returning to FC27's main menu is detected from Live Editor's log. Say so when
        # that log cannot be found, instead of silently keeping the last career on screen.
        if g and 'bridge: ready' in self.integration.text() and time.monotonic()>=self._next_logs_check:
            self._next_logs_check=time.monotonic()+30.0
            try:
                from .le_menu_watch import find_logs_dir
                self._logs_found=find_logs_dir() is not None
            except Exception:
                self._logs_found=True
            base=self.integration.text().split(' • Live Editor log not found')[0]
            self.integration.setText(base if self._logs_found else base+(' • Live Editor log not found, so returning to the main menu is not detected '
                '(the overlay keeps the last career until you load another). If Live Editor runs as administrator, restart Academy Engine as administrator.'))
        if self._game_was_running and not g:
            clear_live_session_markers()
            try: detach_runtime('FC27 closed')
            except Exception: pass
        self._game_was_running=g
        le=live_editor_status(self.settings.get('live_editor_root') or None)
        self._set_status(self.game,'Running' if g else 'Not running','good' if g else 'muted')
        self._set_status(self.engine,'Running' if h.get('running') else 'Starting…','good' if h.get('running') else 'warn')
        if not h.get('running'): ensure_running()

        if g:
            host=ensure_overlay_host(); host_ok=bool(host.get('ok'))
            hb=bool(host.get('heartbeat'))
            label='External host ready' if (host_ok and hb) else ('External host starting…' if host_ok else 'External host recovering…')
            self._set_status(self.overlay,label,'good' if (host_ok and hb) else 'warn')
            detail=(str(host.get('detail') or host.get('status') or '')) + ' • No Academy UI code is injected into FC27.exe.'
            mismatch=elevation_mismatch()
            self.elev_row.setVisible(mismatch)
            if mismatch:
                detail=('FC27 is running as administrator but Academy Engine is not, so Windows blocks the overlay over the game. '
                        'Restart Academy Engine as administrator with the button below.'+(' '+self._elev_note if self._elev_note else '')+' • '+detail)
                self._set_status(self.overlay,'Needs administrator','warn')
                if self.settings.get('auto_elevate') and not self._elevate_attempted:
                    self.restart_elevated()
            self.overlay_detail.setText(detail)
        else:
            stop_overlay_host(); host_ok=False
            self.elev_row.setVisible(False)
            self._set_status(self.overlay,'Waiting for FC27','muted')
            self.overlay_detail.setText('External overlay starts only after FC27 is detected. No Academy UI code is injected into FC27.exe.')

        rt=(le.get('runtime_marker') or {}); state=str(rt.get('state') or '').upper()
        life=runtime_lifecycle()
        lstate=str(life.get('state') or '').upper()
        loaded=bool(g and lstate=='READY' and life.get('career_uid') and life.get('storage_key'))
        # Full overlay generations are published by the bridge service only.
        # The launcher intentionally never rebuilds/publishes career data: doing
        # so while a snapshot is being reconciled can expose a stale/partial read
        # model and prematurely promote RECONCILING back to READY.
        if loaded:
            self._set_status(self.career,'Ready • '+self.settings.get('overlay_hotkey','F8')+' opens Academy Engine','good')
        elif g and lstate in {'CAREER_LOADING','RECONCILING','ADVANCING'}:
            self._set_status(self.career,'Synchronizing • '+str(life.get('detail') or lstate).title(),'info')
        else:
            self._set_status(self.career,'Not loaded','muted')

    def _set_auto_elevate(self,on):
        self.settings['auto_elevate']=bool(on); save_settings(self.settings)

    def restart_elevated(self):
        """Restart as administrator through the UAC prompt; this launcher then closes (v1.0.1)."""
        self._elevate_attempted=True
        ok,msg=elevation.relaunch_elevated()
        self._elev_note='' if ok else msg
        if ok:
            # Close once the event loop runs: this can be decided during start-up (the first
            # poll runs in __init__), before the window is shown or app.exec() has started.
            self._restarting=True; self.overlay_detail.setText(msg)
            QTimer.singleShot(0,self._finish_restart)
        else:
            self.overlay_detail.setText(msg)

    def _finish_restart(self):
        self.close(); QApplication.quit()

    def closeEvent(self,event):
        self.timer.stop(); stop_overlay_host(); stop_engine(); clear_live_session_markers(); event.accept()

def run():
    app=QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('FC27 Academy Engine')
    w=Launcher()
    # Size from the user's logical desktop geometry so the launcher opens large
    # enough to show the full setup/status content on normal displays while still
    # fitting on smaller/high-DPI screens. The scroll area remains the fallback.
    screen=app.primaryScreen()
    if screen:
        avail=screen.availableGeometry()
        target_w=max(960,min(1100,int(avail.width()*0.82)))
        target_h=max(760,min(900,int(avail.height()*0.90)))
        target_w=min(target_w,avail.width())
        target_h=min(target_h,avail.height())
        w.resize(target_w,target_h)
        frame=w.frameGeometry(); frame.moveCenter(avail.center()); w.move(frame.topLeft())
    else:
        w.resize(1040,860)
    if not w._restarting:      # restarting as administrator at start-up: never show this window
        w.show()
    return app.exec()
