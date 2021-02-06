import sys

from kiwoom.kiwoom import Kiwoom
from PyQt5.QtWidgets import *

class Ui_class():
    def __init__(self):
        print('UI 클라스입니다.')

        self.app = QApplication(sys.argv) #변수 초기화

        self.kiwoom = Kiwoom()

        self.app.exec_() #스케줄러