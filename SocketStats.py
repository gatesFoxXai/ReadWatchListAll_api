import time
import asyncio
import argparse
import threading
import sys
import select
from enum import Enum


class EnumLoginStatusType(Enum):
    DEFAULT = 0
    LOGIN_FAILE = 1
    CONNECT_LOGIN = 3
    LOGIN_SUCCESS = 4
    REQ_WatchlistAll = 10
    ACK_WatchlistAll = 11
    REQ_FiveTickA = 12
    ACK_FiveTickA = 13
    REQ_Watchlist = 14
    ACK_Watchlist = 15
    REQ_StockTick = 16
    ACK_StockTick = 17
    REQ_SUBSCRIBE_ADD = 18
    ACK_SUBSCRIBE_ADD = 19
    RELOGIN = 50
    LOGOUT = 100


class SocketState:
    _instance = None
    _exit_flag = False
    MaxRound = 20

    def __init__(self, name, SocketType):        
        self.status = False
        self.latest_timestamp = None
        self.latest_timeREQ_WatchlistAll = None
        self.value = 0
        self.name = name
        self.SocketType = SocketType
        print(f'__init__ {SocketType} {name}')
        self._lock = threading.Lock()


    def AckStatus(self,name,SocketType):
        #收到 REQ name 回應 ack SocketType
        if(self.name == name):
            self.name = SocketType.name
            self.SocketType = SocketType
            self.value = SocketType.value
            self.status = True
        return status
    
    def  isAckStatus(self,name):
        if(self.name == name):
            return true

    def setAckStatus(SocketType):
        self.name = SocketType.name
        self.SocketType = SocketType
        self.SocketType = SocketType.value
        self.status = True
        return status

    def SocketState(name, SocketType):
        return self.SharePtr(name, SocketType)

    def SocketState(SocketType):
        return self.SharePtr(SocketType.name, SocketType)

    def _req_states(name, SocketType):
        return self.SharePtr(name, SocketType)

    def _req_states(SocketType):
        return self.SharePtr(SocketType.name, SocketType)    

    @classmethod
    def SharePtr(cls, name, SocketType):
        if cls._instance is None:
            cls._instance = cls(name, SocketType)            
        return cls._instance



    def RqState(self, SocketType, name=None):
        #避免重複相同命令請求
        if(name == None):
            name = self.SocketType.name
        if((self.SocketType.value == SocketType.value) and (name == name)):
            self.latest_timestamp = time.time()
            self.increment()
            self.status = True       

        return self.status

    def reset_roundCountGr1(self):
        elapsed = time.time() - self.latest_timeREQ_WatchlistAll
        print(f'reset_round: elapsed={elapsed:.3f}s')
        with self._lock: 
            self.value = EnumLoginStatusType.REQ_FiveTickA.value
            self.SocketType = EnumLoginStatusType.REQ_FiveTickA
            return self.value

    def reset_round(self):        
        with self._lock:
            if self.latest_timeREQ_WatchlistAll is not None:
                elapsed = time.time() - self.latest_timeREQ_WatchlistAll
                print(f'reset_round: elapsed={elapsed:.3f}s')
                if elapsed < 1.0:
                    print('不到1秒，跳過REQ_WatchlistAll')
                    #還沒登入成功
                    if(self.value > self.ACK_SUBSCRIBE_ADD ):
                        self.value = EnumLoginStatusType.REQ_FiveTickA.value
                        self.SocketType = EnumLoginStatusType.REQ_FiveTickA
                    return self.value
            elif(self.value > self.ACK_SUBSCRIBE_ADD):
                    self.value = EnumLoginStatusType.REQ_FiveTickA.value
                    self.SocketType = EnumLoginStatusType.REQ_FiveTickA
                    safe.name = "REQ_FiveTickA"        
            return self.value 

    def increment(self,isLogin=True):
        round_num = self.value
        if not isLogin:
            return round_num
        with self._lock:            
            if(round_num <=EnumLoginStatusType.REQ_SUBSCRIBE_ADD.value and round_num>=EnumLoginStatusType.REQ_WatchlistAll.value):
                self.value += 1                
                self.SocketType.value = self.value
            else:
                self.value = EnumLoginStatusType.REQ_FiveTickA.value
                self.SocketType = EnumLoginStatusType.REQ_FiveTickA
                self.name = "REQ_FiveTickA"
            round_num = self.value    
            return round_num
                 
            

    
    def get_round(self,isLogin=True):
        round_num = self.value 
        if round_num < EnumLoginStatusType.REQ_WatchlistAll.value:
            round_num = EnumLoginStatusType.REQ_WatchlistAll.value
        elif round_num > EEnumLoginStatusType.ACK_SUBSCRIBE_ADD:
            if isLogin:
                self.reset_round()
        else:
            pass

        print(f'round_num = {round_num} value:{self.value}') 
        return round_num


async def _ack_async():
    await asyncio.sleep(0.01)
    ptr = SocketState.SharePtr("CONNECT_LOGIN", EnumLoginStatusType.CONNECT_LOGIN)
    print(f'[_ack_async] 啟動 name={ptr.name} type={ptr.SocketType}')
    
    isLogin = True
    while isLogin and not SocketState._exit_flag:
        await asyncio.sleep(1/60)
        
        # 檢查 Q 鍵
        if sys.platform == 'win32':
            import msvcrt
            if msvcrt.kbhit():
                key = msvcrt.getch().decode('utf-8', errors='ignore').upper()
                if key == 'Q':
                    print('收到Q鍵')
                    SocketState._exit_flag = True
                    break
        
        # 根據目前狀態處理
        if ptr.name == "LOGIN_SUCCESS":
            current_type = ptr.SocketType
            
            if current_type == EnumLoginStatusType.REQ_WatchlistAll:
                print('wait REQ_WatchlistAll')
                ptr.latest_timeREQ_WatchlistAll = time.time()
                
            elif current_type == EnumLoginStatusType.ACK_WatchlistAll:
                print('>> 收到 ACK_WatchlistAll，推進')
                ptr.increment()
                #需要處理融資卷時,才需要循環,否則開盤後只需一次成功,取得漲跌停資料開盤資前料
                
            elif current_type == EnumLoginStatusType.ACK_FiveTickA:
                print('>> 收到ACK_FiveTickA，推進')
                ptr.increment()
                
            elif current_type == EnumLoginStatusType.ACK_Watchlist:
                print('>> 收到ACK_Watchlist，推進')
                ptr.increment()
                
            elif current_type == EnumLoginStatusType.ACK_StockTick:
                print('>> 收到ACK_StockTick，推進')
                ptr.increment()
                
            elif current_type > EnumLoginStatusType.ACK_SUBSCRIBE_ADD:
                print('>> 收到ACK_SUBSCRIBE_ADD，reset')
                ptr.reset_round()


def workerRec(name):
    print(f'[{threading.current_thread().name}] 啟動')
    ptr = SocketState.SharePtr("CONNECT_LOGIN", EnumLoginStatusType.CONNECT_LOGIN)
    
    if ptr.name == "CONNECT_LOGIN":
        ptr.AckStatus(EnumLoginStatusType.LOGIN_SUCCESS,"LOGIN_SUCCESS") 
    
    print(f'[workerRec] 開始監聽')
    
    while not SocketState._exit_flag:
        time.sleep(0.05)
        
        # 回應對應的 ACK
        if ptr.SocketType == EnumLoginStatusType.REQ_WatchlistAll:
            
            print(f'wait[workerRec] 回應ACK_WatchlistAll')
        elif ptr.SocketType == EnumLoginStatusType.REQ_FiveTickA:
           
            print(f'wait[workerRec] 回應ACK_FiveTickA')
        elif ptr.SocketType == EnumLoginStatusType.REQ_Watchlist:
            
            print(f'wait[workerRec] 回應ACK_Watchlist')
        elif ptr.SocketType == EnumLoginStatusType.REQ_StockTick:
            
            print(f'wait[workerRec] 回應ACK_StockTick')
        elif ptr.SocketType == EnumLoginStatusType.REQ_SUBSCRIBE_ADD:
            
            print(f'wait[workerRec] 回應ACK_SUBSCRIBE_ADD')
    
    print(f'[workerRec] 結束')


# def main():
#     import time
#     parser = argparse.ArgumentParser(description="Socket test")
#     parser.add_argument("--reset", action="store_True", help="重置單例")
#     args = parser.parse_args()
    
#     if args.reset:
#         SocketState._instance = None
#         print("單例已重置")
    
#     client = SocketState.SharePtr("CONNECT_LOGIN", EnumLoginStatusType.CONNECT_LOGIN)
#     print(f'client: {client}')
    
#     result = client.RqState(EnumLoginStatusType.CONNECT_LOGIN, "CONNECT_LOGIN")
#     print(f'RqState: {result}')
    
#     if result:
#         print("===== 登入成功 =====")
        
#         # 設定初始狀態
#         client.name = "LOGIN_SUCCESS"
#         client.SocketType = EnumLoginStatusType.REQ_WatchlistAll
#         client.latest_timeREQ_WatchlistAll = time.time()
        
#         # 啟動執行緒
#         t1 = threading.Thread(target=workerRec, args=("Thread-rec",))
#         t1.start()
        
#         t2 = threading.Thread(target=lambda: asyncio.run(_ack_async()))
#         t2.start()
#     else:
#         print("===== 登入中 =====")
#         asyncio.run(_ack_async())
    
#     time.sleep(0.3)
#     print("主執行緒: 按Q退出...")
    
#     while not SocketState._exit_flag:
#         if sys.platform == 'win32':
#             import msvcrt
#             if msvcrt.kbhit():
#                 key = msvcrt.getch().decode('utf-8', errors='ignore').upper()
#                 if key == 'Q':
#                     SocketState._exit_flag = True
#                     print("主執行緒收到Q鍵")
#                     break
#         time.sleep(0.1)
    
#     if t1.is_alive():
#         t1.join()
#     if t2.is_alive():
#         t2.join()
    
#     print("===== 程式結束 =====")


#if __name__ == "__main__":
#    main()
