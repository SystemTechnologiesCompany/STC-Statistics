"""Dedicated scientific workspaces with cancellable processes and live 3D views."""
import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import numpy as np
import pandas as pd
import nbformat
from PySide6.QtCore import Qt,QProcess,QProcessEnvironment,QTimer
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QScrollArea,QFrame,
    QLabel,QLineEdit,QSpinBox,QDoubleSpinBox,QCheckBox,QListWidget,QListWidgetItem,
    QTabWidget,QTableView,QStackedWidget,QFileDialog,QMessageBox,QSplitter,QAbstractItemView)
from .theme import GlassButton,GlassComboBox
from .science import CMAPS,TABLE_MIME,unpack_result,pack_result,render_result,notebook_code,display_table,scene_box_aspect,localize_result,translate_figures

PAGES={
 'maps':('Map Studio','Atelier cartes','Samples, contours, IDW grids, terrain derivatives and profiles.','Points, isovaleurs, grilles IDW, dérivées et profils.'),
 'scene':('3D Studio','Atelier 3D','Rotate point clouds, terrain surfaces and interpolated scalar volumes.','Explorer des points, surfaces et volumes scalaires interpolés.'),
 'relations':('Correlation Lab','Corrélations','Annotated heatmaps, scatter matrices and bivariate diagnostics.','Cartes annotées, matrices de nuages et diagnostics bivariés.'),
 'prediction':('Prediction Lab','Prédiction','Random Forest and Gradient Boosting with honest train/test evaluation.','Random Forest et Gradient Boosting avec évaluation apprentissage/test.')}

TABLE_NAMES={
 'Sample values':'Valeurs des points','Point cloud':'Nuage de points',
 'Grid values':'Valeurs de la grille','Volume values':'Valeurs du volume','Profile':'Profil','Regional plane':'Plan régional',
 'Correlation':'Corrélation','Pair counts':'Effectifs par paire','Bivariate statistics':'Statistiques bivariées',
 'Train and test metrics':'Mesures apprentissage et test','Repeated-split summary':'Résumé des répétitions',
 'Predictions':'Prédictions','Feature importance':'Importance des variables','Hyperparameters':'Hyperparamètres'}


def l(app,en,fr): return fr if app.language=='fr' else en


class StudioPage(QWidget):
    def __init__(self,app,key):
        super().__init__()
        self.app,self.key=app,key
        self.fields={}; self.labels=[]; self.choices=[]; self.result=None; self.output_cell=None; self.job=None
        self.columns_signature=None
        outer=QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        actions=QHBoxLayout()
        self.make_button=self.button(actions,'Compute','Calculer',self.run,True)
        self.recipe_button=self.button(actions,'Editable Python','Python modifiable',self.recipe)
        self.cancel_button=self.button(actions,'Cancel calculation','Annuler le calcul',self.cancel)
        self.cancel_button.setEnabled(False)
        actions.addStretch()
        self.button(actions,'Data page','Page Données',lambda:app.navigate('data'))
        if key in ('maps','scene'):
            self.button(actions,'Open spatial file','Ouvrir un fichier spatial',app.open_file)
        self.button(actions,'Spatial demo','Exemple spatial',self.demo)
        outer.addLayout(actions)
        self.status=QLabel(); self.status.setWordWrap(True); outer.addWidget(self.status)
        self.progress=__import__('PySide6.QtWidgets',fromlist=['QProgressBar']).QProgressBar()
        self.progress.setRange(0,100); self.progress.hide(); outer.addWidget(self.progress)
        splitter=QSplitter(Qt.Orientation.Horizontal); outer.addWidget(splitter,1)
        holder=QWidget(); form_layout=QVBoxLayout(holder); form_layout.setContentsMargins(8,8,12,8)
        if key in ('maps','scene'):
            hint=QLabel(); hint.setWordWrap(True); form_layout.addWidget(hint)
            self.labels.append((hint,'Only numeric columns are listed. Decimal-comma text can be converted after reviewing a preview.',
                'Seules les colonnes numériques sont proposées. Convertissez les nombres texte à virgule après vérification de l’aperçu.'))
            self.button(form_layout,'Prepare numbers…','Préparer les nombres…',self.prepare_numbers)
        self.form=QVBoxLayout(); self.form.setSpacing(6)
        form_layout.addLayout(self.form); form_layout.addStretch()
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(holder)
        scroll.setMinimumWidth(245); scroll.setMaximumWidth(340); splitter.addWidget(scroll)
        self.tabs=QTabWidget(); splitter.addWidget(self.tabs); splitter.setStretchFactor(1,1)
        visual=QWidget(); visual_layout=QVBoxLayout(visual); self.visual_layout=visual_layout
        self.plot_picker=GlassComboBox(); self.plot_picker.currentIndexChanged.connect(self.select_plot)
        visual_layout.addWidget(self.plot_picker)
        self.figures=QStackedWidget(); visual_layout.addWidget(self.figures,1)
        empty=QLabel(); empty.setWordWrap(True); empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label=empty
        self.labels.append((empty,'Load Excel/CSV on Data, choose columns and Compute.\n3D views support mouse rotation; calculations stay local.',
                            'Importez Excel/CSV dans Données, choisissez les colonnes et calculez.\nRotation 3D à la souris ; calculs locaux.'))
        self.figures.addWidget(empty)
        bar=QHBoxLayout()
        self.button(bar,'Save current figure','Enregistrer la figure',self.save_figure)
        self.button(bar,'Expand view','Agrandir la vue',self.expand_view)
        self.button(bar,'Open notebook results','Voir les résultats Python',lambda:app.navigate('notebook'))
        bar.addStretch(); visual_layout.addLayout(bar)
        self.tabs.addTab(visual,'Visual')
        values=QWidget(); values_layout=QVBoxLayout(values)
        self.table_picker=GlassComboBox(); self.table_picker.currentIndexChanged.connect(self.select_table)
        values_layout.addWidget(self.table_picker)
        self.table=QTableView(); self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        values_layout.addWidget(self.table,1)
        bar=QHBoxLayout()
        self.button(bar,'Export full table','Exporter toute la table',self.export_table)
        if key=='maps': self.button(bar,'ESRI ASCII grid','Grille ASCII ESRI',self.export_grid)
        if key=='scene': self.button(bar,'OBJ surface mesh','Maillage de surface OBJ',self.export_obj)
        values_layout.addLayout(bar); self.tabs.addTab(values,'Values')
        self.notes=__import__('PySide6.QtWidgets',fromlist=['QPlainTextEdit']).QPlainTextEdit()
        self.notes.setReadOnly(True); self.tabs.addTab(self.notes,'Methods & limits')
        self.plots=[]
        self.build_controls()
        self.mode_changed()
        self.translate()

    def button(self,layout,en,fr,callback,primary=False):
        widget=GlassButton()
        if primary: widget.setObjectName('primary')
        widget.clicked.connect(callback); layout.addWidget(widget); self.labels.append((widget,en,fr))
        return widget

    def field(self,key,en,fr,widget):
        label=QLabel(); label.setWordWrap(True); self.labels.append((label,en,fr))
        self.form.addWidget(label); self.form.addWidget(widget); self.form.addSpacing(6); self.fields[key]=widget
        if isinstance(widget,GlassComboBox): widget.currentIndexChanged.connect(self.changed)
        elif isinstance(widget,(QSpinBox,QDoubleSpinBox)): widget.valueChanged.connect(self.changed)
        elif isinstance(widget,QCheckBox): widget.toggled.connect(self.changed)
        elif isinstance(widget,QLineEdit): widget.textEdited.connect(self.changed)
        return widget

    def combo(self,key,en,fr,values):
        widget=GlassComboBox()
        for a,b,value in values: widget.addItem(l(self.app,a,b),value)
        self.choices.append((widget,values)); return self.field(key,en,fr,widget)

    def column(self,key,en,fr): return self.field(key,en,fr,GlassComboBox())

    def integer(self,key,en,fr,value,low,high):
        widget=QSpinBox(); widget.setRange(low,high); widget.setValue(value)
        return self.field(key,en,fr,widget)

    def number(self,key,en,fr,value,low,high,decimals=3):
        widget=QDoubleSpinBox(); widget.setDecimals(decimals); widget.setRange(low,high); widget.setValue(value)
        return self.field(key,en,fr,widget)

    def check(self,key,en,fr,checked=False):
        widget=QCheckBox(); widget.setChecked(checked); return self.field(key,en,fr,widget)

    def listing(self,key,en,fr):
        widget=QListWidget(); widget.setMinimumHeight(170); widget.itemChanged.connect(self.changed)
        return self.field(key,en,fr,widget)

    def build_controls(self):
        if self.key in ('maps','scene'):
            self.column('x','X / easting','X / coordonnée Est'); self.column('y','Y / northing','Y / coordonnée Nord')
            if self.key=='scene': self.column('z','Z / elevation or depth','Z / altitude ou profondeur')
            self.column('value',('Colour property (points) / volume scalar' if self.key=='scene' else 'Property / scalar value'),
                        ('Couleur (points) / scalaire du volume' if self.key=='scene' else 'Propriété / valeur scalaire'))
            self.combo('coordinate_mode','Input coordinates','Coordonnées d’entrée',[
                ('Local/projected planar X/Y','X/Y locales ou projetées','planar'),
                ('WGS84 longitude/latitude → UTM','Longitude/latitude WGS84 → UTM','wgs84')])
            self.integer('utm_zone','UTM zone (0 = automatic)','Zone UTM (0 = automatique)',0,0,60)
            self.fields['coordinate_mode'].currentIndexChanged.connect(self.update_profile_bounds)
            self.fields['utm_zone'].valueChanged.connect(self.update_profile_bounds)
            for role in ('x','y'): self.fields[role].currentIndexChanged.connect(self.update_profile_bounds)
            if self.key=='maps':
                modes=[('Sample locations','Localisation des points','samples'),('Filled contours','Isovaleurs colorées','contour'),
                       ('Contour lines','Courbes de niveau','lines'),('Gridded heatmap','Grille colorée','grid'),
                       ('Hillshade','Ombrage','hillshade'),('Gradient magnitude','Norme du gradient','gradient'),('Residual anomaly','Anomalie résiduelle','residual')]
            else:
                modes=[('3D point cloud','Nuage de points 3D','points'),('Gridded surface','Surface interpolée','surface'),
                       ('Triangulated surface (TIN)','Surface triangulée (TIN)','tin'),('Wireframe','Maillage filaire','wireframe'),
                       ('Volume slices','Coupes du volume','slices'),('Thresholded voxels','Voxels par seuil','voxels')]
            mode=self.combo('mode','View / model','Vue / modèle',modes)
            mode.setCurrentIndex(1 if self.key=='maps' else 0)
            mode.currentIndexChanged.connect(self.mode_changed)
            self.combo('interpolation','Interpolation','Interpolation',[('IDW','IDW','idw'),('Linear triangulation','Triangulation linéaire','linear'),('Nearest neighbour','Plus proche voisin','nearest')])
            self.fields['interpolation'].currentIndexChanged.connect(self.mode_changed)
            self.integer('resolution','Grid resolution (longest axis)','Résolution de grille (axe le plus long)',70,12,200)
            self.integer('neighbors','IDW neighbours','Voisins IDW',12,1,64)
            self.number('power','IDW power','Puissance IDW',2,.1,8)
            self.combo('cmap','Colour scale','Échelle de couleurs',[(v,v,v) for v in CMAPS])
            self.field('crs','Coordinate reference label (no reprojection)','Référence des coordonnées (sans reprojection)',QLineEdit('Local / projected coordinates'))
            if self.key=='scene':
                self.number('exaggeration','Vertical view exaggeration','Exagération verticale de la vue',1,.01,100)
                self.number('elevation','Camera elevation (°)','Élévation de la caméra (°)',28,-89,89,1)
                self.number('azimuth','Camera azimuth (°)','Azimut de la caméra (°)',-60,-360,360,1)
                self.check('depth_down','Z increases downward','Z croît vers le bas')
                self.number('threshold','Voxel value percentile','Percentile du seuil voxel',50,0,99.9,1)
            else:
                self.check('profile','Extract a line profile','Extraire un profil')
                for key,en,fr in [('start_x','Profile start X','Départ X'),('start_y','Profile start Y','Départ Y'),('end_x','Profile end X','Fin X'),('end_y','Profile end Y','Fin Y')]:
                    self.number(key,en,fr,0,-1e12,1e12,5)
                self.fields['profile'].toggled.connect(self.mode_changed)
        elif self.key=='relations':
            self.listing('columns','Variables (2–12; max 6 for scatter matrix)','Variables (2–12 ; 6 pour la matrice de nuages)')
            self.combo('mode','Visual analysis','Analyse visuelle',[('Annotated heatmap','Carte de corrélation annotée','heatmap'),
                ('Scatter matrix','Matrice de nuages','matrix'),('Bivariate scatter + OLS','Nuage bivarié + droite OLS','scatter'),('Bivariate density','Densité bivariée','density')])
            self.combo('method','Association coefficient','Coefficient d’association',[(s.title(),s.title(),s) for s in ('pearson','spearman','kendall')])
            self.integer('min_pairs','Minimum complete pairs','Minimum de paires complètes',3,3,1000000)
            self.check('squared','Squared coefficient in heatmap','Coefficient au carré dans la carte')
            self.combo('cmap','Density colour scale','Couleurs de densité',[(v,v,v) for v in CMAPS])
        else:
            self.column('target','Response to predict','Variable à prédire')
            self.fields['target'].currentIndexChanged.connect(self.target_changed)
            self.listing('features','Predictors (response excluded)','Prédicteurs (réponse exclue)')
            self.combo('algorithm','Regression models','Modèles de régression',[('Compare RF + GB','Comparer RF + GB','both'),('Random Forest','Random Forest','rf'),('Gradient Boosting','Gradient Boosting','gb')])
            self.combo('split','Train / test split','Séparation apprentissage / test',[('Random rows','Lignes aléatoires','random'),('Held-out groups / wells','Groupes / puits séparés','group'),('Ordered last rows for test','Dernières lignes en test','ordered')])
            self.column('group','Group / site / well column (group split only)','Groupe / site / puits (séparation par groupes)')
            self.number('test_fraction','Test fraction','Fraction de test',.2,.1,.5,2)
            self.integer('repeats','Repeated experiments','Expériences répétées',3,1,10)
            self.integer('seed','Reproducible seed','Graine reproductible',42,0,1000000)
            self.integer('trees','Number of trees','Nombre d’arbres',100,10,500)
            self.integer('rf_depth','RF max depth (0 = unlimited)','Profondeur RF (0 = illimitée)',0,0,50)
            self.integer('gb_depth','GB tree depth','Profondeur des arbres GB',3,1,10)
            self.number('learning_rate','GB learning rate','Taux d’apprentissage GB',.05,.001,1)
            self.integer('min_leaf','Minimum rows per leaf','Lignes minimum par feuille',1,1,50)
            self.check('tune','Tune on training CV only','Optimiser sur la validation d’apprentissage uniquement')
            self.integer('folds','Training CV folds','Plis de validation d’apprentissage',3,2,5)
            self.integer('trials','Search trials per model / repeat','Essais par modèle / répétition',6,1,12)
            self.check('predict_missing','Predict rows with missing response','Prédire les réponses manquantes',True)
            for key in ('algorithm','split','group'):
                self.fields[key].currentIndexChanged.connect(self.mode_changed)
            self.fields['tune'].toggled.connect(self.mode_changed)

    def mode_changed(self):
        if self.app.science_busy: return
        if self.key in ('maps','scene') and 'resolution' in self.fields:
            mode=self.fields['mode'].currentData()
            grid=mode not in ('samples','points')
            if self.key=='scene':
                maximum=20 if mode=='voxels' else 28 if mode=='slices' else 200
                self.fields['resolution'].setMaximum(maximum)
                self.fields['value'].setEnabled(mode in ('points','slices','voxels'))
                if 'threshold' in self.fields: self.fields['threshold'].setEnabled(mode=='voxels')
                if mode=='tin': self.fields['interpolation'].setCurrentIndex(self.fields['interpolation'].findData('linear'))
            for key in ('resolution','interpolation'): self.fields[key].setEnabled(grid and mode!='tin')
            for key in ('neighbors','power'): self.fields[key].setEnabled(grid and mode!='tin' and self.fields['interpolation'].currentData()=='idw')
            if self.key=='maps' and 'profile' in self.fields:
                self.fields['profile'].setEnabled(grid)
                for key in ('start_x','start_y','end_x','end_y'): self.fields[key].setEnabled(grid and self.fields['profile'].isChecked())
        elif self.key=='prediction' and 'trials' in self.fields:
            grouped=self.fields['split'].currentData()=='group'
            self.fields['group'].setEnabled(grouped)
            if grouped:
                group=self.fields['group'].currentData()
                for i in range(self.fields['features'].count()):
                    item=self.fields['features'].item(i)
                    if item.data(Qt.ItemDataRole.UserRole)==group: item.setCheckState(Qt.CheckState.Unchecked)
            for key in ('trials','folds'): self.fields[key].setEnabled(self.fields['tune'].isChecked())
            self.fields['rf_depth'].setEnabled(self.fields['algorithm'].currentData()!='gb')
            for key in ('gb_depth','learning_rate'): self.fields[key].setEnabled(self.fields['algorithm'].currentData()!='rf')

    def update_profile_bounds(self,*args):
        if self.key!='maps' or 'start_x' not in self.fields or self.app.frame is None: return
        try:
            from .science import project_xy,numeric_frame
            options=self.options()
            numeric=numeric_frame(self.app.frame,[options['x'],options['y']]).dropna()
            if not len(numeric): return
            points,_,_=project_xy(numeric.to_numpy(),options)
            for i,(start,end) in enumerate((('start_x','end_x'),('start_y','end_y'))):
                self.fields[start].setValue(float(points[:,i].min())); self.fields[end].setValue(float(points[:,i].max()))
        except (ValueError,KeyError,TypeError): pass

    def changed(self,*args):
        self.app.mark_dirty()
        if self.result is not None:
            self.status.setText(l(self.app,'Settings/data may differ from this saved result. Compute to refresh.','Les paramètres/données peuvent différer du résultat enregistré. Recalculez pour actualiser.'))
            sender=self.sender()
            if self.key=='scene' and self.plots and any(sender is self.fields.get(k) for k in ('elevation','azimuth','exaggeration','depth_down')):
                ax=self.plots[0][1].axes[0]
                ax.view_init(elev=self.fields['elevation'].value(),azim=self.fields['azimuth'].value(),roll=0)
                controller=getattr(self.plots[0][1].canvas,'_stc_orbit',None)
                aspect=scene_box_aspect(self.result,self.fields['exaggeration'].value())
                if controller: controller.set_aspect(aspect)
                else: ax.set_box_aspect(aspect)
                if bool(ax.zaxis_inverted())!=self.fields['depth_down'].isChecked(): ax.invert_zaxis()
                self.result['options'].update({k:self.fields[k].isChecked() if k=='depth_down' else self.fields[k].value() for k in ('elevation','azimuth','exaggeration','depth_down')})
                self.plots[0][1].canvas.draw_idle()
                self.status.setText(l(self.app,'3D view updated. Calculated values are unchanged.','Vue 3D actualisée. Les valeurs calculées restent intactes.'))

    def target_changed(self):
        if 'features' not in self.fields: return
        target=self.fields['target'].currentData()
        for i in range(self.fields['features'].count()):
            item=self.fields['features'].item(i)
            if item.data(Qt.ItemDataRole.UserRole)==target: item.setCheckState(Qt.CheckState.Unchecked)

    def refresh_columns(self):
        frame=self.app.frame
        numeric=[] if frame is None else list(frame.select_dtypes(include='number').columns)
        all_columns=[] if frame is None else list(frame.columns)
        signature=tuple(all_columns),tuple(numeric)
        if signature==self.columns_signature: return
        self.columns_signature=signature
        defaults={'x':0,'y':1,'z':2,'value':3 if self.key=='scene' else 2,'target':len(numeric)-1,'group':0}
        defaults['group']=next((i for i,column in enumerate(all_columns) if column not in numeric),0)
        for key,widget in self.fields.items():
            if isinstance(widget,GlassComboBox) and key in defaults:
                choices=all_columns if key=='group' else numeric
                previous=widget.currentData(); had_items=widget.count()>0; widget.blockSignals(True); widget.clear()
                for column in choices: widget.addItem(str(column),column)
                if key=='value' and self.key=='maps': widget.addItem(l(self.app,'No scalar (points only)','Sans valeur (points seuls)'),None)
                index=widget.findData(previous)
                default=min(max(0,defaults[key]),len(choices)-1)
                if key=='value' and self.key=='maps' and len(choices)<3: default=len(choices)
                if key=='value' and self.key=='maps' and previous is None and len(choices)>=3 and self.fields['mode'].currentData()!='samples': index=-1
                widget.setCurrentIndex(index if had_items and index>=0 else default)
                widget.blockSignals(False)
            elif isinstance(widget,QListWidget):
                previous=[widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(widget.count()) if widget.item(i).checkState()==Qt.CheckState.Checked]
                widget.blockSignals(True); widget.clear()
                for i,column in enumerate(numeric):
                    item=QListWidgetItem(str(column)); item.setData(Qt.ItemDataRole.UserRole,column)
                    item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
                    selected=column in previous if previous else (i<6 if key=='columns' else column!=self.fields['target'].currentData())
                    item.setCheckState(Qt.CheckState.Checked if selected else Qt.CheckState.Unchecked); widget.addItem(item)
                widget.blockSignals(False)
        self.target_changed()
        self.update_profile_bounds()

    def options(self):
        result={}
        for key,widget in self.fields.items():
            if isinstance(widget,GlassComboBox): result[key]=widget.currentData()
            elif isinstance(widget,QListWidget): result[key]=[widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(widget.count()) if widget.item(i).checkState()==Qt.CheckState.Checked]
            elif isinstance(widget,QCheckBox): result[key]=widget.isChecked()
            elif isinstance(widget,(QSpinBox,QDoubleSpinBox)): result[key]=widget.value()
            else: result[key]=widget.text()
        if self.key=='prediction': result['features']=[c for c in result['features'] if c!=result['target']]
        if self.key=='maps' and result['mode']=='samples': result['profile']=False
        result['language']=self.app.language
        return result

    def restore_options(self,values):
        self.refresh_columns()
        for key,value in values.items():
            widget=self.fields.get(key)
            if widget is None: continue
            if isinstance(widget,GlassComboBox):
                index=widget.findData(value)
                if index>=0: widget.setCurrentIndex(index)
            elif isinstance(widget,QListWidget):
                for i in range(widget.count()): widget.item(i).setCheckState(Qt.CheckState.Checked if widget.item(i).data(Qt.ItemDataRole.UserRole) in value else Qt.CheckState.Unchecked)
            elif isinstance(widget,QCheckBox): widget.setChecked(bool(value))
            elif isinstance(widget,(QSpinBox,QDoubleSpinBox)): widget.setValue(value)
            else: widget.setText(str(value))
        self.mode_changed()

    def translate(self):
        for widget,en,fr in self.labels: widget.setText(l(self.app,en,fr))
        for widget,choices in self.choices:
            for i,(en,fr,value) in enumerate(choices): widget.setItemText(i,l(self.app,en,fr))
        for i,en,fr in [(0,'Visuals','Graphiques'),(1,'Values & export','Valeurs et export'),(2,'Methods & limits','Méthodes et limites')]: self.tabs.setTabText(i,l(self.app,en,fr))
        if self.result is None: self.status.setText(l(self.app,'Ready · load data and choose the variable roles.','Prêt · importez les données et attribuez les variables.'))
        else:
            self.status.setText(l(self.app,'Saved result — compute to apply changed inputs/settings.','Résultat enregistré — recalculez pour appliquer d’autres données/paramètres.'))
            self.plots=translate_figures(self.plots,self.app.language)
            for i,(title,figure) in enumerate(self.plots):
                self.plot_picker.setItemText(i,title); figure.canvas.draw_idle()
                controller=getattr(figure.canvas,'_stc_orbit',None)
                if controller: controller.toolbar.set_language(self.app.language)
            for i in range(self.table_picker.count()):
                title=self.table_picker.itemData(i)
                self.table_picker.setItemText(i,TABLE_NAMES.get(title,title) if self.app.language=='fr' else title)
            self.select_table(self.table_picker.currentIndex())
            localized=localize_result(dict(self.result,notes=list(self.result.get('notes_en',self.result['notes'])),options=dict(self.result['options'],language=self.app.language)))
            self.notes.setPlainText('\n\n'.join(localized['notes']))

    def set_busy(self,busy):
        self.make_button.setEnabled(not busy); self.recipe_button.setEnabled(not busy)
        self.cancel_button.setEnabled(bool(self.job)); self.progress.setVisible(bool(self.job))
        for widget in self.fields.values(): widget.setEnabled(not busy)
        if not busy: self.mode_changed()

    def recipe(self):
        if self.app.science_busy: return
        self.app.add_cell(notebook_code(self.key,self.options()))

    def prepare_numbers(self):
        from .workbench import guard,clean
        def prepare():
            if self.app.frame is None:
                self.app.navigate('data'); return
            candidates=[]
            for name in self.app.frame.columns:
                series=self.app.frame[name]
                if pd.api.types.is_numeric_dtype(series.dtype): continue
                text=series.dropna().astype('string').str.strip()
                if len(text) and text.str.contains(',',regex=False).any() and pd.to_numeric(text.str.replace(',','.',regex=False),errors='coerce').notna().all():
                    candidates.append(name)
            clean(self.app,initial_columns=candidates)
        guard(self.app,prepare)

    def validate_spatial_columns(self,options):
        if self.key not in ('maps','scene'): return True
        roles=[('x','X','X'),('y','Y','Y')]
        if self.key=='scene': roles.append(('z','Z / elevation','Z / altitude'))
        if (self.key=='maps' and options['mode']!='samples') or (self.key=='scene' and options['mode'] in ('slices','voxels')):
            roles.append(('value','Property / scalar value','Propriété / valeur scalaire'))
        numeric=set(self.app.frame.select_dtypes(include='number').columns)
        missing=[l(self.app,en,fr) for key,en,fr in roles if options.get(key) not in numeric]
        if not missing: return True
        message=l(self.app,'Choose numeric columns for: ','Choisissez des colonnes numériques pour : ')+', '.join(missing)+'.\n'+l(self.app,
            'If your Excel numbers use decimal commas, click Prepare numbers, review the preview and apply. Then select the columns again.',
            'Si les nombres Excel utilisent une virgule décimale, cliquez sur Préparer les nombres, vérifiez l’aperçu et appliquez. Sélectionnez ensuite les colonnes.')
        self.status.setText(message+' — STC-SCI102')
        QMessageBox.information(self.app,'STC Statistics',message+'\n\nSTC-SCI102')
        return False

    def run(self):
        if self.app.frame is None:
            self.app.navigate('data'); return
        if self.app.active or self.app.science_busy or (self.app.loader and self.app.loader.isRunning()): return
        options=self.options()
        if not self.validate_spatial_columns(options): return
        temporary=tempfile.TemporaryDirectory(prefix='stc-science-')
        folder=Path(temporary.name)
        try:
            self.app.frame.to_parquet(folder/'data.parquet',index=True)
            (folder/'request.json').write_text(json.dumps({'kind':self.key,'options':options}),encoding='utf-8')
            process=QProcess(self)
            environment=QProcessEnvironment.systemEnvironment()
            environment.insert('PYTHONPATH',str(Path(__file__).resolve().parent.parent))
            for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'): environment.insert(name,'1')
            environment.remove('PYTHONHOME'); process.setProcessEnvironment(environment)
            process.setProgram(sys.executable); process.setArguments(['-B','-m','stc_statistics.science_worker',str(folder)])
            self.job={'process':process,'temp':temporary,'folder':folder,'options':options,'cancelled':False}
            self.app.science_busy=True; self.app.set_busy(False)
            self.progress.setValue(0); self.progress.show()
            self.status.setText(l(self.app,'Calculating locally… You can cancel safely.','Calcul local… Vous pouvez annuler sans risque.'))
            process.readyReadStandardOutput.connect(self.read_progress)
            process.finished.connect(self.finished)
            process.errorOccurred.connect(lambda error:self.finished(-1) if self.job and process.state()==QProcess.ProcessState.NotRunning else None)
            process.start()
        except Exception as exc:
            temporary.cleanup(); self.job=None; self.app.science_busy=False; self.app.set_busy(False)
            from .feedback import show_error
            show_error(self.app,'input',exc)

    def read_progress(self):
        if not self.job: return
        process=self.job['process']
        while process.canReadLine():
            try: self.progress.setValue(int(json.loads(bytes(process.readLine()))['progress']))
            except (ValueError,KeyError): pass

    def cancel(self):
        if self.job:
            self.job['cancelled']=True; self.job['process'].kill()

    def finished(self,*args):
        if not self.job: return
        job=self.job; self.job=None
        try:
            folder=job['folder']
            if job['cancelled']:
                self.status.setText(l(self.app,'Calculation cancelled. Your data is unchanged.','Calcul annulé. Vos données sont intactes.'))
            elif (folder/'result.json').is_file():
                packed=json.loads((folder/'result.json').read_text(encoding='utf-8'))
                result=unpack_result(packed)
                self.display_result(result)
                self.record_result(packed,job['options'])
                self.status.setText(l(self.app,'Result saved in the notebook and project. Figures rotate/zoom; full tables export below.','Résultat conservé dans le notebook et le projet. Rotation/zoom des figures ; export des tables complètes.'))
            else:
                failure=json.loads((folder/'error.json').read_text(encoding='utf-8')) if (folder/'error.json').exists() else {'message':'Calculation unavailable / Calcul indisponible','code':'STC-SCI101'}
                from .update_messages import record_error
                diagnostic=(folder/'diagnostic.log').read_text(encoding='utf-8') if (folder/'diagnostic.log').exists() else bytes(job['process'].readAllStandardError()).decode(errors='replace')[-12000:]
                record_error('STC-SCI101',diagnostic,'science')
                parts=failure['message'].split(' / ',1)
                message=parts[-1] if self.app.language=='fr' else parts[0]
                self.status.setText(message+' · '+failure['code'])
                QMessageBox.warning(self.app,'STC Statistics',message+'\n'+failure['code'])
        except Exception as exc:
            from .feedback import show_error
            show_error(self.app,'input',exc)
        finally:
            job['process'].deleteLater(); job['temp'].cleanup()
            self.app.science_busy=False; self.app.set_busy(bool(self.app.active)); self.progress.hide()
            if getattr(self.app,'_science_close_pending',False):
                self.app._science_close_pending=False; QTimer.singleShot(0,self.app.close)

    def display_result(self,result):
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg,NavigationToolbar2QT
        self.result=result; self.plots=translate_figures(render_result(result),self.app.language)
        while self.figures.count():
            widget=self.figures.widget(0); self.figures.removeWidget(widget)
            if widget is self.empty_label: widget.hide()
            else: widget.deleteLater()
        self.plot_picker.blockSignals(True); self.plot_picker.clear()
        for title,figure in self.plots:
            view=QWidget(); layout=QVBoxLayout(view); layout.setContentsMargins(0,0,0,0)
            canvas=FigureCanvasQTAgg(figure)
            if self.key=='scene':
                from .scene_view import install_orbit
                toolbar=install_orbit(canvas,result,self.capture_camera,self.app.language,view)
            else:
                toolbar=NavigationToolbar2QT(canvas,view)
                toolbar.setStyleSheet('background:#edf4ef;color:#172a20;')
            layout.addWidget(toolbar)
            minimum_height=0; minimum_width=0
            if self.key=='prediction' and getattr(figure,'_stc_plot_name',title) in ('Observed vs predicted','Residual diagnostics'):
                minimum_height=300*(len(figure.axes)//2); minimum_width=630
            elif self.key=='relations' and result['mode']=='matrix':
                count=len(result['numeric'].columns); minimum_height=160*count; minimum_width=160*count
            if minimum_height:
                canvas.setMinimumSize(minimum_width,minimum_height)
                area=QScrollArea(); area.setWidgetResizable(True); area.setWidget(canvas); layout.addWidget(area,1)
            else: layout.addWidget(canvas,1)
            self.figures.addWidget(view)
            self.plot_picker.addItem(title); canvas.draw_idle()
        self.plot_picker.blockSignals(False); self.select_plot(0)
        self.table_picker.blockSignals(True); self.table_picker.clear()
        for title in result['tables']: self.table_picker.addItem(TABLE_NAMES.get(title,title) if self.app.language=='fr' else title,title)
        self.table_picker.blockSignals(False); self.select_table(0)
        localized=localize_result(dict(result,notes=list(result.get('notes_en',result['notes'])),options=dict(result['options'],language=self.app.language)))
        self.notes.setPlainText('\n\n'.join(localized['notes']))
        self.status.setText(l(self.app,'Saved result · compute to apply changed inputs/settings.','Résultat enregistré · recalculez pour appliquer d’autres données/paramètres.'))

        if self.key=='scene' and self.plots: self.capture_camera(mark_dirty=False)

    def capture_camera(self,event=None,mark_dirty=True):
        if self.key!='scene' or not self.plots: return
        ax=self.plots[0][1].axes[0]
        controller=getattr(self.plots[0][1].canvas,'_stc_orbit',None)
        if controller: self.result['options']['zoom']=controller.zoom
        for key,value in [('elevation',float(ax.elev)),('azimuth',float(ax.azim))]:
            widget=self.fields[key]; widget.blockSignals(True); widget.setValue(value); widget.blockSignals(False)
            self.result['options'][key]=value
        if mark_dirty: self.app.mark_dirty()

    def record_result(self,packed,options):
        # Keep historical images/code, but only the latest interactive payload per
        # workspace, so projects do not accumulate duplicate grids/model data.
        for old in self.app.cells:
            if getattr(old,'studio_key',None)==self.key: old.studio_payload=None
        cell=self.app.add_cell(notebook_code(self.key,options)); self.output_cell=cell
        cell.studio_key=self.key; cell.studio_payload=packed
        cell.executed_source=cell.editor.toPlainText()
        cell.outputs=[]
        for title,table in self.result['tables'].items():
            preview=display_table(title,table.head(150),self.app.language)
            title_local=TABLE_NAMES.get(title,title) if self.app.language=='fr' else title
            cell.outputs.append(nbformat.v4.new_output('display_data',data={'text/html':preview.to_html(),TABLE_MIME:preview.to_json(orient='split',double_precision=15)},metadata={'stc':{'title':title_local+(f' (aperçu / preview: {len(preview)} / {len(table)})' if len(preview)<len(table) else '')}}))
        for title,figure in self.plots:
            controller=getattr(figure.canvas,'_stc_orbit',None)
            if controller: controller.finish_interaction()
            data=io.BytesIO(); figure.savefig(data,format='png',dpi=150,facecolor='white')
            cell.outputs.append(nbformat.v4.new_output('display_data',data={'image/png':base64.b64encode(data.getvalue()).decode()},metadata={}))
        cell.outputs.append(nbformat.v4.new_output('stream',name='stdout',text='\n'.join(self.result['notes'])+'\nLarge tables are previewed here; use Values & export for complete CSV/Excel tables.\n'))
        cell.render(); cell.chart_button.setVisible(bool(self.plots)); self.app.navigate(self.key,animate=False)

    def select_plot(self,index): self.figures.setCurrentIndex(index)

    def select_table(self,index):
        if not self.result or index<0: return
        title=self.table_picker.itemData(index)
        from .app import FrameModel
        self.table_model=FrameModel(display_table(title,self.result['tables'][title],self.app.language))
        self.table.setModel(self.table_model); self.table.resizeColumnsToContents()

    def save_figure(self):
        if not self.plots: return
        path,_=QFileDialog.getSaveFileName(self.app,l(self.app,'Save figure','Enregistrer la figure'),'STC_Figure.png','PNG (*.png);;PDF (*.pdf);;SVG (*.svg)')
        if path:
            try:
                figure=self.plots[self.plot_picker.currentIndex()][1]
                controller=getattr(figure.canvas,'_stc_orbit',None)
                if controller: controller.finish_interaction()
                figure.savefig(path,dpi=220,facecolor='white')
            except Exception as exc:
                from .feedback import show_error
                show_error(self.app,'export',exc)

    def expand_view(self):
        if not self.plots: return
        from PySide6.QtWidgets import QDialog
        dialog=QDialog(self.app); dialog.setWindowTitle('STC Statistics · '+l(self.app,'Scientific view','Vue scientifique'))
        layout=QVBoxLayout(dialog); self.visual_layout.removeWidget(self.figures); layout.addWidget(self.figures)
        close=GlassButton(l(self.app,'Return to workspace','Retour à l’espace de travail')); close.clicked.connect(dialog.accept); layout.addWidget(close)
        dialog.showMaximized(); dialog.exec()
        self.visual_layout.insertWidget(1,self.figures,1); self.figures.show(); dialog.deleteLater()

    def export_table(self):
        if not self.result or self.table_picker.currentIndex()<0: return
        title=self.table_picker.currentData(); table=self.result['tables'][title]
        path,_=QFileDialog.getSaveFileName(self.app,l(self.app,'Export complete table','Exporter la table complète'),'STC_Values.xlsx','Excel (*.xlsx);;CSV (*.csv)')
        if path:
            try:
                from .science_exports import export_table
                export_table(display_table(title,table,self.app.language),path)
            except Exception as exc:
                from .feedback import show_error
                show_error(self.app,'export',exc)

    def export_grid(self):
        if not self.result: return
        if 'field' not in self.result:
            QMessageBox.information(self.app,'STC Statistics',l(self.app,'Compute a gridded map first. Point locations have no raster grid.','Calculez une carte maillée. Les points seuls ne constituent pas une grille.')); return
        path,_=QFileDialog.getSaveFileName(self.app,'ESRI ASCII grid','STC_Grid.asc','ESRI ASCII (*.asc)')
        if path:
            try:
                from .science_exports import export_ascii
                export_ascii(self.result,path)
            except Exception as exc:
                from .feedback import show_error
                show_error(self.app,'export',exc)

    def export_obj(self):
        if not self.result: return
        if self.result['mode'] in ('points','slices','voxels'):
            QMessageBox.information(self.app,'STC Statistics',l(self.app,'OBJ export requires a surface/TIN/wireframe. Export volume values as CSV instead.','OBJ nécessite une surface/TIN/maillage. Exportez les valeurs du volume en CSV.')); return
        path,_=QFileDialog.getSaveFileName(self.app,'OBJ surface','STC_Surface.obj','Wavefront OBJ (*.obj)')
        if path:
            try:
                from .science_exports import export_obj
                export_obj(self.result,path)
            except Exception as exc:
                from .feedback import show_error
                show_error(self.app,'export',exc)

    def demo(self):
        if self.app.science_busy or self.app.active: return
        if self.app.frame is not None and QMessageBox.question(self.app,'STC Statistics',l(self.app,'Replace the current data with the spatial demo? Save your project first.','Remplacer les données par l’exemple spatial ? Enregistrez d’abord votre projet.'),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes: return
        rng=np.random.default_rng(42); n=350
        x=rng.uniform(530000,580000,n); y=rng.uniform(240000,280000,n)
        z=250+80*np.sin((x-530000)/10000)+.0006*(y-240000)
        porosity=rng.uniform(8,28,n); permeability=np.maximum(.01,np.exp(.12*porosity)+.0003*(x-530000)+rng.normal(0,1.5,n))
        self.app.file_path=None; self.app.sheet.clear()
        self.app.use_frame(pd.DataFrame({'X':x,'Y':y,'Elevation_m':z,'Porosity_pct':porosity,'Permeability_mD':permeability,'Well_group':['Well-'+str(i%10) for i in range(n)]}))
        self.app.mark_dirty(); self.app.navigate(self.key)


def install(app):
    from .i18n import TEXT
    app.science_busy=False; app.studio_pages={}
    for key,(en,fr,en_desc,fr_desc) in PAGES.items():
        TEXT['en'].update({key:en,key+'_description':en_desc})
        TEXT['fr'].update({key:fr,key+'_description':fr_desc})
        page=StudioPage(app,key); app.studio_pages[key]=page; app.pages.addWidget(page)
        button=GlassButton(); button.setObjectName('navigation'); button.setCheckable(True); button.setMinimumHeight(34)
        button.clicked.connect(lambda checked=False,k=key:app.navigate(k)); app.nav_buttons[key]=button
    for key in ('projects','data','maps','scene','geology','analysis','relations','prediction','charts','notebook','exports','updates'):
        button=app.nav_buttons[key]; app.nav_layout.removeWidget(button); app.nav_layout.addWidget(button)


def save_states(app):
    states={}
    for key,page in app.studio_pages.items():
        options=page.options()
        if key=='scene' and page.result is not None and page.plots:
            axes=page.plots[0][1].axes[0]
            options.update(elevation=float(axes.elev),azimuth=float(axes.azim))
            controller=getattr(page.plots[0][1].canvas,'_stc_orbit',None)
            if controller: options['zoom']=controller.zoom
            page.result['options'].update(elevation=options['elevation'],azimuth=options['azimuth'])
            if page.output_cell is not None: page.output_cell.studio_payload=pack_result(page.result)
        states[key]=options
    return states


def restore_states(app,states):
    for page in app.studio_pages.values():
        page.result=None; page.output_cell=None
        page.plots=[]; page.plot_picker.clear(); page.table_picker.clear(); page.notes.clear()
        while page.figures.count():
            widget=page.figures.widget(0); page.figures.removeWidget(widget)
            if widget is not page.empty_label: widget.deleteLater()
        page.figures.addWidget(page.empty_label); page.empty_label.show()
        page.table.setModel(None)
    for key,values in states.items():
        if key in app.studio_pages: app.studio_pages[key].restore_options(values)
    for cell in app.cells:
        key=getattr(cell,'studio_key',None); payload=getattr(cell,'studio_payload',None)
        if key in app.studio_pages and payload:
            page=app.studio_pages[key]; page.display_result(unpack_result(payload)); page.output_cell=cell
