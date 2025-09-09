#!/usr/bin/env python3
"""
Cross-platform installation script for RAG system
Works on Windows, macOS, and Linux
"""
import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path

class RAGInstaller:
    def __init__(self):
        self.system = platform.system()
        self.project_root = Path(__file__).parent
        
    def run_command(self, cmd, description, cwd=None, check=True):
        """Run command with proper error handling"""
        print(f"🔄 {description}...")
        try:
            if isinstance(cmd, str):
                result = subprocess.run(cmd, shell=True, cwd=cwd, check=check, 
                                      capture_output=True, text=True)
            else:
                result = subprocess.run(cmd, cwd=cwd, check=check, 
                                      capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ {description} completed")
                return True
            else:
                print(f"❌ {description} failed:")
                print(f"stdout: {result.stdout}")
                print(f"stderr: {result.stderr}")
                return False
        except subprocess.CalledProcessError as e:
            print(f"❌ {description} failed: {e}")
            if e.stdout:
                print(f"stdout: {e.stdout}")
            if e.stderr:
                print(f"stderr: {e.stderr}")
            return False
        except Exception as e:
            print(f"❌ {description} failed: {e}")
            return False
    
    def check_python(self):
        """Check Python version"""
        print("🐍 Checking Python...")
        try:
            version_info = sys.version_info
            version_str = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
            print(f"✅ Python {version_str} found")
            
            if version_info < (3, 8):
                print("❌ Python 3.8 or later is required")
                return False
            return True
        except Exception as e:
            print(f"❌ Python check failed: {e}")
            return False
    
    def check_node(self):
        """Check Node.js installation"""
        print("📦 Checking Node.js...")
        try:
            result = subprocess.run(['node', '--version'], 
                                  capture_output=True, text=True, check=True)
            version = result.stdout.strip()
            print(f"✅ Node.js {version} found")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ Node.js not found")
            print("Please install Node.js 18 or later from https://nodejs.org/")
            return False
    
    def check_git(self):
        """Check Git installation"""
        print("🔧 Checking Git...")
        try:
            result = subprocess.run(['git', '--version'], 
                                  capture_output=True, text=True, check=True)
            version = result.stdout.strip()
            print(f"✅ {version} found")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️ Git not found (optional for basic functionality)")
            return False
    
    def check_tesseract(self):
        """Check Tesseract OCR installation"""
        print("👁️ Checking Tesseract OCR...")
        try:
            result = subprocess.run(['tesseract', '--version'], 
                                  capture_output=True, text=True, check=True)
            version_line = result.stdout.split('\n')[0]
            print(f"✅ {version_line} found")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️ Tesseract OCR not found")
            print("📋 Installation instructions:")
            if self.system == "Windows":
                print("  Download from: https://github.com/UB-Mannheim/tesseract/wiki")
            elif self.system == "Darwin":  # macOS
                print("  brew install tesseract tesseract-lang")
            else:  # Linux
                print("  sudo apt-get install tesseract-ocr tesseract-ocr-kor")
            print("  Make sure to install Korean language support")
            return False
    
    def install_python_deps(self):
        """Install Python dependencies"""
        print("📦 Installing Python dependencies...")
        
        # Upgrade pip
        if not self.run_command([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'], 
                               "Upgrading pip"):
            return False
        
        # Install requirements
        requirements_file = self.project_root / "requirements.txt"
        if requirements_file.exists():
            if not self.run_command([sys.executable, '-m', 'pip', 'install', '-r', str(requirements_file)], 
                                   "Installing Python packages"):
                return False
        else:
            print("⚠️ requirements.txt not found")
        
        return True
    
    def install_node_deps(self):
        """Install Node.js dependencies"""
        frontend_dir = self.project_root / "frontend"
        if not frontend_dir.exists():
            print("⚠️ Frontend directory not found")
            return False
        
        package_json = frontend_dir / "package.json"
        if not package_json.exists():
            print("⚠️ package.json not found")
            return False
        
        return self.run_command(['npm', 'install'], "Installing Node.js packages", cwd=frontend_dir)
    
    def setup_directories(self):
        """Create necessary directories"""
        print("📁 Setting up project structure...")
        
        directories = [
            "data/documents",
            "data/index", 
            "data/chroma",
            "data/golden",
            "reports",
            "logs"
        ]
        
        for dir_path in directories:
            full_path = self.project_root / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            print(f"  📂 {dir_path}")
        
        print("✅ Project structure created")
        return True
    
    def setup_environment(self):
        """Setup environment file"""
        print("⚙️ Setting up environment...")
        
        env_example = self.project_root / ".env.example"
        env_file = self.project_root / ".env"
        
        if not env_file.exists() and env_example.exists():
            shutil.copy2(env_example, env_file)
            print("✅ Created .env from template")
        elif env_file.exists():
            print("✅ .env file already exists")
        else:
            print("⚠️ No .env.example found")
        
        return True
    
    def download_models(self):
        """Download AI models if setup script exists"""
        print("🤖 Checking for model download script...")
        
        setup_script = self.project_root / "setup_offline.py"
        if setup_script.exists():
            return self.run_command([sys.executable, str(setup_script), '--download-models'], 
                                   "Downloading AI models", check=False)
        else:
            print("ℹ️ No model download script found")
            return True
    
    def run_tests(self):
        """Run basic tests to verify installation"""
        print("🧪 Running installation tests...")
        
        # Test Python imports
        test_imports = [
            'fastapi',
            'uvicorn', 
            'whoosh',
            'sentence_transformers'
        ]
        
        for module in test_imports:
            try:
                subprocess.run([sys.executable, '-c', f'import {module}'], 
                             check=True, capture_output=True)
                print(f"  ✅ {module}")
            except subprocess.CalledProcessError:
                print(f"  ❌ {module} import failed")
                return False
        
        print("✅ Import tests passed")
        return True
    
    def install(self):
        """Main installation method"""
        print("🎯 RAG System Installer")
        print(f"💻 Platform: {self.system}")
        print(f"📁 Project: {self.project_root}")
        print()
        
        # Check prerequisites
        if not self.check_python():
            return 1
        
        if not self.check_node():
            return 1
        
        # Optional checks
        self.check_git()
        self.check_tesseract()
        print()
        
        # Setup project
        if not self.setup_directories():
            return 1
        
        if not self.setup_environment():
            return 1
        
        # Install dependencies
        if not self.install_python_deps():
            return 1
        
        if not self.install_node_deps():
            return 1
        
        # Download models (optional)
        self.download_models()
        
        # Test installation
        if not self.run_tests():
            print("⚠️ Some tests failed, but installation may still work")
        
        print()
        print("✅ Installation completed successfully!")
        print()
        print("🚀 Next steps:")
        print("  1. Place your documents in data/documents/")
        print("  2. Run indexing: make index (or scripts/index.bat on Windows)")
        print("  3. Start system: make run (or python run.py)")
        print()
        
        return 0

def main():
    installer = RAGInstaller()
    sys.exit(installer.install())

if __name__ == '__main__':
    main()