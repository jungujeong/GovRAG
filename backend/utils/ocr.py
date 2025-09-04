import pytesseract
from PIL import Image
import cv2
import numpy as np
from typing import Optional, Dict, List
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class OCRProcessor:
    """Advanced OCR processor for Korean documents"""
    
    def __init__(self, lang: str = 'kor+eng'):
        self.lang = lang
        self.config = r'--oem 3 --psm 6'
        
        # Check Tesseract installation
        try:
            pytesseract.get_tesseract_version()
        except Exception as e:
            logger.error(f"Tesseract not found: {e}")
            raise RuntimeError("Tesseract OCR not installed")
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for better OCR results"""
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Apply thresholding
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Noise removal
        denoised = cv2.medianBlur(thresh, 3)
        
        # Deskewing
        coords = np.column_stack(np.where(denoised > 0))
        if len(coords) > 0:
            angle = cv2.minAreaRect(coords)[-1]
            
            if angle < -45:
                angle = 90 + angle
            
            if abs(angle) > 0.5:
                (h, w) = denoised.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                denoised = cv2.warpAffine(denoised, M, (w, h),
                                         flags=cv2.INTER_CUBIC,
                                         borderMode=cv2.BORDER_REPLICATE)
        
        return denoised
    
    def extract_text(self, image_path: str) -> str:
        """Extract text from image file"""
        try:
            # Load image
            image = cv2.imread(image_path)
            
            if image is None:
                raise ValueError(f"Cannot load image: {image_path}")
            
            # Preprocess
            processed = self.preprocess_image(image)
            
            # Perform OCR
            text = pytesseract.image_to_string(
                processed,
                lang=self.lang,
                config=self.config
            )
            
            return text
            
        except Exception as e:
            logger.error(f"OCR failed for {image_path}: {e}")
            return ""
    
    def extract_with_confidence(self, image_path: str) -> Dict:
        """Extract text with confidence scores"""
        try:
            # Load image
            image = cv2.imread(image_path)
            
            if image is None:
                raise ValueError(f"Cannot load image: {image_path}")
            
            # Preprocess
            processed = self.preprocess_image(image)
            
            # Get detailed OCR data
            data = pytesseract.image_to_data(
                processed,
                lang=self.lang,
                config=self.config,
                output_type=pytesseract.Output.DICT
            )
            
            # Process results
            results = {
                "text": "",
                "confidence": 0.0,
                "words": []
            }
            
            valid_words = []
            confidence_scores = []
            
            for i in range(len(data['text'])):
                if int(data['conf'][i]) > 0:
                    word = data['text'][i].strip()
                    
                    if word:
                        valid_words.append(word)
                        confidence_scores.append(int(data['conf'][i]))
                        
                        results["words"].append({
                            "text": word,
                            "confidence": int(data['conf'][i]),
                            "bbox": {
                                "x": data['left'][i],
                                "y": data['top'][i],
                                "width": data['width'][i],
                                "height": data['height'][i]
                            }
                        })
            
            results["text"] = " ".join(valid_words)
            
            if confidence_scores:
                results["confidence"] = sum(confidence_scores) / len(confidence_scores)
            
            return results
            
        except Exception as e:
            logger.error(f"OCR with confidence failed: {e}")
            return {
                "text": "",
                "confidence": 0.0,
                "words": []
            }
    
    def extract_table(self, image_path: str) -> List[List[str]]:
        """Extract table structure from image"""
        try:
            # Load image
            image = cv2.imread(image_path)
            
            if image is None:
                return []
            
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Detect horizontal and vertical lines
            thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
            
            # Detect horizontal lines
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
            horizontal = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel)
            
            # Detect vertical lines
            vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
            vertical = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, vertical_kernel)
            
            # Combine lines
            table_mask = cv2.add(horizontal, vertical)
            
            # Find contours
            contours, _ = cv2.findContours(table_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            # Extract cells
            cells = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                
                if w > 20 and h > 20:  # Filter small regions
                    cell_image = gray[y:y+h, x:x+w]
                    
                    # OCR on cell
                    cell_text = pytesseract.image_to_string(
                        cell_image,
                        lang=self.lang,
                        config=self.config
                    ).strip()
                    
                    cells.append({
                        "text": cell_text,
                        "bbox": (x, y, w, h)
                    })
            
            # Sort cells into rows and columns
            if cells:
                # Sort by y coordinate (rows)
                cells.sort(key=lambda c: c["bbox"][1])
                
                # Group into rows
                rows = []
                current_row = []
                current_y = cells[0]["bbox"][1]
                
                for cell in cells:
                    if abs(cell["bbox"][1] - current_y) < 20:  # Same row
                        current_row.append(cell)
                    else:
                        # Sort row by x coordinate
                        current_row.sort(key=lambda c: c["bbox"][0])
                        rows.append([c["text"] for c in current_row])
                        
                        current_row = [cell]
                        current_y = cell["bbox"][1]
                
                if current_row:
                    current_row.sort(key=lambda c: c["bbox"][0])
                    rows.append([c["text"] for c in current_row])
                
                return rows
            
            return []
            
        except Exception as e:
            logger.error(f"Table extraction failed: {e}")
            return []