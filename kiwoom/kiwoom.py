import os
import pandas as pd

from PyQt5.QAxContainer import *
from PyQt5.QtCore import *
from PyQt5.QtTest import *
from config.errorCode import *
from config.kiwoomType import *


class Kiwoom(QAxWidget):
    def __init__(self):
        super().__init__()

        print('키움 클래스입니다.')

        self.realType = RealType()

        #event loop 모음
        self.login_event_loop = None
        self.detail_account_info_event_loop = QEventLoop()
        self.calculator_event_loop = QEventLoop()

       #screen 번호 모음
        self.screen_my_info = '2000'
        self.screen_calculation_stock = '4000'
        self.screen_real_stock = '5000' #종목별 할당한 스크린 번호
        self.screen_order_stock = '6000' #종목별 할당할 주문용 스크린 번호
        self.screen_start_stop_real = '1000'

        #변수 모음
        self.account_num = None
        self.account_stock_dict = {} #보유종목
        self.not_account_stock_dict = {} #미체결종목
        self.portfolio_stock_dict = {}
        self.jango_dict = {} #잔고

        #계좌관련 변수
        self.use_money = 0
        self.use_money_percent = 0.5

        #종목 분석용
        self.calcul_data = []


        #실행
        self.get_ocx_instance()
        self.event_slots()
        self.real_event_slots()

        self.signal_login_commConnect()
        self.get_account_info()
        self.detail_account_info() #예수금 가져오기
        self.detail_account_mystock() #계좌평가 잔고내역 요청
        self.not_concluded_account() #미체결종목 요청
        # self.calculator_fnc() #일봉 차트 조회

        self.read_code() # 저장된 종목들 불러오기ㅣ
        self.screen_number_setting() #스크린 번호 할당

        #최초 받을때만 마지막 0으로 받고, 나머지는 1로 받아야 초기화 안됨
        self.dynamicCall('SetRealReg(QString, QString, QSTring, QString)', self.screen_start_stop_real, '', self.realType.REALTYPE['장시작시간']['장운영구분'], '0') #장 열려있는지 체크

        #portfolio_stock_dict: read_code를 통해 생성된 현재 포트폴리오
        for code in self.portfolio_stock_dict.keys():
            screen_num = self.portfolio_stock_dict[code]['스크린 번호']
            fids = self.realType.REALTYPE['주식체결']['체결시간']

            self.dynamicCall('SetRealReg(QString, QString, QSTring, QString)', screen_num, code, fids, '1')
            print(f'실시간 등록 코드 : {code}, 번호 : {fids}, 스크린 번호 : {screen_num}')
    #Kiwoom API 제어
    def get_ocx_instance(self):
        self.setControl('KHOPENAPI.KHOpenAPICtrl.1')

    #로그인
    def event_slots(self):
        self.OnEventConnect.connect(self.login_slot)
        self.OnReceiveTrData.connect(self.trdata_slot)
        self.OnReceiveMsg.connect(self.msg_slot)

    def real_event_slots(self):
        self.OnReceiveRealData.connect(self.realdata_slot)
        self.OnReceiveChejanData.connect(self.chejan_slot)
    def login_slot(self, errCode):
        print(errors(errCode))
        self.login_event_loop.exit()

    def signal_login_commConnect(self):
        self.dynamicCall('CommConnect()')

        self.login_event_loop = QEventLoop()
        self.login_event_loop.exec_() #로그인이 될 때까지 실행

    #계좌정보 가져오기
    def get_account_info(self):
        account_list = self.dynamicCall('GetLoginInfo(String)', 'ACCNO')
        self.account_num = account_list[:-1]#계좌번호 8158061411
        print(f'나의 계좌 번호 : {self.account_num}')

    #예수금 가져오기
    def detail_account_info(self):
        print('예수금 요청하는 부분')

        #요청
        self.dynamicCall('SetInputValue(String, String)', '계좌번호', self.account_num)
        self.dynamicCall('SetInputValue(String, String)', '비밀번호', '0000')
        self.dynamicCall('SetInputValue(String, String)', '비밀번호입력매체구분', '00')
        self.dynamicCall('SetInputValue(String, String)', '조회구분', '2')
        #네번째: Screen Number. 그룹을 만들어서 한 스크린번호에 총 100개까지 요청 가능
        #스크린 번호의 목적: Tr요청이 아니라, 종목에 대한 주가를 받으려면, 받고싶다고 등록을 해야
        self.dynamicCall('CommRqData(String, String, int, String)', '예수금상세현황요청', 'opw00001', '0', self.screen_my_info)

        self.detail_account_info_event_loop = QEventLoop()
        self.detail_account_info_event_loop.exec_()

    def detail_account_mystock(self, sPrevNext = '0'):
        print('계좌평가잔고내역 요청')
        # 요청
        self.dynamicCall('SetInputValue(String, String)', '계좌번호', self.account_num)
        self.dynamicCall('SetInputValue(String, String)', '비밀번호', '0000')
        self.dynamicCall('SetInputValue(String, String)', '비밀번호입력매체구분', '00')
        self.dynamicCall('SetInputValue(String, String)', '조회구분', '2')
        self.dynamicCall('CommRqData(String, String, int, String)', '계좌평가잔고내역요청', 'opw00018', sPrevNext, self.screen_my_info)

        self.detail_account_info_event_loop.exec_()

    #미체결
    def not_concluded_account(self, sPrevNext = '0'):
        print('미체결종목 요청')
        self.dynamicCall('SetInputValue(QString, QString)', '계좌번호', self.account_num)
        self.dynamicCall('SetInputValue(QString, QString)', '체결구분', '1')
        self.dynamicCall('SetInputValue(QString, QString)', '매매구분', '2')
        self.dynamicCall('CommRqData(QString, QString, int, QString)', '실시간미체결요청', 'opt10075', sPrevNext,
                         self.screen_my_info)
        self.detail_account_info_event_loop.exec_()

    def trdata_slot(self, sScrNo, sRQName, sTrCode, sRecordName,  sPrevNext):
        '''
        tr 요청을 받는 구역
        :param sScrNo: 스크린번호
        :param sRQName: 요청할 때 지은 이름
        :param sTrCode: 요청 id, tr 코드
        :param sRecordName: 사용안함
        :param sPrevNext: 다음 페이지가 있는지(종목 20개 넘어갈때)
        :return:
        '''

        if sRQName == '예수금상세현황요청':
            deposit = self.dynamicCall('GetCommData(String, String, int, String)', sTrCode, sRQName, 0, '예수금')
            if deposit == '':
                print('예수금 불러오기 실패')
            else:
                print(f'예수금 {int(deposit)}')

                #사용금액 설정
                self.use_money = int(deposit) * self.use_money_percent
                self.use_money = self.use_money / 4

            ok_deposit = self.dynamicCall('GetCommData(String, String, int, String)', sTrCode, sRQName, 0, '출금가능금액')
            if ok_deposit == '':
                print('출금 가능 금액 불러오기 실패')
            else:
                print(f'출금 가능 금액 {int(ok_deposit)}')

            self.detail_account_info_event_loop.exit()

        elif sRQName == '계좌평가잔고내역요청':
            total_buy_money = self.dynamicCall('GetCommData(String, String, int, String)', sTrCode, sRQName, 0, '총매입금액')
            total_buy_money_result = int(total_buy_money)

            print(f'총매입금액 : {total_buy_money_result}')

            total_profit_loss_rate = self.dynamicCall('GetCommData(String, String, int, String)', sTrCode, sRQName, 0,'총수익률(%)')
            total_profit_loss_rate_result = float(total_profit_loss_rate)
            print(f'총수익률(%) : {total_profit_loss_rate_result}')

            #보유종목이 있을 경우
            rows = self.dynamicCall('GetRepeatCnt(QString, QString)', sTrCode, sRQName)
            cnt = 0

            for i in range(rows):
                code = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, cnt, '종목번호')
                code = code.strip()[1:] #공백제거
                code_nm = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '종목명')
                stock_quantity = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '보유수량')
                buy_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '매입가')
                learn_rate = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '수익률(%)')
                current_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '현재가')
                total_change_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '매입금액')
                possible_quantity = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '매매가능수량')

                if code in self.account_stock_dict:
                    pass
                else:
                    self.account_stock_dict.update({code:{}})

                code_nm = code_nm.strip()
                stock_quantity = int(stock_quantity.strip())
                buy_price = int(buy_price.strip())
                learn_rate = float(learn_rate.strip())
                current_price = int(current_price.strip())
                total_change_price = int(total_change_price.strip())
                possible_quantity = int(possible_quantity.strip())

                self.account_stock_dict[code].update({'종목명' : code_nm})
                self.account_stock_dict[code].update({'보유수량': stock_quantity})
                self.account_stock_dict[code].update({'매입가': buy_price})
                self.account_stock_dict[code].update({'수익률(%)': learn_rate})
                self.account_stock_dict[code].update({'현재가': current_price})
                self.account_stock_dict[code].update({'매입금액': total_change_price})
                self.account_stock_dict[code].update({'매매가능수량': possible_quantity})

                cnt += 1
            print(f'계좌에 가지고 있는 종목 : {self.account_stock_dict}')
            print(f'계좌에 보유종목 카운트 : {cnt}')

            #20종목 넘어서 다음 페이지 있으면
            if sPrevNext == '2':
                self.detail_account_mystock(sPrevNext='2')
            else:
                self.detail_account_info_event_loop.exit()

        elif sRQName == '실시간미체결요청':
            #종목들 가져오기
            rows = self.dynamicCall('GetRepeatCnt(QString, QString)', sTrCode, sRQName)


            for i in range(rows):
                code = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '종목코드')
                code_nm = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '종목명')
                order_no = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '주문번호')
                order_quantity = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '주문수량')
                order_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '주문가격')
                order_gubun = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '주문구분')
                not_quantity = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '미체결수량')
                ok_quantity = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '체결량')

                code = code.strip() #공백제거
                code_nm = code_nm.strip()
                order_no = int(order_no.strip())
                order_status = order_status.strip()
                order_quantity = int(order_quantity.strip())
                order_price = int(order_price.strip())
                order_gubun = order_gubun.strip().lstrip('+').lstrip('-')
                not_quantity = int(not_quantity.strip())
                ok_quantity = int(ok_quantity.strip())

                if order_no in self.not_account_stock_dict:
                    pass
                else:
                    self.not_account_stock_dict[order_no].update({'종목코드' : code})
                    self.not_account_stock_dict[order_no].update({'종목명': code_nm})
                    self.not_account_stock_dict[order_no].update({'주문번호': order_no})
                    self.not_account_stock_dict[order_no].update({'주문상태': order_status})
                    self.not_account_stock_dict[order_no].update({'주문수량': order_quantity})
                    self.not_account_stock_dict[order_no].update({'주문가격': order_price})
                    self.not_account_stock_dict[order_no].update({'주문구분': order_gubun})
                    self.not_account_stock_dict[order_no].update({'미체결수량': not_quantity})
                    self.not_account_stock_dict[order_no].update({'체결량': ok_quantity})

                    print(f'미체결 종목 : {self.not_account_stock_dict[order_no]}')
            self.detail_account_info_event_loop.exit()

        if sRQName == '주식일봉차트조회':
            code = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, 0, '종목코드')
            code = code.strip()
            print(f'일봉 데이터 요청 :  {code}')

            cnt = self.dynamicCall('GetRepeatCnt (QString, QString)', sTrCode, sRQName)
            print(f'데이터 일수 : {cnt}')

            #한번 조회하면 600일치까지 가져올 수 있다.
            for i in range(cnt):
                data = []

                current_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '현재가')
                volume = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '거래량')
                trading_value = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i,'거래대금')
                date = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '일자')
                start_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '시가')
                high_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i,'고가')
                low_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i,'저가')
                close_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i,'종가')

                data.append('') #GetCommDataEx라는 함수와 형식 맞춰주기 위해
                data.append(current_price.strip())
                data.append(volume.strip())
                data.append(trading_value.strip())
                data.append(date.strip())
                data.append(start_price.strip())
                data.append(high_price.strip())
                data.append(low_price.strip())
                data.append(close_price.strip())
                data.append('')

                self.calcul_data.append(data.copy())


            if sPrevNext == '2':
                self.day_kiwoom_db(code = code, sPrevNext = sPrevNext)
            else:
                '''
                --------------
                로직 들어가는 부분
                --------------
                '''
                print(f'총 일수 {len(self.calcul_data)}')
                pass_success = False
                if self.calcul_data == None or len(self.calcul_data) < 120:
                    pass_success = False
                else:
                    total_price = 0
                    for value in self.calcul_data[:120]:
                        total_price += int(value[1])

                    moving_average_price = total_price / 120

                    bottom_stock_price= False
                    check_price = None
                    if int(self.calcul_data[0][7]) <= moving_average_price and moving_average_price <= int(self.calcul_data[0][6]):
                        print('오늘 주가 120이평선에 걸쳐있는 것 확인')
                        bottom_stock_price = True
                        check_price = int(self.calcul_data[0][6])


                    #과거 일봉들이 120일 이평선보다 밑에 있는지 확인
                    #그렇게 확인하다가 일봉이 120일 이평선보다 위에 있으면 계산 진행
                    prev_price = None #과거의 일봉 저가
                    if bottom_stock_price == True:
                        moving_average_price = 0
                        price_top_moving = False

                        idx = 1
                        while True:
                            if len(self.calcul_data[idx:]) < 120:
                                print('120일치가 없음!')
                                break
                            total_price = 0
                            for value in self.calcul_data[idx:120+idx]:
                                total_price += int(value[1])
                            moving_average_price_prev = total_price / 120

                            if moving_average_price_prev <= int(self.calcul_data[idx][6]) and idx <= 20:
                                print('20일 동안 주가가 120일 이평선과 같거나 위에 있으면 조건 통과 못함')
                                price_top_moving = False
                                break

                            elif int(self.calcul_data[idx][7]) > moving_average_price_prev and idx > 20:
                                print('120일 이평선 위에 있는 일봉 확인됨')
                                price_top_moving = True
                                prev_price = int(self.calcul_data[idx][7])
                                break
                            idx += 1

                        #g해당 부분 이평선이 가장 최근 일자의 이평선 가격보다 낮은지 확인
                        if price_top_moving == True:
                            if moving_average_price > moving_average_price_prev and check_price > prev_price:
                                print('포착된 이평선의 가격이 오늘자(최근일자) 이평선 가격보다 낮은 것 확인됨')
                                print('포착된 부분의 일봉 저가가 오늘자 일봉의 고가보다 낮은지 확인됨')
                                pass_success = True
                if pass_success == True:
                    print('조건부 통과')

                    code_nm = self.dynamicCall('GetMasterCodeName(QString', code)
                    f = open('C:/Users/Lenovo/OneDrive - SNU/Quantry/quantryDB/kiwoom_data/condition_stock.txt', 'a', encoding= 'utf-8')
                    f.write(f'{code}\t{code_nm}\t{str(self.calcul_data[0][1])}\n')
                    f.close()
                else:
                    print('조건부 통과 못함')

                self.calcul_data.clear()
                self.calculator_event_loop.exit()
    #종목 코드들 가져오기
    def get_code_list_by_market(self, market_code):
        '''
        :param market_code: 시장코드
        :return:
        '''
        code_list= self.dynamicCall('GetCodeListByMarket(QString)', market_code)
        code_list = code_list.split(';')[:-1]
        return code_list

    def calculator_fnc(self):
        code_list = self.get_code_list_by_market('10')
        print(f'코스닥 개수 {len(code_list)}')

        for idx, code in enumerate(code_list):
            self.dynamicCall('DisconnectRealData(QString)', self.screen_calculation_stock)#스크린 번호를 요청하면 그룹이 만들어지고, 쌓이면 안돼서 불필요한건 끊어줘야한다.
            print(f'{idx + 1} / {len(code_list)} : KOSDAQ Stock Code : {code} is updating...')
            self.day_kiwoom_db(code = code)
    def day_kiwoom_db(self, code = None, date = None, sPrevNext = '0'):

        QTest.qWait(3600) #3.6초마다 딜레이

        self.dynamicCall('SetInputValue(QString, QString)', '종목코드', code)
        self.dynamicCall('SetInputValue(QString, QString)', '수정주가구분', '1')

        if date != None:

            self.dynamicCall('SetInputValue(QString, QString)', '기준일자', date)

        self.dynamicCall('CommRqData(QString,QString, int, QString)', '주식일봉차트조회', 'opt10081', sPrevNext, self.screen_calculation_stock)

        self.calculator_event_loop.exec_()

    def read_code(self):
        if os.path.exists('kiwoom_data/condition_stock.txt'):
            f = open('kiwoom_data/condition_stock.txt', 'r', encoding = 'utf8')

            lines = f.readlines()
            for line in lines:
                if line != '':
                    # ls = line.split('\t')
                    ls = line.split(' ')

                    stock_code = ls[0]
                    stock_name = ls[1]
                    stock_price = abs(int(ls[2].split('\n')[0])) #하락이면 -가 붙어나오기 때문

                    self.portfolio_stock_dict.update({stock_code : {'종목명' : stock_name, '현재가' : stock_price}})
            f.close()

        elif os.path.exists('C:/Users/Lenovo/OneDrive - SNU/Quantry/quantryDB/TradingView/StrongBuy/StrongBuy20210203.csv'):
            df = pd.read_csv('C:/Users/Lenovo/OneDrive - SNU/Quantry/quantryDB/TradingView/StrongBuy/StrongBuy20210203.csv')
            for row in df.values:
                stock_name = row[0]
                stock_code = row[1]
                stock_price = 10000

                self.portfolio_stock_dict[stock_code] = {'종목명' : stock_name, '현재가' : stock_price}

        print(self.portfolio_stock_dict)

    def screen_number_setting(self):
        screen_overwrite = []

        #계좌평가잔고내역에 있는 종목들
        for code in self.account_stock_dict.keys():
            if code not in screen_overwrite:
                screen_overwrite.append(code)

        #미체결에 있는 종목들
        for order_number in self.not_account_stock_dict.keys():
            code = self.account_stock_dict[order_number]['종목코드']

            if code not in screen_overwrite:
                screen_overwrite.append(code)

        #포트폴리오 종목
        for code in self.portfolio_stock_dict.keys():
            if code not in screen_overwrite:
                screen_overwrite.append(code)

        cnt = 0
        for code in screen_overwrite:
            temp_screen = int(self.screen_real_stock)
            order_screen = int(self.screen_order_stock)

            #screen 번호 하나에 종목 100개까지 가능(여기서는 일단 50)
            if (cnt % 50) == 0:
                temp_screen += 1 #screen 번호 하나 당 종목 코드 50개씩 할당
                self.screen_real_stock = str(temp_screen)

                order_screen += 1
                self.screen_order_stock = str(order_screen)

            if code in self.portfolio_stock_dict.keys():
                self.portfolio_stock_dict[code].update({'스크린 번호' : str(self.screen_real_stock)})
                self.portfolio_stock_dict[code].update({'주문용 스크린 번호' : str(self.screen_order_stock)})

            else:
                self.portfolio_stock_dict.update({code : {'스크린 번호': str(self.screen_real_stock), '주문용 스크린 번호': str(self.screen_order_stock)}})

            cnt += 1
        print(self.portfolio_stock_dict)

    def realdata_slot(self, sCode, sRealType, sRealData):
        print(f'check!!!! {sRealType}')
        if sRealType == '장시작시간':
            fid = self.realType.REALTYPE[sRealType]['장운영구분']
            value = self.dynamicCall('GetCommRealData(QString, int)', sCode, fid)

            if value == 0:
                print('장 시작 전')
            elif value == '3':
                print('장 시작')
            elif value == '2':
                print('장 종료, 동시호가로 넘어감')
            elif value == '4':
                print('3시 30분 장 종료')

                for code in self.portfolio_stock_dict.keys():
                     self.dynamicCall('SetRealRemove(QString, QString)', self.portfolio_stock_dict[sCode]['스크린번호'],sCode)
                QTest.qWait(5000)

                self.file_delete()
                self.calculator_fnc()

        elif sRealType == '주식체결':
            a = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['체결시간'])  # 출력 HHMMSS
            b = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['현재가'])  # 출력 : +(-)2520
            b = abs(int(b))
            c = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['전일대비'])  # 출력 : +(-)2520
            c = abs(int(c))
            d = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['등락율'])  # 출력 : +(-)12.98
            d = float(d)
            e = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['(최우선)매도호가'])  # 출력 : +(-)2520
            e = abs(int(e))
            f = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['(최우선)매수호가'])  # 출력 : +(-)2515
            f = abs(int(f))
            g = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['거래량'])  # 출력 : +240124 매수일때, -2034 매도일 때
            g = abs(int(g))
            h = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['누적거래량'])  # 출력 : 240124
            h = abs(int(h))
            i = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['고가'])  # 출력 : +(-)2530
            i = abs(int(i))
            j = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['시가'])  # 출력 : +(-)2530
            j = abs(int(j))
            k = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['저가'])  # 출력 : +(-)2530
            k = abs(int(k))

            self.portfolio_stock_dict[sCode].update({"체결시간": a})
            self.portfolio_stock_dict[sCode].update({"현재가": b})
            self.portfolio_stock_dict[sCode].update({"전일대비": c})
            self.portfolio_stock_dict[sCode].update({"등락율": d})
            self.portfolio_stock_dict[sCode].update({"(최우선)매도호가": e})
            self.portfolio_stock_dict[sCode].update({"(최우선)매수호가": f})
            self.portfolio_stock_dict[sCode].update({"거래량": g})
            self.portfolio_stock_dict[sCode].update({"누적거래량": h})
            self.portfolio_stock_dict[sCode].update({"고가": i})
            self.portfolio_stock_dict[sCode].update({"시가": j})
            self.portfolio_stock_dict[sCode].update({"저가": k})

            print(self.portfolio_stock_dict)

            #계좌잔고평가내역에 있고 오늘 산 잔고에는 없을 경우 -> 신규 매도
            if sCode in self.account_stock_dict.keys() and sCode not in self.jango_dict.keys():
                # print(f'신규 매도를 한다 {sCode}')

                asd = self.account_stock_dict[sCode]

                #b: 현재가
                meme_rate = (b - asd['매입가']) / asd['매입가'] * 100 #매매율

                #신규매도
                if asd['매매가능수량'] > 0 and (meme_rate > 5 or meme_rate < -5):
                    '''
                     SendOrderCredit(
                      BSTR sRQName,   // 사용자 구분명
                      BSTR sScreenNo,   // 화면번호 
                      BSTR sAccNo,    // 계좌번호 10자리 
                      LONG nOrderType,    // 주문유형 1:신규매수, 2:신규매도 3:매수취소, 4:매도취소, 5:매수정정, 6:매도정정
                      BSTR sCode,   // 종목코드
                      LONG nQty,    // 주문수량
                      LONG nPrice,    // 주문가격
                      BSTR sHogaGb,   // 거래구분(혹은 호가구분)은 아래 참고
                      BSTR sCreditGb, // 신용거래구분
                      BSTR sLoanDate,   // 대출일
                      BSTR sOrgOrderNo    // 원주문번호
                      )
                    '''
                    order_success = self.dynamicCall('SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)',
                                     ['신규매도', self.portfolio_stock_dict[sCode]['주문용스크린번호'], self.account_num, 2,
                                     sCode,  asd['매매가능수량'], 0, self.realType.SENDTYPE['거래구분']['시장가'], ''])

                    if order_success == 0:
                        print('매도주문 전달 성공')
                        del self.account_stock_dict[sCode]
                    else:
                        print('매도주문 전달 실패')
            #오늘 산 잔고에 있을 경우
            elif sCode in self.jango_dict.keys():
                jd = self.jango_dict[sCode]
                meme_rate = (b - jd['매입단가']) / jd['매입단가'] * 100

                if jd['주문가능수량'] > 0 and (meme_rate > 5 or meme_rate < -5):
                    order_success = self.dynamicCall(
                        "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                        ["신규매도", self.portfolio_stock_dict[sCode]["주문용스크린번호"], self.account_num, 2, sCode, jd['주문가능수량'],
                         0, self.realType.SENDTYPE['거래구분']['시장가'], ""]
                    )

                    if order_success == 0:
                        self.logging.logger.debug("매도주문 전달 성공")
                    else:
                        self.logging.logger.debug("매도주문 전달 실패")

                print(f'신규 매도를 한다 2 {sCode}')

            #등락률이 2% 이상이고, 오늘 산 잔고에 없을 경우
            elif d > 2.0 and sCode not in self.jango_dict:
                print(f'매수조건 통과 {sCode}')

                result = (self.use_money * 0.1) / e
                quantity = int(result)

                order_success = self.dynamicCall(
                    "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                    ["신규매수", self.portfolio_stock_dict[sCode]["주문용스크린번호"], self.account_num, 1, sCode, quantity, e,
                     self.realType.SENDTYPE['거래구분']['지정가'], ""]
                )

                if order_success == 0:
                    print('매수주문 전달 성공')
                    # self.logging.logger.debug("매수주문 전달 성공")
                else:
                    print('매수주문 전달 실패')
                    # self.logging.logger.debug("매수주문 전달 실패")

            #갑자기 추가됐을 때를 대비해서
            not_sell_list = list(self.not_account_stock_dict)
            for order_num in not_sell_list:
                code = self.not_account_stock_dict[order_num]['종목코드']
                trade_price = self.not_account_stock_dict[order_num]['주문가격']
                not_quantity = self.not_account_stock_dict[order_num]['미체결수량']
                order_gubun = self.not_account_stock_dictp[order_num]['주문구분']

                if order_gubun == '매수' and not_quantity > 0 and e > trade_price:
                    order_success = self.dynamicCall(
                        "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                        ["매수취소", self.portfolio_stock_dict[sCode]["주문용스크린번호"], self.account_num, 3, code, 0, 0,
                         self.realType.SENDTYPE['거래구분']['지정가'], order_num]
                    )

                    if order_success == 0:
                        print('매수취소 전달 성공')
                        # self.logging.logger.debug("매수취소 전달 성공")
                    else:
                        print('매수취소 전달 실패')
                        # self.logging.logger.debug("매수취소 전달 실패")
                elif not_quantity == 0:
                    del self.not_account_stock_dict[order_num]

    def chejan_slot(self, sGubun, nItemCnt, sFIdList):

        #주문체결
        if int(sGubun) == 0:
            account_num = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['계좌번호'])
            sCode = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['종목코드'])[1:]
            stock_name = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['종목명'])
            stock_name = stock_name.strip()

            origin_order_number = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['원주문번호'])  # 출력 : defaluse : "000000"
            order_number = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['주문번호'])  # 출럭: 0115061 마지막 주문번호
            order_status = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['주문상태'])  # 출력: 접수, 확인, 체결
            order_quan = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['주문수량'])  # 출력 : 3
            order_quan = int(order_quan)

            order_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['주문가격'])  # 출력: 21000
            order_price = int(order_price)

            not_chegual_quan = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['미체결수량'])  # 출력: 15, default: 0
            not_chegual_quan = int(not_chegual_quan)

            order_gubun = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['주문구분'])  # 출력: -매도, +매수
            order_gubun = order_gubun.strip().lstrip('+').lstrip('-')

            chegual_time_str = self.dynamicCall("GetChejanData(int)",self.realType.REALTYPE['주문체결']['주문/체결시간'])  # 출력: '151028'

            chegual_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['체결가'])  # 출력: 2110 default : ''
            if chegual_price == '':
                chegual_price = 0
            else:
                chegual_price = int(chegual_price)

            chegual_quantity = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['체결량'])  # 출력: 5 default : ''
            if chegual_quantity == '':
                chegual_quantity = 0
            else:
                chegual_quantity = int(chegual_quantity)

            current_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['현재가'])  # 출력: -6000
            current_price = abs(int(current_price))

            first_sell_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['(최우선)매도호가'])  # 출력: -6010
            first_sell_price = abs(int(first_sell_price))

            first_buy_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['(최우선)매수호가'])  # 출력: -6000
            first_buy_price = abs(int(first_buy_price))

            ######## 새로 들어온 주문이면 주문번호 할당
            if order_number not in self.not_account_stock_dict.keys():
                self.not_account_stock_dict.update({order_number: {}})

            self.not_account_stock_dict[order_number].update({"종목코드": sCode})
            self.not_account_stock_dict[order_number].update({"주문번호": order_number})
            self.not_account_stock_dict[order_number].update({"종목명": stock_name})
            self.not_account_stock_dict[order_number].update({"주문상태": order_status})
            self.not_account_stock_dict[order_number].update({"주문수량": order_quan})
            self.not_account_stock_dict[order_number].update({"주문가격": order_price})
            self.not_account_stock_dict[order_number].update({"미체결수량": not_chegual_quan})
            self.not_account_stock_dict[order_number].update({"원주문번호": origin_order_number})
            self.not_account_stock_dict[order_number].update({"주문구분": order_gubun})
            self.not_account_stock_dict[order_number].update({"주문/체결시간": chegual_time_str})
            self.not_account_stock_dict[order_number].update({"체결가": chegual_price})
            self.not_account_stock_dict[order_number].update({"체결량": chegual_quantity})
            self.not_account_stock_dict[order_number].update({"현재가": current_price})
            self.not_account_stock_dict[order_number].update({"(최우선)매도호가": first_sell_price})
            self.not_account_stock_dict[order_number].update({"(최우선)매수호가": first_buy_price})

            print(self.not_account_stock_dict)
        #체결되면 output이 1. 잔고 가져오는 과정
        elif int(sGubun) == 1:
            account_num = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['계좌번호'])
            sCode = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['종목코드'])[1:]

            stock_name = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['종목명'])
            stock_name = stock_name.strip()

            current_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['현재가'])
            current_price = abs(int(current_price))

            stock_quan = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['보유수량'])
            stock_quan = int(stock_quan)

            like_quan = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['주문가능수량'])
            like_quan = int(like_quan)

            buy_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['매입단가'])
            buy_price = abs(int(buy_price))

            total_buy_price = self.dynamicCall("GetChejanData(int)",
                                               self.realType.REALTYPE['잔고']['총매입가'])  # 계좌에 있는 종목의 총매입가
            total_buy_price = int(total_buy_price)

            meme_gubun = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['매도매수구분'])
            meme_gubun = self.realType.REALTYPE['매도수구분'][meme_gubun]

            first_sell_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['(최우선)매도호가'])
            first_sell_price = abs(int(first_sell_price))

            first_buy_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['(최우선)매수호가'])
            first_buy_price = abs(int(first_buy_price))

            if sCode not in self.jango_dict.keys():
                self.jango_dict.update({sCode: {}})

            self.jango_dict[sCode].update({"현재가": current_price})
            self.jango_dict[sCode].update({"종목코드": sCode})
            self.jango_dict[sCode].update({"종목명": stock_name})
            self.jango_dict[sCode].update({"보유수량": stock_quan})
            self.jango_dict[sCode].update({"주문가능수량": like_quan})
            self.jango_dict[sCode].update({"매입단가": buy_price})
            self.jango_dict[sCode].update({"총매입가": total_buy_price})
            self.jango_dict[sCode].update({"매도매수구분": meme_gubun})
            self.jango_dict[sCode].update({"(최우선)매도호가": first_sell_price})
            self.jango_dict[sCode].update({"(최우선)매수호가": first_buy_price})

            if stock_quan == 0:
                del self.jango_dict[sCode]
                self.dynamicCall('SetRealRemove(QString, QString)', self.portfolio_stock_dict[sCode]['스크린번호'], sCode)

    #송수신 메시지 get
    def msg_slot(self, sScrNo, sRQName, sTrCode, msg):

        print(f'스크린 : {sScrNo}, 요청이름: {sRQName}, tr코드: {sTrCode} --- {msg}')

    #매일 파일 업데이트
    def file_delete(self):
        if os.path.isfile('files/condition_stock.txt'):
            os.remove('files/condition_stock.txt')
