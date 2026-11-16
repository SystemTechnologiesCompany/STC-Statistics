"""Customer activation screen. The workbench is created only after verification."""
from PySide6.QtCore import Qt,QThread,Signal,QTimer,QSettings,QUrl
from PySide6.QtGui import QPixmap,QIcon,QDesktopServices
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QCheckBox,QProgressBar,QFrame,QScrollArea
from .theme import GlassBackground,GlassButton,GlassComboBox
from .licensing import LicenseClient,LicenseError,CONTACT_URL

COPY={
 'en':{
  'title':'Activate STC Statistics','intro':'Your data. Your results. Your Python.',
  'heading':'Enter your STC UNIC CODE',
  'description':'Enter the code STC gave you after your purchase to unlock your statistics workspace.',
  'code':'STC UNIC CODE','show':'Show code','activate':'Activate app','retry':'Verify my activation',
  'purchase':'Get your code · Contact STC on LinkedIn ↗',
  'help':'Need a code? Open our official LinkedIn page and contact System Technologies Company (STC) to purchase a license. We will give you your personal STC UNIC CODE.',
  'seat':'One license activates one PC and one Windows account. Keep your code private. Changing your PC? Contact STC to transfer your license.',
  'online':'An internet connection is required when you open the app. Your datasets and notebook content are not sent to the licensing service.',
  'checking':'Verifying your license…','activating':'Activating your workspace…',
  'ready':'Your workspace is ready to activate.','invalid':'Check your code and try again.',
  'STC-L100':'Enter your STC UNIC CODE to get started.',
  'STC-L101':'This code could not be verified. Check it or contact STC.',
  'STC-L102':'This license is already assigned to another PC or Windows account. Contact STC for help.',
  'STC-L103':'This license is not active. Contact STC to renew or restore access.',
  'STC-L104':'We could not reach the activation service. Try again later or contact STC.',
  'STC-L105':'Your saved activation could not be verified on this Windows account. Enter your code again or contact STC.',
  'STC-L106':'Please wait a minute before trying again.',
  'STC-L107':'Your activation could not be saved. Try again or contact STC.',
  'STC-L108':'Your activation could not be verified securely. Try again or contact STC.',
 },
 'fr':{
  'title':'Activer STC Statistics','intro':'Vos données. Vos résultats. Votre Python.',
  'heading':'Saisissez votre STC UNIC CODE',
  'description':"Saisissez le code remis par STC après votre achat pour accéder à votre espace de statistiques.",
  'code':'STC UNIC CODE','show':'Afficher le code','activate':"Activer l’application",'retry':'Vérifier mon activation',
  'purchase':'Obtenir votre code · Contacter STC sur LinkedIn ↗',
  'help':"Besoin d’un code ? Ouvrez notre page LinkedIn officielle et contactez System Technologies Company (STC) pour acheter une licence. Nous vous remettrons votre STC UNIC CODE personnel.",
  'seat':"Une licence active un PC et un compte Windows. Gardez votre code privé. Vous changez de PC ? Contactez STC pour transférer votre licence.",
  'online':"Une connexion Internet est nécessaire à l’ouverture de l’application. Vos données et le contenu de vos notebooks ne sont pas transmis au service de licences.",
  'checking':'Vérification de votre licence…','activating':'Activation de votre espace…',
  'ready':'Votre espace est prêt à être activé.','invalid':'Vérifiez votre code et réessayez.',
  'STC-L100':'Saisissez votre STC UNIC CODE pour commencer.',
  'STC-L101':'Ce code n’a pas pu être vérifié. Vérifiez-le ou contactez STC.',
  'STC-L102':'Cette licence est déjà associée à un autre PC ou compte Windows. Contactez STC.',
  'STC-L103':'Cette licence n’est pas active. Contactez STC pour renouveler ou rétablir votre accès.',
  'STC-L104':'Le service d’activation est indisponible. Réessayez plus tard ou contactez STC.',
  'STC-L105':'Votre activation enregistrée n’a pas pu être vérifiée sur ce compte Windows. Saisissez à nouveau votre code ou contactez STC.',
  'STC-L106':'Veuillez patienter une minute avant de réessayer.',
  'STC-L107':'Votre activation n’a pas pu être enregistrée. Réessayez ou contactez STC.',
  'STC-L108':'Votre activation n’a pas pu être vérifiée de manière sécurisée. Réessayez ou contactez STC.',
 }
}


class LicenseWorker(QThread):
    verified=Signal()
    denied=Signal(str)

    def __init__(self,code=None,client_factory=LicenseClient,parent=None):
        super().__init__(parent)
        self.code,self.factory=code,client_factory

    def run(self):
        try:
            client=self.factory()
            client.check() if self.code is None else client.activate(self.code)
        except LicenseError as exc:
            self.denied.emit(exc.code)
        except Exception:
            self.denied.emit('STC-L104')
        else:
            self.verified.emit()
        finally:
            self.code=None


class ActivationDialog(QDialog):
    def __init__(self,parent=None,client_factory=LicenseClient,auto_check=True):
        super().__init__(parent)
        self.client_factory=client_factory
        self.worker=None
        self.verified=False
        self.error_code='STC-L100'
        self.settings=QSettings('STC','Statistics')
        self.language=self.settings.value('language','en')
        if self.language not in COPY:
            self.language='en'
        from .pages import LOGO_PATH
        self.setWindowIcon(QIcon(str(LOGO_PATH)))
        self.resize(850,740)
        self.setMinimumSize(660,560)
        outer=QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        root=GlassBackground()
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(root)
        outer.addWidget(scroll)
        layout=QVBoxLayout(root)
        layout.setContentsMargins(36,28,36,28)
        layout.setSpacing(16)
        brand=QHBoxLayout()
        logo=QLabel()
        logo.setPixmap(QPixmap(str(LOGO_PATH)).scaled(58,64,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        brand.addWidget(logo)
        name=QLabel('STC STATISTICS')
        name.setStyleSheet('color:#51e4ac;font-size:17px;letter-spacing:3px;')
        brand.addWidget(name)
        brand.addStretch()
        self.languages=GlassComboBox()
        self.languages.addItem('English','en')
        self.languages.addItem('Français','fr')
        self.languages.setCurrentIndex(0 if self.language=='en' else 1)
        self.languages.currentIndexChanged.connect(self.change_language)
        brand.addWidget(self.languages)
        layout.addLayout(brand)
        self.title=QLabel()
        self.title.setStyleSheet('font-size:30px;font-weight:600;color:white;')
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        self.intro=QLabel()
        layout.addWidget(self.intro)
        card=QFrame()
        card.setObjectName('pageCard')
        content=QVBoxLayout(card)
        content.setContentsMargins(24,24,24,24)
        content.setSpacing(14)
        self.description=QLabel()
        self.description.setWordWrap(True)
        content.addWidget(self.description)
        self.code_label=QLabel()
        content.addWidget(self.code_label)
        self.code=QLineEdit()
        self.code.setMaxLength(64)
        self.code.setEchoMode(QLineEdit.EchoMode.Password)
        self.code.setPlaceholderText('STC-XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX')
        self.code.setMinimumHeight(46)
        self.code.setAccessibleName('STC UNIC CODE')
        self.code_label.setBuddy(self.code)
        self.code.returnPressed.connect(self.activate)
        content.addWidget(self.code)
        self.show_code=QCheckBox()
        self.show_code.toggled.connect(lambda visible:self.code.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password))
        content.addWidget(self.show_code)
        self.status=QLabel()
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(46)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content.addWidget(self.status)
        self.progress=QProgressBar()
        self.progress.setRange(0,0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(5)
        self.progress.hide()
        content.addWidget(self.progress)
        buttons=QHBoxLayout()
        self.activate_button=GlassButton('')
        self.activate_button.setObjectName('primary')
        self.activate_button.clicked.connect(self.activate)
        buttons.addWidget(self.activate_button)
        self.retry_button=GlassButton('')
        self.retry_button.clicked.connect(lambda:self.start_check())
        buttons.addWidget(self.retry_button)
        content.addLayout(buttons)
        layout.addWidget(card)
        self.help=QLabel()
        self.help.setWordWrap(True)
        layout.addWidget(self.help)
        self.contact=GlassButton('')
        self.contact.clicked.connect(lambda:QDesktopServices.openUrl(QUrl(CONTACT_URL)))
        layout.addWidget(self.contact)
        self.seat=QLabel()
        self.seat.setWordWrap(True)
        layout.addWidget(self.seat)
        self.online=QLabel()
        self.online.setWordWrap(True)
        self.online.setStyleSheet('color:#a2b8ae;font-size:12px;')
        layout.addWidget(self.online)
        layout.addStretch()
        self.retranslate()
        if auto_check:
            QTimer.singleShot(0,self.start_check)

    def change_language(self):
        self.language=self.languages.currentData()
        self.settings.setValue('language',self.language)
        self.retranslate()

    def retranslate(self):
        words=COPY[self.language]
        self.setWindowTitle(words['title'])
        for widget,key in ((self.title,'heading'),(self.intro,'intro'),(self.description,'description'),
                           (self.code_label,'code'),(self.show_code,'show'),(self.activate_button,'activate'),
                           (self.retry_button,'retry'),(self.contact,'purchase'),(self.help,'help'),
                           (self.seat,'seat'),(self.online,'online')):
            widget.setText(words[key])
        self.status.setText(words.get(self.error_code,words['STC-L104'])+
                            ('  ·  '+self.error_code if self.error_code.startswith('STC-L') and self.error_code!='STC-L100' else ''))

    def activate(self):
        import re
        code=self.code.text().strip().upper()
        if not re.fullmatch(r'STC-(?:[A-Z2-7]{8}-){3}[A-Z2-7]{8}',code):
            self.error_code='invalid'
            self.retranslate()
            return
        self.start_check(code)

    def start_check(self,code=None):
        if self.worker is not None:
            return
        self.error_code='checking' if code is None else 'activating'
        self.retranslate()
        self.activate_button.setEnabled(False)
        self.retry_button.setEnabled(False)
        self.code.setEnabled(False)
        self.progress.show()
        self.worker=LicenseWorker(code,self.client_factory,self)
        self.worker.verified.connect(self.on_verified)
        self.worker.denied.connect(self.on_denied)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_verified(self):
        self.verified=True
        self.code.clear()

    def on_denied(self,code):
        self.error_code=code if code in COPY['en'] else 'STC-L104'
        self.retranslate()

    def on_finished(self):
        worker=self.worker
        self.worker=None
        worker.deleteLater()
        self.progress.hide()
        self.activate_button.setEnabled(True)
        self.retry_button.setEnabled(True)
        self.code.setEnabled(True)
        if self.verified:
            self.accept()

    def accept(self):
        if self.verified and self.worker is None:
            super().accept()

    def reject(self):
        # Avoid destroying a running network thread; each request has a timeout.
        if self.worker is None:
            super().reject()


def authorize(parent=None):
    dialog=ActivationDialog(parent)
    return dialog.exec()==QDialog.DialogCode.Accepted and dialog.verified
