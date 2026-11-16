"""Centred, roll-free Qt orbit control with coalesced lightweight drag previews."""
import numpy as np
from PySide6.QtCore import QObject,QTimer
from PySide6.QtWidgets import QToolBar,QLabel


def preview_points(result,maximum=1200):
    mode=result['mode']
    if mode=='points': points=result['points']; colors=result['values']
    elif mode in ('slices','voxels'):
        axes=result['axes']; field=result['field']
        mask=np.isfinite(field)
        if mode=='voxels':
            mask &= field>=np.percentile(field[mask],float(result['options'].get('threshold',50)))
        else:
            sliced=np.zeros(field.shape,bool)
            for i in range(3):
                selector=[slice(None)]*3; selector[i]=len(axes[i])//2
                sliced[tuple(selector)]=True
            mask &= sliced
        indices=np.column_stack(np.nonzero(mask))
        points=np.column_stack([axes[i][indices[:,i]] for i in range(3)])
        colors=field[mask]
    else:
        x,y=result['axes']; xx,yy=np.meshgrid(x,y); field=result['field']; mask=np.isfinite(field)
        points=np.column_stack([xx[mask],yy[mask],field[mask]]); colors=field[mask]
    if len(points)>maximum:
        keep=np.linspace(0,len(points)-1,maximum,dtype=int)
        points=points[keep]; colors=colors[keep]
    return points,colors


class OrbitController(QObject):
    def __init__(self,canvas,result,on_commit):
        super().__init__(canvas)
        self.canvas,self.ax,self.result,self.on_commit=canvas,canvas.figure.axes[0],result,on_commit
        self.drag=None; self.pending=None; self.pending_zoom=False; self.previewing=False; self.closed=False
        self.home_angles=(float(np.clip(result['options'].get('elevation',28),-89,89)),
                          float((result['options'].get('azimuth',-60)+180)%360-180))
        self.ax.view_init(elev=self.home_angles[0],azim=self.home_angles[1],roll=0)
        self.bounds=[tuple(sorted(getter())) for getter in (self.ax.get_xlim3d,self.ax.get_ylim3d,self.ax.get_zlim3d)]
        self.zoom=float(np.clip(result['options'].get('zoom',1),.25,3))
        self.artists=[(artist,artist.get_visible()) for artist in self.ax.collections]
        points,colors=preview_points(result)
        norm=getattr(self.artists[0][0],'norm',None) if self.artists else None
        if norm is None or norm.vmin is None or norm.vmax is None:
            from matplotlib.colors import Normalize
            scalars=result.get('field',result['values'])
            norm=Normalize(vmin=np.nanmin(scalars),vmax=np.nanmax(scalars))
        style={'color':'#22965e'} if result['mode']=='wireframe' else {'c':colors,'norm':norm,'cmap':result['options'].get('cmap','viridis')}
        self.preview=self.ax.scatter(*points.T,s=5,depthshade=False,**style)
        self.preview.set_visible(False)
        self.center()
        self.ax.disable_mouse_rotation()
        self.set_aspect(self.ax.get_box_aspect())
        self.timer=QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(33)
        self.timer.timeout.connect(self.flush)
        self.settle=QTimer(self); self.settle.setSingleShot(True); self.settle.setInterval(140)
        self.settle.timeout.connect(self.finish_zoom)
        self.connections=[canvas.mpl_connect(name,callback) for name,callback in (
            ('button_press_event',self.press),('motion_notify_event',self.motion),
            ('button_release_event',self.release),('scroll_event',self.scroll),
            ('figure_leave_event',self.leave),('close_event',lambda event:self.dispose()))]
        canvas.destroyed.connect(self.dispose)

    def center(self):
        down=self.ax.zaxis_inverted()
        self.ax.set_xlim3d(*self.bounds[0]); self.ax.set_ylim3d(*self.bounds[1])
        self.ax.set_zlim3d(*(self.bounds[2][::-1] if down else self.bounds[2]))

    def set_aspect(self,aspect): self.ax.set_box_aspect(aspect,zoom=self.zoom)

    def press(self,event):
        # Axes3D's native handler otherwise schedules a full draw for every
        # motion, even after mouse_init has disabled its rotation buttons.
        self.ax.button_pressed=None
        if self.closed or event.button!=1 or event.inaxes is not self.ax: return
        self.drag=(float(event.x),float(event.y),float(self.ax.elev),float(self.ax.azim))

    def motion(self,event):
        if self.drag is None or event.x is None or event.y is None: return
        x,y,elevation,azimuth=self.drag
        sensitivity=180/max(150,min(self.canvas.width(),self.canvas.height()))
        self.pending=(float(np.clip(elevation+(event.y-y)*sensitivity,-89,89)),
                      float((azimuth-(event.x-x)*sensitivity+180)%360-180))
        self.show_preview()
        if not self.timer.isActive(): self.timer.start()

    def show_preview(self):
        if self.previewing: return
        for artist,visible in self.artists: artist.set_visible(False)
        self.ax.set_axis_off()
        self.preview.set_visible(True); self.previewing=True

    def full_detail(self):
        self.preview.set_visible(False)
        for artist,visible in self.artists: artist.set_visible(visible)
        self.ax.set_axis_on()
        self.previewing=False

    def flush(self):
        if self.closed: return
        changed=self.pending_zoom; self.pending_zoom=False
        if self.pending is not None:
            elevation,azimuth=self.pending; self.pending=None
            self.ax.view_init(elev=elevation,azim=azimuth,roll=0)
            changed=True
        if changed: self.canvas.draw_idle()

    def release(self,event=None):
        if self.closed or self.drag is None: return
        self.timer.stop(); self.settle.stop(); self.flush(); self.drag=None
        self.full_detail(); self.canvas.draw_idle(); self.on_commit()

    def leave(self,event):
        # Avoid leaving the model in preview mode when the pointer leaves the canvas.
        if self.drag is not None: self.release()

    def change_zoom(self,multiplier):
        if self.closed: return
        self.zoom=float(np.clip(self.zoom*multiplier,.25,3))
        self.set_aspect(self.ax.get_box_aspect()); self.show_preview(); self.pending_zoom=True
        if not self.timer.isActive(): self.timer.start()
        self.settle.start(); self.on_commit()

    def finish_zoom(self):
        if self.closed or self.drag is not None: return
        self.timer.stop(); self.settle.stop(); self.flush(); self.full_detail(); self.canvas.draw_idle()

    def finish_interaction(self):
        self.release(); self.finish_zoom()

    def scroll(self,event):
        if event.inaxes is self.ax: self.change_zoom(1.15**float(np.clip(event.step,-3,3)))

    def reset(self):
        if self.closed: return
        self.finish_interaction(); self.zoom=1.; self.center(); self.set_aspect(self.ax.get_box_aspect())
        self.ax.view_init(elev=self.home_angles[0],azim=self.home_angles[1],roll=0)
        self.canvas.draw_idle(); self.on_commit()

    def dispose(self,*args):
        if self.closed: return
        self.closed=True; self.timer.stop(); self.settle.stop()
        for connection in self.connections: self.canvas.mpl_disconnect(connection)


class OrbitToolbar(QToolBar):
    def __init__(self,controller,language,parent=None):
        super().__init__(parent)
        self.controller=controller; self.setMovable(False)
        self.reset_action=self.addAction('',controller.reset)
        self.in_action=self.addAction('',lambda:controller.change_zoom(1.15))
        self.out_action=self.addAction('',lambda:controller.change_zoom(1/1.15))
        self.addSeparator(); self.help=QLabel(); self.addWidget(self.help)
        self.setStyleSheet('QToolBar {background:#edf4ef;color:#172a20;} QToolButton {color:#172a20;padding:7px;border:0;} QToolButton:hover {background:#c9e8d5;} QLabel {color:#172a20;font-size:9pt;}')
        self.set_language(language)

    def set_language(self,language):
        french=language=='fr'
        self.reset_action.setText('Recentrer' if french else 'Reset view')
        self.in_action.setText('Zoom +'); self.out_action.setText('Zoom −')
        self.help.setText('Glisser : rotation · Molette : zoom' if french else 'Drag: orbit · Wheel: zoom')
        self.setToolTip('Aperçu allégé pendant le mouvement ; axes et détail complet reviennent à la fin.' if french else 'Lightweight preview while moving; axes and full detail return when you finish.')


def install_orbit(canvas,result,on_commit,language,parent):
    controller=OrbitController(canvas,result,on_commit)
    canvas._stc_orbit=controller
    controller.toolbar=OrbitToolbar(controller,language,parent)
    return controller.toolbar
