import os
import subprocess
import tempfile
import chardet
from pathlib import Path
import logging
import time
import sys
import requests
import platform
from config import DOCUMENTS_PATH, logger, HWP_SERVER_URL
import fitz  # PyMuPDF

# Windows 전용 모듈 import
if platform.system() == 'Windows':
    import win32com.client
    import pythoncom

class DocumentProcessor:
    def __init__(self, documents_path=DOCUMENTS_PATH):
        self.documents_path = documents_path
        os.makedirs(documents_path, exist_ok=True)
        
        # Windows 서버 URL 설정
        self.hwp_server_url = HWP_SERVER_URL or "http://192.168.0.2:8000"
        
        # Windows 서버 연결 상태 확인
        self.windows_server_available = self._check_windows_server()
        if not self.windows_server_available:
            logger.error("Windows HWP 서버에 연결할 수 없습니다. HWP 파일 처리가 불가능합니다.")
        
        # Windows 환경에서만 한글 프로그램 설치 확인
        self.has_hwp = False
        if platform.system() == 'Windows':
            self.has_hwp = self._check_hwp_installation()
            if not self.has_hwp:
                logger.warning("한글(HWP) 프로그램이 설치되어 있지 않거나 COM 등록이 되어있지 않습니다.")
    
    def _check_windows_server(self):
        """Windows HWP 서버 연결 상태 확인"""
        try:
            response = requests.get(f"{self.hwp_server_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Windows HWP 서버 연결 실패: {e}")
            return False
    
    def _check_hwp_installation(self):
        """한글 프로그램 설치 여부 및 COM 객체 등록 확인 (Windows 전용)"""
        if platform.system() != 'Windows':
            return False
            
        try:
            pythoncom.CoInitialize()
            try:
                hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
                hwp.Quit()
                pythoncom.CoUninitialize()
                logger.info("한글(HWP) 프로그램 확인 완료")
                return True
            except Exception as e:
                logger.error(f"한글(HWP) 프로그램 확인 실패: {e}")
                pythoncom.CoUninitialize()
                return False
        except Exception as e:
            logger.error(f"COM 초기화 실패: {e}")
            return False
    
    def _extract_text_file(self, hwp_file_path, output_format="TEXT"):
        """HWP 파일에서 SaveAs 메서드를 사용하여 텍스트 추출"""
        try:
            pythoncom.CoInitialize()
            hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
            
            # 경로가 Path 객체인 경우 문자열로 변환
            hwp_file_path = str(hwp_file_path) if isinstance(hwp_file_path, Path) else hwp_file_path
            # 절대 경로로 변환
            hwp_file_path = os.path.abspath(hwp_file_path)
            
            # 임시 텍스트 파일 경로 생성
            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
                txt_file_path = tmp.name
            
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModuleEx")
            # 파일 오픈
            hwp.Open(hwp_file_path)
            
            # 텍스트로 저장
            hwp.SaveAs(txt_file_path, "TEXT")
            hwp.Quit()
            pythoncom.CoUninitialize()
            
            # 텍스트 파일 읽기
            with open(txt_file_path, 'rb') as f:
                raw_data = f.read()
                detected = chardet.detect(raw_data)
                encoding = detected['encoding'] if detected['encoding'] else 'utf-8'
            
            with open(txt_file_path, 'r', encoding=encoding, errors='replace') as f:
                text = f.read()
            
            # 임시 파일 삭제
            os.unlink(txt_file_path)
            return text
        except Exception as e:
            logger.error(f"SaveAs 방식으로 텍스트 추출 실패: {e}")
            try:
                pythoncom.CoUninitialize()
            except:
                pass
            return ""
        
    def process_hwp_with_win32(self, file_path):
        """pywin32 COM 자동화를 사용하여 HWP 파일 처리"""
        if not self.has_hwp:
            logger.warning("한글 프로그램이 설치되어 있지 않아 Win32 방식으로 처리할 수 없습니다.")
            return self._fallback_hwp_processing(file_path)
            
        try:
            # COM 초기화 추가
            pythoncom.CoInitialize()
            
            # 경로가 Path 객체인 경우 문자열로 변환
            if isinstance(file_path, Path):
                file_path = str(file_path)
                
            # 절대 경로로 변환
            file_path = os.path.abspath(file_path)
            logger.info(f"Win32로 HWP 처리 중, 절대 경로: {file_path}")
            
            # 방법 1: GetTextFile 사용    
            try:
                hwp = win32com.client.gencache.EnsureDispatch("HWPFrame.HwpObject")
                hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModuleEx")
                hwp.Open(file_path)
                time.sleep(0.5)  # 한글 로딩 시간 확보
                text = hwp.GetTextFile("TEXT", "")
                hwp.Quit()
                
                if text and len(text.strip()) > 0:
                    # COM 해제
                    pythoncom.CoUninitialize()
                    return text
            except Exception as e:
                logger.error(f"GetTextFile 방식 실패: {e}")
            
            # 방법 2: SaveAs 방식 시도
            try:
                pythoncom.CoUninitialize()  # 이전 COM 해제
                text = self._extract_text_file(file_path)
                if text and len(text.strip()) > 0:
                    return text
            except Exception as e:
                logger.error(f"SaveAs 방식 실패: {e}")
                
            # COM 해제
            try:
                pythoncom.CoUninitialize()
            except:
                pass
                
            return self._fallback_hwp_processing(file_path)
        except Exception as e:
            logger.error(f"Win32로 HWP 처리 중 오류: {e}")
            # COM 해제 시도
            try:
                pythoncom.CoUninitialize()
            except:
                pass
            return self._fallback_hwp_processing(file_path)
    
    def _alternative_hwp_processing(self, file_path):
        """HWP 파일에서 텍스트를 추출하는 대체 방법"""
        if not self.has_hwp:
            return ""
            
        try:
            if isinstance(file_path, Path):
                file_path = str(file_path)
                
            # 절대 경로로 변환
            file_path = os.path.abspath(file_path)
            
            # COM 초기화
            pythoncom.CoInitialize()
            
            # 다른 방식으로 COM 객체 생성 시도
            hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModuleEx")
            hwp.Open(file_path)
            time.sleep(0.5)  # 한글 로딩 시간 확보
            
            text = hwp.GetTextFile("TEXT", "")
            hwp.Quit()
            
            # COM 해제
            pythoncom.CoUninitialize()
            return text
        except Exception as e:
            logger.error(f"대체 HWP 처리 방법 오류: {e}")
            try:
                pythoncom.CoUninitialize()
            except:
                pass
            return ""
    
    def _fallback_hwp_processing(self, file_path):
        """pyhwp를 사용한 대체 방법"""
        try:
            # 경로가 Path 객체인 경우 문자열로 변환
            if isinstance(file_path, Path):
                file_path = str(file_path)
                
            # 절대 경로로 변환
            file_path = os.path.abspath(file_path)
            
            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
                tmp_path = tmp.name
            
            # 파일 형식 확인
            logger.info(f"대체 방법으로 HWP 파일 처리 시도 중: {file_path}")
            
            success = False
            error_msg = ""
            
            # 방법 1: hwp5proc 사용
            try:
                logger.info("방법 1 시도 중: hwp5proc")
                cmd = f"hwp5proc cat --output=\"{tmp_path}\" \"{file_path}\""
                subprocess.run(cmd, shell=True, check=True)
                success = True
            except Exception as e:
                error_msg += f"방법 1 실패: {str(e)}\n"
                
            # 방법 2: hwp5txt 사용
            if not success:
                try:
                    logger.info("방법 2 시도 중: hwp5txt")
                    cmd = f"hwp5txt \"{file_path}\" > \"{tmp_path}\""
                    subprocess.run(cmd, shell=True, check=True)
                    success = True
                except Exception as e:
                    error_msg += f"방법 2 실패: {str(e)}\n"
            
            # 방법 3: COM 대체 방법
            if not success and self.has_hwp:
                logger.info("방법 3 시도 중: 대체 COM 방식")
                text = self._alternative_hwp_processing(file_path)
                if text:
                    return text
                else:
                    error_msg += "방법 3 실패\n"
            
            # 방법 4: 파일 복사 후 시도
            if not success:
                try:
                    logger.info("방법 4 시도 중: 파일 복사 후 처리")
                    # 임시 디렉토리에 파일 복사
                    temp_dir = tempfile.mkdtemp()
                    temp_file = os.path.join(temp_dir, "temp.hwp")
                    with open(file_path, 'rb') as src, open(temp_file, 'wb') as dst:
                        dst.write(src.read())
                    
                    # hwp5txt로 시도
                    cmd = f"hwp5txt \"{temp_file}\" > \"{tmp_path}\""
                    subprocess.run(cmd, shell=True, check=True)
                    success = True
                    
                    # 임시 디렉토리 정리
                    os.remove(temp_file)
                    os.rmdir(temp_dir)
                except Exception as e:
                    error_msg += f"방법 4 실패: {str(e)}\n"
                    try:
                        os.remove(temp_file)
                        os.rmdir(temp_dir)
                    except:
                        pass
            
            # 모든 방법이 실패하면 오류 기록
            if not success:
                logger.error(f"모든 HWP 처리 방법 실패: {error_msg}")
                return "문서 변환에 실패했습니다. 다른 문서를 사용해 주세요."
                
            # 파일에서 텍스트 읽기
            with open(tmp_path, 'rb') as f:
                raw_data = f.read()
                detected = chardet.detect(raw_data)
                encoding = detected['encoding'] if detected['encoding'] else 'utf-8'
                
            with open(tmp_path, 'r', encoding=encoding, errors='replace') as f:
                text = f.read()
                
            os.unlink(tmp_path)
            return text
        except Exception as e:
            logger.error(f"대체 HWP 처리 중 오류: {e}")
            return "문서 처리 중 오류가 발생했습니다."
    
    def save_document(self, file, overwrite=False):
        """문서 저장 및 유효성 검사"""
        try:
            # 파일 확장자 확인
            file_ext = os.path.splitext(file.name)[1].lower()
            if file_ext not in ['.hwp', '.pdf']:
                return False, f"지원하지 않는 파일 형식: {file_ext}. HWP 또는 PDF 파일만 지원됩니다."
            
            # HWP 파일인 경우 Windows 서버 연결 상태 확인
            if file_ext == '.hwp' and not self.windows_server_available and not self.has_hwp:
                return False, "Windows HWP 서버에 연결할 수 없어 HWP 파일을 처리할 수 없습니다."
            
            # 파일 저장
            file_path = Path(self.documents_path) / file.name
            
            if file_path.exists() and not overwrite:
                return False, "이미 존재하는 파일입니다."
            
            with open(file_path, 'wb') as f:
                f.write(file.getbuffer())
            
            return True, str(file_path)
            
        except Exception as e:
            logger.error(f"문서 저장 중 오류 발생: {e}")
            return False, str(e)
    
    def list_documents(self):
        """문서 디렉토리의 모든 문서 목록 반환"""
        try:
            return [f for f in os.listdir(self.documents_path) if f.lower().endswith(('.hwp', '.pdf'))]
        except Exception as e:
            logger.error(f"문서 목록 조회 오류: {e}")
            return []
    
    def delete_document(self, filename, vector_store=None):
        """문서 디렉토리 및 벡터 저장소에서 문서 삭제"""
        try:
            file_path = Path(self.documents_path) / filename
            deleted = False
            
            # 파일 시스템에서 삭제
            if file_path.exists():
                os.remove(file_path)
                logger.info(f"파일 {filename}이(가) 파일 시스템에서 삭제됨")
                deleted = True
                
                # 벡터 DB에서도 삭제 (벡터 스토어가 제공된 경우)
                if vector_store:
                    success = vector_store.delete_document(filename)
                    if success:
                        logger.info(f"문서 {filename}이(가) 벡터 저장소에서 삭제됨")
                    else:
                        logger.warning(f"문서 {filename}을(를) 벡터 저장소에서 삭제하지 못함")
            
            return deleted
        except Exception as e:
            logger.error(f"문서 삭제 오류: {e}")
            return False
    
    def get_document_path(self, filename):
        """문서의 전체 경로 반환"""
        return str(Path(self.documents_path) / filename)
    
    def _process_hwp_with_windows_server(self, file_path):
        """Windows 서버를 통해 HWP 파일 처리"""
        if not self.windows_server_available:
            raise Exception("Windows HWP 서버에 연결할 수 없습니다.")
            
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, 'application/x-hwp')}
                response = requests.post(f"{self.hwp_server_url}/convert", files=files, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    text = result.get('text', '')
                    if not text:
                        raise Exception("변환된 텍스트가 비어있습니다.")
                    return text
                else:
                    raise Exception(f"서버 오류: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Windows 서버 통신 오류: {e}")
            raise
            
    def process_pdf(self, file_path):
        """PDF 파일에서 텍스트 추출 (PyMuPDF 사용)"""
        try:
            # 경로가 Path 객체인 경우 문자열로 변환
            if isinstance(file_path, Path):
                file_path = str(file_path)
                
            # 절대 경로로 변환
            file_path = os.path.abspath(file_path)
            logger.info(f"PDF 처리 시작 (PyMuPDF), 절대 경로: {file_path}")
            
            # PyMuPDF를 사용하여 텍스트 추출
            pdf_document = fitz.open(file_path)
            logger.info(f"PDF 파일 로드 완료. 총 {len(pdf_document)}페이지 발견")
            
            text = ""
            
            # 각 페이지의 텍스트 추출 및 병합
            for i, page in enumerate(pdf_document):
                logger.debug(f"페이지 {i+1} 처리 중...")
                
                # 페이지에서 텍스트 추출 - 'text' 메서드 사용
                page_text = page.get_text("text")
                
                if page_text:
                    text += page_text + "\n\n"
                    logger.debug(f"페이지 {i+1} 텍스트 길이: {len(page_text)} 자")
                else:
                    logger.warning(f"페이지 {i+1}에서 텍스트를 추출할 수 없습니다")
            
            # 문서 닫기
            pdf_document.close()
            
            if not text or len(text.strip()) == 0:
                logger.warning(f"PDF에서 추출된 텍스트가 없습니다: {file_path}")
                return "PDF에서 텍스트를 추출할 수 없습니다."
                
            logger.info(f"PDF 처리 완료. 추출된 텍스트 길이: {len(text)} 자")
            # 샘플 텍스트 로그 추가 (디버깅용)
            if len(text) > 100:
                logger.debug(f"추출된 텍스트 샘플: {text[:100]}...")
                
            return text
            
        except Exception as e:
            logger.error(f"PDF 처리 중 오류: {e}")
            return ""
    
    def extract_text(self, file_path):
        """파일에서 텍스트 추출"""
        try:
            # 파일 확장자 확인
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # PDF 파일 처리
            if file_ext == '.pdf':
                text = self.process_pdf(file_path)
                if not text:
                    raise Exception("PDF 파일 처리 실패")
                return text, {"source": os.path.basename(file_path)}
            
            # HWP 파일 처리
            elif file_ext == '.hwp':
                # Windows 서버 연결 상태 확인
                if not self.windows_server_available and not self.has_hwp:
                    raise Exception("Windows HWP 서버에 연결할 수 없어 HWP 파일을 처리할 수 없습니다.")
                
                text = ""
                error_msg = ""
                
                # Windows 서버를 통한 처리 시도
                if self.windows_server_available:
                    try:
                        text = self._process_hwp_with_windows_server(file_path)
                    except Exception as e:
                        error_msg += f"Windows 서버 처리 실패: {str(e)}\n"
                
                # Windows 환경에서 로컬 처리 시도
                if not text and platform.system() == 'Windows' and self.has_hwp:
                    try:
                        text = self.process_hwp_with_win32(file_path)
                    except Exception as e:
                        error_msg += f"로컬 처리 실패: {str(e)}\n"
                
                if not text:
                    raise Exception(f"HWP 파일 처리 실패:\n{error_msg}")
                    
                return text, {"source": os.path.basename(file_path)}
            
            else:
                raise Exception(f"지원하지 않는 파일 형식: {file_ext}")
                
        except Exception as e:
            logger.error(f"텍스트 추출 중 오류 발생: {e}")
            raise 