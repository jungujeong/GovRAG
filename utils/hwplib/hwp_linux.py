import os
import subprocess
import tempfile
import logging
from pathlib import Path
import jpype
import jpype.imports
from jpype.types import *

# 로깅 설정
logger = logging.getLogger(__name__)

class HwpLinuxExtractor:
    """
    리눅스 환경에서 hwplib를 사용하여 HWP 파일에서 텍스트를 추출하는 클래스
    """

    def __init__(self, hwplib_jar_path=None):
        """
        초기화 함수
        
        Args:
            hwplib_jar_path: hwplib-1.1.8.jar 파일의 경로
        """
        self.hwplib_jar_path = hwplib_jar_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            "hwplib-1.1.8.jar"
        )
        self._start_jvm()

    def _start_jvm(self):
        """JVM을 시작하고 hwplib jar를 로드"""
        try:
            if not jpype.isJVMStarted():
                jpype.startJVM(
                    jpype.getDefaultJVMPath(), 
                    "-Djava.class.path=" + self.hwplib_jar_path,
                    convertStrings=True
                )
                logger.info("JVM 시작 및 hwplib 로드 완료")
            return True
        except Exception as e:
            logger.error(f"JVM 시작 오류: {e}")
            return False

    def extract_text(self, hwp_file_path):
        """
        HWP 파일에서 텍스트 추출
        
        Args:
            hwp_file_path: HWP 파일 경로
            
        Returns:
            추출된 텍스트 문자열
        """
        try:
            # HWP 파일 절대 경로로 변환
            hwp_file_path = str(Path(hwp_file_path).absolute())
            
            if not os.path.exists(hwp_file_path):
                logger.error(f"파일이 존재하지 않습니다: {hwp_file_path}")
                return ""
            
            # Java 클래스 import
            from kr.dogfoot.hwplib.reader import HWPReader
            from kr.dogfoot.hwplib.tool.textextractor import TextExtractor
            from kr.dogfoot.hwplib.tool.textextractor import TextExtractOption
            
            # HWP 파일 로드
            try:
                hwpFile = HWPReader.fromFile(hwp_file_path)
                
                # 방법 1: 기본 TextExtractOption 사용
                option = TextExtractOption()
                
                # 텍스트 추출
                text = TextExtractor.extract(hwpFile, option)
                
                logger.info(f"HWP 파일에서 텍스트 추출 완료: {hwp_file_path}")
                return text
            except jpype.JException as je:
                # XML 형식의 한글 파일 처리 (Office 2007+ XML)
                if "OfficeXmlFileException" in str(je):
                    logger.warning(f"XML 형식의 한글 파일 감지: {hwp_file_path}")
                    return self._extract_hwpx_text(hwp_file_path)
                else:
                    # 다른 Java 예외는 다음 방법으로 시도
                    logger.error(f"기본 방법 실패, 대체 방법 시도: {je}")
                    raise
            
        except Exception as e:
            logger.error(f"기본 TextExtractOption 사용 실패: {e}")
            try:
                # 방법 2: BOTH 텍스트 추출 메서드 사용
                from kr.dogfoot.hwplib.tool.textextractor import TextExtractMethod
                text = TextExtractor.extract(hwpFile, TextExtractMethod.BOTH)
                return text
            except Exception as e2:
                logger.error(f"BOTH 메서드 사용 실패: {e2}")
                try:
                    # 방법 3: MAIN 텍스트 추출 메서드 사용
                    from kr.dogfoot.hwplib.tool.textextractor import TextExtractMethod
                    text = TextExtractor.extract(hwpFile, TextExtractMethod.MAIN)
                    return text
                except Exception as e3:
                    logger.error(f"MAIN 메서드 사용 실패: {e3}")
                    return self._fallback_extraction(hwp_file_path)
    
    def _extract_hwpx_text(self, hwp_file_path):
        """
        XML 형식의 한글 파일에서 텍스트 추출 (HWPX 또는 XML 기반 HWP)
        
        Args:
            hwp_file_path: HWP 파일 경로
            
        Returns:
            추출된 텍스트 문자열
        """
        try:
            logger.info(f"XML 기반 한글 파일 처리 시도: {hwp_file_path}")
            
            # 임시 파일로 복사하고 .zip으로 확장자 변경
            with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
                temp_path = temp_file.name
                
                # 파일 복사
                import shutil
                shutil.copy2(hwp_file_path, temp_path)
                
                # ZIP 파일로 처리
                import zipfile
                text_content = []
                
                with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                    # 한글 XML 문서 내 텍스트를 포함하는 파일 찾기
                    for file_info in zip_ref.infolist():
                        # 일반적으로 텍스트는 'Contents/section*.xml' 파일에 있음
                        if 'section' in file_info.filename.lower() and file_info.filename.endswith('.xml'):
                            try:
                                with zip_ref.open(file_info) as xml_file:
                                    content = xml_file.read().decode('utf-8')
                                    
                                    # XML 파싱 (안전하게)
                                    import xml.etree.ElementTree as ET
                                    try:
                                        root = ET.fromstring(content)
                                        # 텍스트 요소 추출 (단순화된 접근)
                                        for elem in root.iter():
                                            if elem.text and elem.text.strip():
                                                text_content.append(elem.text.strip())
                                    except ET.ParseError:
                                        # XML 파싱 실패 시 정규식으로 텍스트 추출
                                        import re
                                        text_matches = re.findall(r'>([^<]+)<', content)
                                        text_content.extend([t.strip() for t in text_matches if t.strip()])
                            except Exception as e:
                                logger.error(f"섹션 파일 처리 중 오류: {e}")
                        
                        # 'bodyText' 파일도 확인
                        elif 'bodytext' in file_info.filename.lower() and file_info.filename.endswith('.xml'):
                            try:
                                with zip_ref.open(file_info) as xml_file:
                                    content = xml_file.read().decode('utf-8')
                                    
                                    # 텍스트 추출
                                    import re
                                    text_matches = re.findall(r'>([^<]+)<', content)
                                    text_content.extend([t.strip() for t in text_matches if t.strip()])
                            except Exception as e:
                                logger.error(f"bodyText 파일 처리 중 오류: {e}")
            
            # 임시 파일 삭제
            os.unlink(temp_path)
            
            # 결과 반환
            if text_content:
                result = '\n'.join(text_content)
                logger.info(f"XML 형식 한글 파일에서 {len(text_content)}개 텍스트 조각 추출 성공")
                return result
            else:
                logger.warning("XML 형식 한글 파일에서 텍스트를 찾을 수 없음")
                # 텍스트를 찾지 못한 경우 대체 방법 시도
                return self._fallback_extraction(hwp_file_path)
                
        except Exception as e:
            logger.error(f"XML 기반 한글 파일 처리 실패: {e}")
            return self._fallback_extraction(hwp_file_path)
    
    def _fallback_extraction(self, hwp_file_path):
        """
        hwp_loader.py를 subprocess로 실행하는 대체 방법
        
        Args:
            hwp_file_path: HWP 파일 경로
            
        Returns:
            추출된 텍스트 문자열
        """
        try:
            logger.info(f"대체 방법으로 HWP 텍스트 추출 시도: {hwp_file_path}")
            loader_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hwp_loader.py")
            
            result = subprocess.run(
                ["python", loader_path, "--hwp_jar_path", self.hwplib_jar_path, "--file_path", hwp_file_path],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"대체 방법 오류: {result.stderr}")
                return ""
                
            return result.stdout.strip()
            
        except Exception as e:
            logger.error(f"대체 방법 실행 오류: {e}")
            return ""
    
    # ────────────────────────────────────────────────────────────────
    # NEW METHOD ➜ “셀마다 AAA 삽입” 예시
    # ────────────────────────────────────────────────────────────────
    def extract_tables_with_marker(self, hwp_file_path, marker="AAA"):
        """
        문서 안 모든 표를 순회하면서 **각 셀 앞뒤에 marker(기본 'AAA')를 붙여**
        3-중첩 파이썬 리스트로 반환한다.
        
        Returns
        -------
        list[list[list[str]]]
            tables[표][행][셀] -> 'AAA{cellText}AAA'
        """
        # 1) 필요한 Java 클래스 import
        from kr.dogfoot.hwplib.reader import HWPReader
        from kr.dogfoot.hwplib.object.bodytext.control import ControlType
        from kr.dogfoot.hwplib.tool.textextractor import TextExtractor, TextExtractOption
        JControlTable = jpype.JClass(
            "kr.dogfoot.hwplib.object.bodytext.control.table.ControlTable"
        )

        # 2) 파일 로드 & 옵션
        hwp = HWPReader.fromFile(str(Path(hwp_file_path).absolute()))
        option = TextExtractOption()            # 기본 텍스트 추출 옵션
        body = hwp.getBodyText()

        tables_py = []

        # 3) 섹션 → 문단 → 컨트롤 → 표 순회
        for s_idx in range(body.getSectionCount()):
            section = body.getSection(s_idx)
            for para in section.getParagraphs():
                for ctrl in (para.getControlList() or []):
                    if ctrl.getType() != ControlType.Table:
                        continue
                    table = JControlTable.cast_(ctrl)

                    # 4) 행 / 셀 순회 -- 셀마다 AAA 삽입
                    rows_py = []
                    for row in table.getRowList():
                        cells_py = []
                        for cell in row.getCellList():
                            cell_text = " ".join(
                                TextExtractor.extract(p, option)
                                for p in cell.getParagraphList()
                            ).strip()
                            cells_py.append(f"{marker}{cell_text}{marker}")
                        rows_py.append(cells_py)
                    tables_py.append(rows_py)

        return tables_py


    def shutdown(self):
        """JVM 종료"""
        if jpype.isJVMStarted():
            jpype.shutdownJVM()
            logger.info("JVM 종료 완료") 