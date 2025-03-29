from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import tempfile
import win32com.client
import uvicorn
from typing import Optional
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="HWP Processing Server")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 운영 환경에서는 특정 도메인만 허용하도록 수정
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """
    서버 상태 확인 엔드포인트
    """
    try:
        # HWP COM 객체 생성 테스트
        hwp = win32com.client.gencache.EnsureDispatch("HWPFrame.HwpObject")
        hwp.Quit()
        return {"status": "healthy", "message": "HWP server is running and can create HWP objects"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/convert")
async def convert_hwp(file: UploadFile = File(...)):
    """
    HWP 파일을 텍스트로 변환하는 엔드포인트
    """
    try:
        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(delete=False, suffix='.hwp') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        # HWP 파일 변환
        text = convert_hwp_to_text(temp_path)
        
        # 임시 파일 삭제
        os.unlink(temp_path)
        
        if not text:
            raise HTTPException(status_code=500, detail="텍스트 추출 실패")
        
        return {"text": text, "filename": file.filename}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error converting HWP file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def convert_hwp_to_text(file_path: str) -> str:
    """
    HWP 파일을 텍스트로 변환하는 함수
    """
    try:
        # HWP COM 객체 생성
        hwp = win32com.client.gencache.EnsureDispatch("HWPFrame.HwpObject")
        
        # 백그라운드 모드 설정
        hwp.XHwpWindows.Item(0).Visible = False
        
        # 파일 열기
        hwp.Open(file_path)
        
        # 전체 텍스트 추출
        text = hwp.GetTextFile("TEXT", file_path)
        
        # 파일 닫기
        hwp.Quit()
        
        if not text:
            raise Exception("추출된 텍스트가 비어있습니다")
        
        return text
        
    except Exception as e:
        logger.error(f"Error in convert_hwp_to_text: {str(e)}")
        raise

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 