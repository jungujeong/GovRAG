#!/usr/bin/env python3
import os
import sys
import tarfile
import subprocess
from pathlib import Path
import json
import hashlib
from datetime import datetime

def create_offline_bundle():
    """Create offline bundle with all dependencies"""
    
    print("Creating offline bundle...")
    
    # Create dist directory
    dist_dir = Path("dist")
    dist_dir.mkdir(exist_ok=True)
    
    bundle_name = f"rag_chatbot_offline_{datetime.now().strftime('%Y%m%d')}.tar.gz"
    bundle_path = dist_dir / bundle_name
    
    # Create temporary directory for bundle contents
    temp_dir = Path("temp_bundle")
    temp_dir.mkdir(exist_ok=True)
    
    try:
        # 1. Download Python packages
        print("Downloading Python packages...")
        pip_dir = temp_dir / "python_packages"
        pip_dir.mkdir(exist_ok=True)
        
        subprocess.run([
            sys.executable, "-m", "pip", "download",
            "-r", "requirements.txt",
            "-d", str(pip_dir)
        ], check=True)
        
        # 2. Bundle frontend dependencies
        print("Bundling frontend dependencies...")
        frontend_dir = Path("frontend")
        
        if (frontend_dir / "node_modules").exists():
            # Create frontend bundle
            subprocess.run(
                ["npm", "run", "build"],
                cwd=frontend_dir,
                check=True
            )
            
            # Copy built frontend
            import shutil
            shutil.copytree(
                frontend_dir / "dist",
                temp_dir / "frontend_dist"
            )
        
        # 3. Create models directory structure
        print("Preparing model directories...")
        models_dir = temp_dir / "models"
        models_dir.mkdir(exist_ok=True)
        (models_dir / "embeddings").mkdir(exist_ok=True)
        (models_dir / "reranker").mkdir(exist_ok=True)
        
        # Add download instructions
        with open(models_dir / "README.md", "w") as f:
            f.write("""# Model Download Instructions

## Embedding Models
1. Download BAAI/bge-m3 from HuggingFace
2. Place in models/embeddings/BAAI_bge-m3/

## Reranker Model
1. Download jinaai/jina-reranker-v2-base-multilingual
2. Place in models/reranker/jina-reranker/

## Ollama Models
1. Install Ollama offline
2. Pull models: ollama pull qwen3:4b
""")
        
        # 4. Copy source code
        print("Copying source code...")
        for item in ["backend", "frontend/src", "frontend/package.json", 
                    "frontend/vite.config.js", "tests", "data/golden"]:
            src = Path(item)
            if src.exists():
                if src.is_dir():
                    shutil.copytree(src, temp_dir / item)
                else:
                    shutil.copy2(src, temp_dir / item)
        
        # 5. Copy configuration files
        print("Copying configuration files...")
        config_files = [
            "requirements.txt",
            ".env.example",
            "Makefile",
            "README.md",
            "setup_offline.py",
            "start.sh",
            "stop.sh"
        ]
        
        for config_file in config_files:
            if Path(config_file).exists():
                shutil.copy2(config_file, temp_dir)
        
        # 6. Create installation script
        print("Creating installation script...")
        with open(temp_dir / "install_offline.sh", "w") as f:
            f.write("""#!/bin/bash
set -e

echo "Installing RAG Chatbot System (Offline)"

# Install Python packages
echo "Installing Python packages..."
pip install --no-index --find-links python_packages -r requirements.txt

# Setup directories
echo "Setting up directories..."
mkdir -p data/documents data/index data/chroma data/golden
mkdir -p reports logs

# Copy models if available
if [ -d "models" ]; then
    echo "Copying models..."
    cp -r models ../
fi

# Setup frontend
if [ -d "frontend_dist" ]; then
    echo "Setting up frontend..."
    mkdir -p ../frontend/dist
    cp -r frontend_dist/* ../frontend/dist/
fi

# Copy source code
echo "Copying source code..."
cp -r backend ../
cp -r tests ../
cp -r data/golden/* ../data/golden/

# Copy configuration
cp .env.example ../.env
cp Makefile ../
cp *.sh ../

echo "Installation complete!"
echo "Next steps:"
echo "1. cd .."
echo "2. Edit .env file with your settings"
echo "3. Place HWP/PDF documents in data/documents/"
echo "4. Run: make index"
echo "5. Run: make run"
""")
        
        os.chmod(temp_dir / "install_offline.sh", 0o755)
        
        # 7. Create manifest
        print("Creating manifest...")
        manifest = {
            "version": "1.0.0",
            "created": datetime.now().isoformat(),
            "contents": {
                "python_packages": len(list(pip_dir.glob("*.whl"))) + len(list(pip_dir.glob("*.tar.gz"))),
                "source_files": sum(1 for _ in temp_dir.rglob("*.py")),
                "frontend_built": (temp_dir / "frontend_dist").exists()
            },
            "requirements": {
                "python": ">=3.12",
                "ollama": "required (install separately)",
                "tesseract": "optional (for OCR)",
                "java": "optional (for HWP)"
            }
        }
        
        with open(temp_dir / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)
        
        # 8. Create tarball
        print(f"Creating bundle: {bundle_name}")
        with tarfile.open(bundle_path, "w:gz") as tar:
            tar.add(temp_dir, arcname="rag_chatbot_offline")
        
        # 9. Calculate checksum
        print("Calculating checksum...")
        sha256_hash = hashlib.sha256()
        with open(bundle_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        checksum = sha256_hash.hexdigest()
        
        with open(dist_dir / f"{bundle_name}.sha256", "w") as f:
            f.write(f"{checksum}  {bundle_name}\n")
        
        # 10. Clean up
        print("Cleaning up...")
        shutil.rmtree(temp_dir)
        
        # Print summary
        bundle_size = bundle_path.stat().st_size / (1024 * 1024)
        print("\n" + "="*50)
        print(f"✅ Bundle created successfully!")
        print(f"📦 File: {bundle_path}")
        print(f"📏 Size: {bundle_size:.2f} MB")
        print(f"🔐 SHA256: {checksum}")
        print("\nTo use this bundle:")
        print("1. Copy to target machine")
        print("2. Extract: tar -xzf " + bundle_name)
        print("3. cd rag_chatbot_offline")
        print("4. Run: ./install_offline.sh")
        print("="*50)
        
    except subprocess.CalledProcessError as e:
        print(f"Error creating bundle: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        # Ensure cleanup
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    create_offline_bundle()