"""
Zoo for customized simple widgets
"""
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QLabel, QPushButton


class AcceptRejectDialog(QDialog):
    """
    Customized widget for user to accept or reject a state

    Refer to: https://www.mfitzp.com/tutorials/pyqt-dialogs/
    """

    def __init__(self, parent=None, title="", message=""):
        super(AcceptRejectDialog, self).__init__(parent)

        self.setWindowTitle(title)

        # Button box
        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel

        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        # Set layout
        self.layout = QVBoxLayout()
        message = QLabel(message)
        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

        # Flag to show (1) None: not Ok or Cancel (2) True: accepted (3) False: rejected
        self.m_status = None

    def accept(self):
        super(AcceptRejectDialog, self).accept()
        self.m_status = True

    def reject(self):
        super(AcceptRejectDialog, self).reject()
        self.m_status = False

    def is_accepted(self):
        return self.m_status
