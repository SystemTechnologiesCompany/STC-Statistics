"""Task-specific desktop dialogs; all numerical recipes remain editable in Python."""
import base64
import html
import json
from pathlib import Path
import nbformat
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox, QLineEdit, QGridLayout, QWidget,
    QDoubleSpinBox, QSpinBox, QListWidget, QListWidgetItem, QMessageBox, QFileDialog,
    QTextBrowser, QPlainTextEdit, QHBoxLayout, QCheckBox)
from .theme import GlassComboBox as Combo, GlassButton as Button


def tr(app, en, fr):
    return fr if app.language == 'fr' else en


def dialog(app, title):
    d = QDialog(app)
    d.setWindowTitle(title)
    d.resize(720, 610)
    outer = QVBoxLayout(d)
    form = QFormLayout()
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    outer.addLayout(form)
    return d, outer, form


def choose(app, title, entries):
    d, outer, form = dialog(app, title)
    widgets = {}
    for key, label, values in entries:
        if isinstance(values, list):
            widget = Combo()
            for text, value in values:
                widget.addItem(text, value)
        else:
            widget = QLineEdit(str(values))
        widgets[key] = widget
        form.addRow(label, widget)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(d.accept)
    buttons.rejected.connect(d.reject)
    outer.addWidget(buttons)
    if d.exec() != QDialog.DialogCode.Accepted:
        return None
    return {k: (w.currentData() if isinstance(w, Combo) else w.text()) for k,w in widgets.items()}


def guard(app, fn):
    if getattr(app,'updating',False) or app.active or (app.loader and app.loader.isRunning()):
        return
    try:
        return fn()
    except Exception as exc:
        QMessageBox.warning(app, app.t('error'), str(exc))


def clean(app):
    if app.frame is None:
        raise ValueError(app.t('no_data'))
    from .projects import clean_frame
    picker, outer, form = dialog(app,tr(app,'Choose columns to clean','Choisir les colonnes à nettoyer'))
    listing = QListWidget()
    for c in app.frame.columns:
        item = QListWidgetItem(str(c))
        item.setData(Qt.ItemDataRole.UserRole,c)
        item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if c in app.selected_columns() else Qt.CheckState.Unchecked)
        listing.addItem(item)
    outer.addWidget(listing)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(picker.accept)
    buttons.rejected.connect(picker.reject)
    outer.addWidget(buttons)
    if picker.exec()!=QDialog.DialogCode.Accepted:
        return
    columns=[listing.item(i).data(Qt.ItemDataRole.UserRole) for i in range(listing.count()) if listing.item(i).checkState()==Qt.CheckState.Checked]
    options = choose(app, tr(app,'Clean selected columns','Nettoyer les colonnes sélectionnées'), [
        ('operation',tr(app,'Operation','Opération'),[(tr(app,e,f),v) for e,f,v in [
            ('Decimal comma → numbers','Virgule → nombres','numeric'),('Remove duplicate rows','Supprimer les doublons','duplicates'),
            ('Remove rows with missing values','Supprimer les lignes incomplètes','drop'),('Fill with mean','Remplir par moyenne','mean'),
            ('Fill with median','Remplir par médiane','median'),('Fill with mode','Remplir par mode','mode'),('Fill with constant','Remplir par constante','constant')]]),
        ('value',tr(app,'Constant','Constante'),'')])
    if not options:
        return
    result = clean_frame(app.frame, columns, **options)
    d, outer, form = dialog(app,tr(app,'Preview changes','Aperçu des modifications'))
    browser = QTextBrowser()
    browser.setHtml(f'<p>{len(app.frame)} → {len(result)} rows / lignes; missing / manquantes: {app.frame.isna().sum().sum()} → {result.isna().sum().sum()}</p>'+result.head(30).to_html())
    outer.addWidget(browser)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(d.accept)
    buttons.rejected.connect(d.reject)
    outer.addWidget(buttons)
    if d.exec() == QDialog.DialogCode.Accepted:
        app.data_undo = app.frame.copy(deep=True)
        app.use_frame(result)
        app.mark_dirty()


def advanced(app):
    from .advanced import recipe
    if app.frame is None:
        raise ValueError(app.t('no_data'))
    numeric_columns = list(app.frame.select_dtypes(include='number').columns)
    if not numeric_columns:
        raise ValueError('No numeric columns / Aucune colonne numérique')
    options = choose(app,tr(app,'Advanced statistics','Statistiques avancées'),[
        ('method',tr(app,'Method','Méthode'),[(tr(app,e,f),v) for e,f,v in [
            ('Mean confidence intervals','Intervalles de confiance','ci'),('Multiple regression (last column = response)','Régression (dernière colonne = réponse)','regression'),
            ('One-sample t-test','Test t à un échantillon','one_t'),('Welch independent t-test','Test t de Welch indépendant','welch'),('Paired t-test','Test t apparié','paired'),
            ('One-way ANOVA (columns = groups)','ANOVA (colonnes = groupes)','anova'),('Shapiro normality (first column)','Normalité Shapiro (première colonne)','normality'),
            ('Standardized PCA','ACP standardisée','pca'),('K-means clustering','Classification K-means','cluster')]]),
        ('response',tr(app,'Regression response (other selected columns = predictors)','Réponse de régression (autres colonnes sélectionnées = prédicteurs)'),[(str(c),c) for c in numeric_columns]),
        ('confidence',tr(app,'Confidence (0–1)','Confiance (0–1)'),'.95'),('reference',tr(app,'Null mean','Moyenne sous H0'),'0'),('clusters',tr(app,'Clusters','Groupes'),'3')])
    if options:
        options['confidence'] = float(options['confidence'])
        options['reference'] = float(options['reference'])
        options['clusters'] = int(options['clusters'])
        method = options.pop('method')
        response = options.pop('response')
        columns = app.selected_columns()
        if method == 'regression':
            columns = [c for c in columns if c != response] + [response]
        if not 0 < options['confidence'] < 1 or options['clusters'] < 2:
            raise ValueError('Confidence must be between 0 and 1; clusters ≥ 2 / Confiance entre 0 et 1; groupes ≥ 2')
        app.add_cell(recipe(method,columns,app.language,**options))


def geo(app, preferred='reservoir'):
    from .advanced import geology_recipe
    if app.frame is None:
        raise ValueError(app.t('no_data'))
    cols = [(str(c),c) for c in app.frame.columns]
    options = choose(app,tr(app,'Geology analysis','Analyse géologique'),[
        ('method',tr(app,'Analysis','Analyse'), sorted([('Porosity–permeability / Porosité–perméabilité + RQI/FZI','reservoir'),('Depth profile / Profil de profondeur','depth'),('Correlation matrix / Matrice de corrélation','matrix')],key=lambda p:p[1]!=preferred)),
        ('first',tr(app,'Porosity / profile value','Porosité / valeur du profil'),cols),
        ('second',tr(app,'Permeability (mD) / depth','Perméabilité (mD) / profondeur'),cols),
        ('percent',tr(app,'Porosity unit','Unité de porosité'),[('%',True),('Fraction (0–1)',False)]),
        ('thresholds',tr(app,'Class thresholds (mD, separated by ;)','Seuils de classes (mD, séparés par ;)'),'1;10;100;1000')])
    if options:
        method = options['method']
        columns = app.selected_columns() if method == 'matrix' else [options['first'],options['second']]
        if len(set(columns)) != len(columns):
            raise ValueError('Choose distinct columns / Choisissez des colonnes distinctes')
        app.add_cell(geology_recipe(method,columns,percent=options['percent'],thresholds=tuple(float(x) for x in options['thresholds'].split(';'))))


def chart_options(app):
    values = choose(app,tr(app,'Chart appearance','Apparence du graphique'),[
        ('title',tr(app,'Title (empty = automatic)','Titre (vide = automatique)'),app.chart_options.get('title','')),
        ('xlabel','X',app.chart_options.get('xlabel','')),('ylabel','Y',app.chart_options.get('ylabel','')),
        ('color',tr(app,'Color (#RRGGBB)','Couleur (#RRGGBB)'),app.chart_options.get('color','#20945f')),
        ('bins',tr(app,'Histogram bins','Classes histogramme'),app.chart_options.get('bins',15)),
        ('xscale',tr(app,'X scale','Échelle X'),sorted([('Linear / Linéaire','linear'),('Log','log')],key=lambda p:p[1]!=app.chart_options.get('xscale','linear'))),
        ('yscale',tr(app,'Y scale','Échelle Y'),sorted([('Linear / Linéaire','linear'),('Log','log')],key=lambda p:p[1]!=app.chart_options.get('yscale','linear')))])
    if values:
        from matplotlib.colors import is_color_like
        if not is_color_like(values['color']) or not 1 <= int(values['bins']) <= 200:
            raise ValueError('Invalid color or bins (1–200) / Couleur ou classes invalides')
        values['bins'] = int(values['bins'])
        app.chart_options = values
        app.mark_dirty()


def project_save(app, path=None, set_current=True):
    from .projects import save_project
    if app.data_sync_error:
        raise ValueError('Resolve the notebook DataSyncError before saving / Corrigez DataSyncError avant de sauvegarder')
    if path is None:
        path,_ = QFileDialog.getSaveFileName(app,'STC project',app.project_path or 'STC_Project.stcproj','STC (*.stcproj)')
    if not path:
        return False
    if not path.lower().endswith('.stcproj'):
        path += '.stcproj'
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(c.editor.toPlainText(),outputs=c.outputs,execution_count=c.execution_count,metadata={'stc_executed_source':c.executed_source}) for c in app.cells])
    settings={'chart':app.chart_options,'language':app.language,'metrics':app.stats_metrics,'ddof':app.stats_ddof,'percentiles':app.stats_percentiles,'columns':app.selected_columns(),'report':app.report_plan}
    if hasattr(app,'_update_recovery'):
        settings['_update_recovery']=app._update_recovery
    save_project(path, app.frame,notebook,settings)
    if set_current:
        app.project_path = path
        app.dirty = False
    app.statusBar().showMessage(app.t('saved')+': '+path)
    return True


def project_open(app, path=None, restore_recovery=False):
    from .projects import load_project
    if path is None:
        path,_ = QFileDialog.getOpenFileName(app,'STC project','','STC (*.stcproj)')
    if not path:
        return
    frame,notebook,settings = load_project(path)
    if app.dirty and not app.confirm_save():
        return
    app.session.close()
    for cell in list(app.cells):
        app.remove_cell(cell)
    app.frame = None
    app.file_path = None
    if frame is not None:
        app.use_frame(frame)
    else:
        from .app import FrameModel
        app.table.setModel(FrameModel(pd.DataFrame()))
        app.table.hide()
        app.welcome.show()
        app.column_list.clear()
        for label in app.metric_values:
            label.setText('0')
        app.update_info()
    for entry in notebook.cells:
        if entry.cell_type == 'code':
            cell = app.add_cell(entry.source)
            cell.outputs = entry.outputs
            cell.executed_source = entry.metadata.get('stc_executed_source')
            cell.execution_count = entry.execution_count
            # Strip arbitrary saved HTML, retain only sanitized tables and local PNG output.
            from .reports import TableParser
            for output in cell.outputs:
                data = output.get('data',{})
                if 'text/html' in data:
                    parser = TableParser()
                    parser.feed(data['text/html'])
                    data['text/html'] = ''.join('<table>'+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</table>' for rows in parser.tables)
            cell.render()
            if any('image/png' in o.get('data',{}) for o in cell.outputs):
                cell.chart_button.show()
    app.chart_options = settings.get('chart',{})
    app.report_plan = settings.get('report',[])
    app.stats_metrics = settings.get('metrics',list(range(16)))
    app.stats_ddof = settings.get('ddof',1)
    app.stats_percentiles = settings.get('percentiles',[])
    for i in range(app.column_list.count()):
        item = app.column_list.item(i)
        item.setCheckState(Qt.CheckState.Checked if item.data(Qt.ItemDataRole.UserRole) in settings.get('columns',[]) else Qt.CheckState.Unchecked)
    app.project_path, app.file_path = path,None
    app.data_undo = None
    app.data_pending = frame is not None
    app.data_sync_error = False
    app.language_picker.setCurrentIndex(1 if settings.get('language')=='fr' else 0)
    app.dirty = False
    app.navigate('data')
    if restore_recovery and settings.get('_update_recovery'):
        state=settings['_update_recovery']
        app.project_path=state.get('project_path')
        app.file_path=state.get('file_path')
        app.dirty=bool(state.get('dirty'))
        for cell,position in zip(app.cells,state.get('cursors',[])):
            cursor=cell.editor.textCursor()
            cursor.setPosition(min(int(position),len(cell.editor.toPlainText())))
            cell.editor.setTextCursor(cursor)
        for checkbox,value in zip((app.report_tables,app.report_graphs,app.report_text,app.report_code),state.get('report_flags',[])):
            checkbox.setChecked(bool(value))
        if state.get('page')=='charts':
            for cell in reversed(app.cells):
                if any('image/png' in o.get('data',{}) for o in cell.outputs):
                    app.show_cell_charts(cell)
                    break
        if state.get('page') in app.nav_buttons:
            app.navigate(state['page'])
        app.update_info()


def report_builder(app):
    from .reports import collect_results
    items = collect_results(app.cells,tables=app.report_tables.isChecked(),graphs=app.report_graphs.isChecked(),text=app.report_text.isChecked(),code=app.report_code.isChecked(),language=app.language)
    d, outer, form = dialog(app,tr(app,'Build your report','Composer le rapport'))
    listing = QListWidget()
    listing.setDragDropMode(QListWidget.DragDropMode.InternalMove)
    for i,item in enumerate(items):
        row = QListWidgetItem(item['title']+' · '+item['kind'])
        row.setData(Qt.ItemDataRole.UserRole,i)
        row.setFlags(row.flags()|Qt.ItemFlag.ItemIsUserCheckable)
        previous = app.report_plan[0] if app.report_plan else {}
        row.setCheckState(Qt.CheckState.Checked if not previous or i in previous.get('indices',[]) else Qt.CheckState.Unchecked)
        listing.addItem(row)
    previous = app.report_plan[0] if app.report_plan else {}
    if previous.get('signature') == report_signature(items):
        order = previous.get('indices',[]) + [i for i in range(len(items)) if i not in previous.get('indices',[])]
        rows = {}
        while listing.count():
            row = listing.takeItem(0)
            rows[row.data(Qt.ItemDataRole.UserRole)] = row
        for i in order:
            if i in rows:
                listing.addItem(rows[i])
    outer.addWidget(listing)
    item_comment = QPlainTextEdit()
    item_comment.setMaximumHeight(70)
    item_comment.setPlaceholderText(tr(app,'Comment on the selected result','Commentaire sur le résultat sélectionné'))
    annotations = dict(previous.get('annotations',{}))
    active = [None]
    def change_comment(current, old):
        if active[0] is not None:
            annotations[str(active[0])] = item_comment.toPlainText()
        active[0] = current.data(Qt.ItemDataRole.UserRole) if current else None
        item_comment.setPlainText(annotations.get(str(active[0]),''))
    listing.currentItemChanged.connect(change_comment)
    outer.addWidget(item_comment)
    comment = QPlainTextEdit()
    comment.setPlaceholderText(tr(app,'Report introduction / comments','Introduction / commentaires du rapport'))
    comment.setMaximumHeight(90)
    if app.report_plan and 'intro' in app.report_plan[0]:
        comment.setPlainText(app.report_plan[0]['intro'])
    outer.addWidget(comment)
    preview = QTextBrowser()
    outer.addWidget(preview)
    def selection():
        return [listing.item(i).data(Qt.ItemDataRole.UserRole) for i in range(listing.count()) if listing.item(i).checkState()==Qt.CheckState.Checked]
    def show():
        change_comment(listing.currentItem(),listing.currentItem())
        parts = ['<p>'+html.escape(comment.toPlainText())+'</p>']
        for i in selection():
            item=items[i]
            parts.append('<h3>'+html.escape(item['title'])+'</h3>')
            if item['kind']=='table':
                parts.append('<table border="1">'+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row)+'</tr>' for row in item['rows'])+'</table>')
            elif item['kind']=='image':
                parts.append('<img width="560" src="data:image/png;base64,'+base64.b64encode(item['png']).decode()+'">')
            else:
                parts.append('<pre>'+html.escape(item['text'])+'</pre>')
            if annotations.get(str(i)):
                parts.append('<p>'+html.escape(annotations[str(i)])+'</p>')
        preview.setHtml(''.join(parts))
    button=Button(tr(app,'Preview selected results','Aperçu des résultats sélectionnés'))
    button.clicked.connect(show)
    outer.addWidget(button)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(d.accept)
    buttons.rejected.connect(d.reject)
    outer.addWidget(buttons)
    if d.exec()==QDialog.DialogCode.Accepted:
        change_comment(listing.currentItem(),listing.currentItem())
        app.report_plan=[{'intro':comment.toPlainText(),'indices':selection(),'signature':report_signature(items),'annotations':annotations}]
        app.mark_dirty()


def install(app):
    app.chart_options, app.report_plan = {}, []
    app.project_path, app.data_undo = None,None
    from .pages import PAGE_KEYS, card
    from .i18n import TEXT
    for lang in ('en','fr'):
        TEXT[lang].update({'projects':'Projects' if lang=='en' else 'Projets','projects_description':'Save and reopen complete workspaces.' if lang=='en' else 'Enregistrer et rouvrir des espaces de travail complets.',
                           'geology':'Geology' if lang=='en' else 'Géologie','geology_description':'Reservoir properties, depth profiles and correlations.' if lang=='en' else 'Propriétés du réservoir, profils et corrélations.'})
    def add(layout,en,fr,callback):
        button=Button()
        key='extension_'+str(len(app.bound_labels))
        TEXT['en'][key],TEXT['fr'][key]=en,fr
        app.bound_labels.append((button,key))
        button.clicked.connect(lambda:guard(app,callback))
        layout.addWidget(button)
    data_layout=app.pages.widget(0).layout()
    row=QHBoxLayout()
    add(row,'Clean selected columns…','Nettoyer les colonnes sélectionnées…',lambda:clean(app))
    def undo():
        if app.data_undo is not None:
            previous=app.frame.copy(deep=True)
            app.use_frame(app.data_undo)
            app.data_undo=previous
            app.mark_dirty()
    add(row,'Undo / redo data change','Annuler / rétablir la modification',undo)
    data_layout.insertLayout(0,row)
    # Existing pages stay in their established order; added pages have dedicated navigation.
    for key in ('projects','geology'):
        frame,layout=card()
        if key=='projects':
            text_key='project_intro'
            TEXT['en'][text_key]='Keep your dataset, code, results and report choices together. Save a project before closing, then reopen it to continue. Ctrl+S saves the complete workspace. Code is never executed when opening a project.'
            TEXT['fr'][text_key]='Conservez ensemble vos données, code, résultats et choix de rapport. Enregistrez un projet avant de fermer, puis rouvrez-le pour continuer. Ctrl+S enregistre tout l’espace de travail. Aucun code ne s’exécute à l’ouverture.'
            layout.addWidget(app.label(text_key,wrap=True))
            add(layout,'Save complete project…','Enregistrer le projet complet…',lambda:project_save(app))
            add(layout,'Open project…','Ouvrir un projet…',lambda:project_open(app))
        else:
            text_key='geology_intro'
            TEXT['en'][text_key]='Porosity–permeability | RQI / FZI | Depth profiles | Correlation matrix\n\nAssign columns and units in the analysis dialog. Generated Python remains editable. Permeability classes use editable screening thresholds; validate them for your reservoir.'
            TEXT['fr'][text_key]='Porosité–perméabilité | RQI / FZI | Profils de profondeur | Matrice de corrélation\n\nAttribuez les colonnes et unités dans le dialogue. Le code Python reste modifiable. Les classes de perméabilité utilisent des seuils indicatifs modifiables; validez-les pour votre réservoir.'
            layout.addWidget(app.label(text_key,wrap=True))
            grid=QGridLayout()
            for i,(en,fr,en_help,fr_help,method) in enumerate([
                ('Porosity–permeability','Porosité–perméabilité','Crossplot with logarithmic permeability and explicit porosity units.','Diagramme croisé avec perméabilité logarithmique et unités explicites.','reservoir'),
                ('Depth profiles','Profils de profondeur','Plot a property along depth; depth increases downward.','Tracer une propriété selon la profondeur, croissante vers le bas.','depth'),
                ('Correlation matrix','Matrice de corrélation','Compare selected numeric properties in an annotated heatmap.','Comparer les propriétés numériques sélectionnées dans une carte annotée.','matrix'),
                ('Reservoir classification','Classification du réservoir','RQI / FZI and editable permeability screening classes.','RQI / FZI et classes indicatives de perméabilité modifiables.','reservoir')]):
                feature,feature_layout=card()
                heading_key='geo_heading_'+str(i)
                help_key='geo_help_'+str(i)
                TEXT['en'][heading_key],TEXT['fr'][heading_key]=en,fr
                TEXT['en'][help_key],TEXT['fr'][help_key]=en_help,fr_help
                heading=app.label(heading_key)
                heading.setObjectName('cardTitle')
                heading.setWordWrap(True)
                feature_layout.addWidget(heading)
                feature_layout.addWidget(app.label(help_key,wrap=True))
                add(feature_layout,'Configure…','Configurer…',lambda m=method:geo(app,m))
                grid.addWidget(feature,i//2,i%2)
            layout.addLayout(grid)
        layout.addStretch()
        app.pages.addWidget(frame)
        button=Button()
        button.setObjectName('navigation')
        button.setCheckable(True)
        button.setMinimumHeight(38)
        button.clicked.connect(lambda checked=False,k=key:app.navigate(k))
        app.nav_layout.addWidget(button)
        app.nav_buttons[key]=button
    # Place actions in the corresponding content cards; the shared selector moves freely.
    analysis_content=app.pages.widget(1).layout().itemAt(1).widget().widget().layout()
    add(analysis_content,'Advanced statistics…','Statistiques avancées…',lambda:advanced(app))
    analysis_content.insertWidget(0,analysis_content.takeAt(analysis_content.count()-1).widget())
    charts_content=app.chart_stack.widget(0).layout().itemAt(1).widget().widget().layout()
    add(charts_content,'Chart appearance…','Apparence du graphique…',lambda:chart_options(app))
    charts_content.insertWidget(0,charts_content.takeAt(charts_content.count()-1).widget())
    exports=app.pages.widget(4).widget().layout()
    add(exports,'Build and preview report…','Composer et prévisualiser le rapport…',lambda:report_builder(app))
    exports.insertWidget(1,exports.takeAt(exports.count()-1).widget())
    for key in ('projects','data','analysis','charts','geology','notebook','exports','updates'):
        button=app.nav_buttons[key]
        app.nav_layout.removeWidget(button)
        button.setMinimumHeight(34)
        app.nav_layout.addWidget(button)
    app.nav_layout.setSpacing(4)


def report_signature(items):
    import hashlib
    return hashlib.sha256(repr(items).encode('utf-8')).hexdigest()
