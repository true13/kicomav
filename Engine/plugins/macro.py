# -*- coding:utf-8 -*-
# Made by Kei Choi(hanul93@gmail.com)

import os # 파일 삭제를 위해 import
import zlib
import hashlib
import struct, mmap
import kernel
import kavutil
import glob

# 매크로 타입
X95M = 1
X97M = 2

def IsPrint(char) :
    c = ord(char)
    if c > 0x20 and c < 0x80 :
        return True
    else :
        return False

def ExtractMacroData_X95M(data) :
    mac_data = None
    data_size = len(data)

    try :
        if data_size < 0x200 : raise SystemError
        if ord(data[0]) != 0x01 : raise SystemError

        mac_pos = struct.unpack('<L', data[10:10+4])[0]
        mac_pos += ( 14L + 14L )
        if data_size < mac_pos : raise SystemError

        t = struct.unpack('<L', data[mac_pos:mac_pos+4])[0]
        mac_pos += t + 28L + 18L - 14L;
        if data_size < mac_pos : raise SystemError

        mac_pos = struct.unpack('<L', data[mac_pos:mac_pos+4])[0]
        mac_pos += 0x3C
        if data_size < mac_pos : raise SystemError

        # 매크로 정보 위치까지 도착
        if ord(data[mac_pos]) != 0xFE or ord(data[mac_pos+1]) != 0xCA :
            raise SystemError

        # 매크로 소스 코드의 줄 수 얻기
        mac_lines = struct.unpack('<H', data[mac_pos+4:mac_pos+6])[0]
        if mac_lines == 0 : raise SystemError 

        mac_pos = mac_pos + 4L + (mac_lines * 12L)
        if data_size < mac_pos : raise SystemError
        
        mac_len = struct.unpack('<L', data[mac_pos+6:mac_pos+10])[0]
        mac_pos += 10

        # print 'ok :', hex(mac_pos), mac_lines, mac_len

        # 매크로 담긴 영역 추출
        if data_size < (mac_pos + mac_len) : raise SystemError
        mac_data = data[mac_pos:mac_pos + mac_len]

    except :
        pass

    return mac_data

def ExtractMacroData_X97M(data) :
    mac_data = None
    data_size = len(data)

    try :
        if data_size < 0x200 : raise SystemError
        if ord(data[0]) != 0x01 : raise SystemError # 매크로 아님

        if ord(data[9]) == 0x01 and ord(data[10]) == 0x01 :
            # 엑셀 97
            pass
        else :
            # 엑셀 2000 이상
            mac_pos = struct.unpack('<L', data[25:25+4])[0]
            mac_pos = (mac_pos - 1) + 0x3D

        if data_size < mac_pos : raise SystemError


        if ord(data[mac_pos]) != 0xFE or ord(data[mac_pos+1]) != 0xCA :
            raise SystemError

        mac_lines = struct.unpack('<H', data[mac_pos+4:mac_pos+6])[0]
        if mac_lines == 0 : raise SystemError 

        mac_pos = mac_pos + 6L + (mac_lines * 12L);
        if data_size < mac_pos : raise SystemError

        Len = struct.unpack('<L', data[mac_pos+6:mac_pos+10])[0]
        Off = mac_pos + 10

        '''
        print 'Macro off :', hex(Off)
        print 'Macro len :', Len

        fp = open('x97m.dmp', 'wb')
        fp.write(data[Off:Off+Len])
        fp.close()
        '''

        mac_data = data[Off:Off+Len]
    except :
        pass

    return mac_data


def GetMD5_X95M(data) :
    ret = None

    try :
        max = 0
        buf = ''

        for i in range(len(data)) :
            c = data[i]
            if IsPrint(c) :
                max += 1
            else :
                if max > 3 :
                    # print data[i-max:i] # 패턴 생성시 참조 (sigtool)
                    buf += data[i-max:i]
                max = 0

        md5 = hashlib.md5()
        md5.update(buf)
        fmd5 = md5.hexdigest().decode('hex')

        print '%s:%s:%s:' % (len(buf), md5.hexdigest(), len(data)) # 패턴 추출 (sigtool)
        ret = (len(buf), fmd5, len(data))
    except :
        import traceback
        print traceback.format_exc()
        pass

    return ret



#---------------------------------------------------------------------
# KavMain 클래스
# 키콤백신 엔진 모듈임을 나타내는 클래스이다.
# 이 클래스가 없으면 백신 엔진 커널 모듈에서 로딩하지 않는다.
#---------------------------------------------------------------------
class KavMain :
    #-----------------------------------------------------------------
    # init(self, plugins)
    # 백신 엔진 모듈의 초기화 작업을 수행한다.
    #-----------------------------------------------------------------
    def init(self, plugins) : # 백신 모듈 초기화
        try :
            self.plugins = plugins
            self.x95m_ptn   = []
            self.x95m_iptn  = {}
            self.x97m_ptn   = []
            self.x97m_iptn  = {}
            self.__signum__ = 0
            self.__date__   = 0
            self.__time__   = 0
            self.max_date   = 0

            if self.__LoadDB__(X95M) == 1 : raise SystemError
            if self.__LoadDB__(X97M) == 1 : raise SystemError

            return 0
        except :
            pass

            return 1

    def __LoadDB__(self, target_macro) : # 백신 모듈 초기화
        try :
            vdb = kavutil.VDB()

            if target_macro   == X95M : ptn_name = 'x95m'
            elif target_macro == X97M : ptn_name = 'x97m'

            flist = glob.glob(self.plugins + os.sep + ptn_name + '.c*')
            for i in range(len(flist)) :
                fname = flist[i]
                
                # 패턴 로딩
                ptn_data = vdb.Load(fname)
                if ptn_data == None : # 패턴 로딩 실패
                    return 1

                if target_macro   == X95M : self.x95m_ptn.append(ptn_data)
                elif target_macro == X97M : self.x97m_ptn.append(ptn_data)
            
                self.__signum__ += vdb.GetSigNum()

                # 최신 날짜 구하기
                t_d = vdb.GetDate()
                t_t = vdb.GetTime()

                t_date = (t_d << 16) + t_t
                if self.max_date < t_date :
                    self.__date__ = t_d
                    self.__time__ = t_t
                    self.max_date = t_date

            return 0
        except :
            import traceback
            print traceback.format_exc()

            return 1

    #-----------------------------------------------------------------
    # uninit(self)
    # 백신 엔진 모듈의 종료화 작업을 수행한다.
    #-----------------------------------------------------------------
    def uninit(self) : # 백신 모듈 종료화
        return 0
    
    #-----------------------------------------------------------------
    # scan(self, filehandle, filename)
    # 악성코드를 검사한다.
    # 인자값 : mmhandle         - 파일 mmap 핸들
    #        : scan_file_struct - 파일 구조체
    #        : format           - 미리 분석된 파일 포맷
    # 리턴값 : (악성코드 발견 여부, 악성코드 이름, 악성코드 ID) 등등
    #-----------------------------------------------------------------
    def scan(self, mmhandle, scan_file_struct, format) :
        ret = None
        scan_state = kernel.NOT_FOUND
        ret_value = {}
        ret_value['result']     = False # 바이러스 발견 여부
        ret_value['virus_name'] = ''    # 바이러스 이름
        ret_value['scan_state'] = kernel.NOT_FOUND # 0:없음, 1:감염, 2:의심, 3:경고
        ret_value['virus_id']   = -1    # 바이러스 ID

        try :
            section_name = scan_file_struct['deep_filename']
            data = mmhandle[:] # 파일 전체 내용

            # _VBA_PROJECT/xxxx 에 존재하는 스트림은 엑셀95 매크로가 존재한다.
            if section_name.find(r'_VBA_PROJECT/') != -1 :
                ret = self.__ScanVirus_X95M__(data)
            # _VBA_PROJECT_CUR/xxxx 에 존재하는 스트림은 엑셀97 매크로가 존재한다.
            elif section_name.find(r'_VBA_PROJECT_CUR/') != -1 :
                ret = self.__ScanVirus_X97M__(data)

            if ret != None :
                scan_state, s, i_num, i_list = ret

                # 바이러스 이름 조절
                if s[0:2] == 'V.' :
                    s = 'Virus.MSExcel.' + s[2:]
                elif s[0:2] == 'J.' :
                    s = 'Joke.MSExcel.' + s[2:]

                # 악성코드 패턴이 갖다면 결과 값을 리턴한다.
                ret_value['result']     = True # 바이러스 발견 여부
                ret_value['virus_name'] = s    # 바이러스 이름
                ret_value['scan_state'] = scan_state # 0:없음, 1:감염, 2:의심, 3:경고
                ret_value['virus_id']   = 0    # 바이러스 ID
                return ret_value            
        except :
            pass

        # 악성코드를 발견하지 못했음을 리턴한다.
        return ret_value

    def __ScanVirus_X95M__(self, data) :
        ret = None

        try :
            mac_data = ExtractMacroData_X95M(data)
            if mac_data == None : raise SystemError

            hash_data = GetMD5_X95M(mac_data)
            ret = self.__ScanVirus_XM_ExpendDB__(hash_data, X95M)
        except :
            pass

        return ret


    def __ScanVirus_X97M__(self, data) :
        ret = None

        try :
            mac_data = ExtractMacroData_X97M(data)
            if mac_data == None : raise SystemError

            hash_data = GetMD5_X95M(mac_data)
            ret = self.__ScanVirus_XM_ExpendDB__(hash_data, X97M)
        except :
            pass

        return ret

    def __ScanVirus_XM_ExpendDB__(self, hash_data, target_macro) :
        ret = None

        try :
            fsize    = hash_data[0] # md5를 생성한 버퍼의 크기
            fmd5     = hash_data[1] # md5
            mac_size = hash_data[2] # 실제 매크로 크기

            # 패턴 비교
            i_num = -1

            if   target_macro == X95M : xm_ptn = self.x95m_ptn
            elif target_macro == X97M : xm_ptn = self.x97m_ptn

            for i in range(len(xm_ptn)) :
                vpattern = xm_ptn[i]

                try :
                    t = vpattern[fsize] # 패턴 중에 파일 크기로 된 MD5가 존재하나?

                    # MD5의 6자리 내용이 일치하는지 조사
                    id = t[fmd5[0:6]]

                    # 나머지 10자리도 비교해야 함
                    i_num = id[0]   # x95m.iXX 파일에..
                    i_list = id[1]  # 몇번째 리스트인지 알게 됨
                except :
                    pass

                if i_num != -1 : # MD5 6자리와 일치하는 것을 발견 되었다면
                    try :
                        if target_macro == X95M :
                            e_vlist = self.x95m_iptn[i_num]
                        elif target_macro == X97M :
                            e_vlist = self.x97m_iptn[i_num]
                    except :
                        if target_macro == X95M :   ptn_name = 'x95m'
                        elif target_macro == X97M : ptn_name = 'x97m'
                        fname = '%s%s%s.i%02d' % (self.plugins, os.sep,ptn_name,  i_num)
                        vdb = kavutil.VDB() # 패턴 로딩
                        e_vlist = vdb.Load(fname)

                    if e_vlist != None :
                        if target_macro == X95M   : self.x95m_iptn[i_num] = e_vlist
                        elif target_macro == X97M : self.x97m_iptn[i_num] = e_vlist

                        p_md5_10 = e_vlist[i_list][0] # MD5 10자리
                        p_mac_size = int(e_vlist[i_list][1]) # 매크로 크기 
                        p_vname = e_vlist[i_list][2]  # 바이러스 이름

                        if (p_md5_10 == fmd5[6:]) and (p_mac_size == mac_size) : # 모두 일치
                            ret = (kernel.INFECTED, p_vname, i_num, i_list)
                        elif p_md5_10 == fmd5[6:] : # md5만 일치
                            s = p_vname + '.Gen'
                            ret = (kernel.SUSPECT, s, i_num, i_list)
        except :
            pass

        return ret
    #-----------------------------------------------------------------
    # disinfect(self, filename, malwareID)
    # 악성코드를 치료한다.
    # 인자값 : filename   - 파일 이름
    #        : malwareID  - 치료할 악성코드 ID
    # 리턴값 : 악성코드 치료 여부
    #-----------------------------------------------------------------
    def disinfect(self, filename, malwareID) : # 악성코드 치료
        try :
            '''
            # 악성코드 진단 결과에서 받은 ID 값이 0인가?
            if malwareID == 0 : 
                os.remove(filename) # 파일 삭제
                return True # 치료 완료 리턴
            '''
        except :
            pass

        return False # 치료 실패 리턴

    #-----------------------------------------------------------------
    # listvirus(self)
    # 진단/치료 가능한 악성코드의 목록을 알려준다.
    #-----------------------------------------------------------------
    def listvirus(self) : # 진단 가능한 악성코드 목록
        vlist = [] # 리스트형 변수 선언
        vlist.append('Virus.MSExcel.Laroux.A') 
        return vlist

    #-----------------------------------------------------------------
    # getinfo(self)
    # 백신 엔진 모듈의 주요 정보를 알려준다. (버전, 제작자...)
    #-----------------------------------------------------------------
    def getinfo(self) :
        info = {} # 사전형 변수 선언
        info['author'] = 'Kei Choi' # 제작자
        info['version'] = '1.0'     # 버전
        info['title'] = 'Macro Engine' # 엔진 설명
        info['kmd_name'] = 'macro' # 엔진 파일명

        # 패턴 생성날짜와 시간은 없다면 빌드 시간으로 자동 설정
        info['date']    = self.__date__   # 패턴 생성 날짜 
        info['time']    = self.__time__   # 패턴 생성 시간 
        info['sig_num'] = self.__signum__ # 패턴 수
        return info

