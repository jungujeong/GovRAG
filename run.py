#!/usr/bin/env python3
"""
Cross-platform launcher script for RAG system
Works on Windows, macOS, and Linux
"""
import os
import sys
import subprocess
import time
import signal
import platform
from pathlib import Path

class RAGLauncher:
    def __init__(self):
        self.system = platform.system()
        self.project_root = Path(__file__).parent
        self.backend_process = None
        self.frontend_process = None
        
    def check_port(self, port):
        """Check if port is available"""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return True
        except OSError:
            return False
    
    def check_dependencies(self):
        """Check if required dependencies are installed"""
        print("🔍 Checking dependencies...")
        
        # Check Python
        try:
            result = subprocess.run([sys.executable, '--version'], 
                                  capture_output=True, text=True)
            print(f"✅ Python: {result.stdout.strip()}")
        except Exception as e:
            print(f"❌ Python check failed: {e}")
            return False
        
        # Check Node.js
        try:
            result = subprocess.run(['node', '--version'], 
                                  capture_output=True, text=True)
            print(f"✅ Node.js: {result.stdout.strip()}")
        except Exception as e:
            print(f"❌ Node.js not found: {e}")
            return False
        
        # Check if backend dependencies are installed
        try:
            subprocess.run([sys.executable, '-c', 'import fastapi'], 
                          capture_output=True, check=True)
            print("✅ Backend dependencies")
        except subprocess.CalledProcessError:
            print("❌ Backend dependencies missing. Run install script first.")
            return False
        
        # Check if frontend dependencies are installed
        frontend_dir = self.project_root / "frontend"
        if not (frontend_dir / "node_modules").exists():
            print("❌ Frontend dependencies missing. Run install script first.")
            return False
        else:
            print("✅ Frontend dependencies")
        
        return True
    
    def start_backend(self):
        """Start backend server"""
        print("🚀 Starting backend server...")
        
        if not self.check_port(8000):
            print("❌ Port 8000 is already in use")
            return False
        
        backend_dir = self.project_root / "backend"
        env = os.environ.copy()
        env['PYTHONPATH'] = str(backend_dir)
        
        try:
            self.backend_process = subprocess.Popen(
                [sys.executable, '-m', 'uvicorn', 'main:app', '--reload', '--port', '8000'],
                cwd=backend_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait a moment to see if it starts successfully
            time.sleep(3)
            
            if self.backend_process.poll() is None:
                print("✅ Backend server started on http://localhost:8000")
                return True
            else:
                stdout, stderr = self.backend_process.communicate()
                print(f"❌ Backend failed to start:")
                print(f"stdout: {stdout.decode()}")
                print(f"stderr: {stderr.decode()}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to start backend: {e}")
            return False
    
    def start_frontend(self):
        """Start frontend server"""
        print("🚀 Starting frontend server...")
        
        frontend_dir = self.project_root / "frontend"
        
        try:
            self.frontend_process = subprocess.Popen(
                ['npm', 'run', 'dev'],
                cwd=frontend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            print("✅ Frontend server starting...")
            print("🌐 Frontend will be available at http://localhost:5173")
            return True
                
        except Exception as e:
            print(f"❌ Failed to start frontend: {e}")
            return False
    
    def cleanup(self):
        """Clean up processes"""
        print("\n🛑 Shutting down...")
        
        if self.frontend_process:
            try:
                if self.system == "Windows":
                    self.frontend_process.terminate()
                else:
                    self.frontend_process.send_signal(signal.SIGTERM)
                self.frontend_process.wait(timeout=5)
                print("✅ Frontend stopped")
            except subprocess.TimeoutExpired:
                self.frontend_process.kill()
                print("🔪 Frontend force killed")
            except Exception as e:
                print(f"⚠️ Error stopping frontend: {e}")
        
        if self.backend_process:
            try:
                if self.system == "Windows":
                    self.backend_process.terminate()
                else:
                    self.backend_process.send_signal(signal.SIGTERM)
                self.backend_process.wait(timeout=5)
                print("✅ Backend stopped")
            except subprocess.TimeoutExpired:
                self.backend_process.kill()
                print("🔪 Backend force killed")
            except Exception as e:
                print(f"⚠️ Error stopping backend: {e}")
    
    def run(self):
        """Main run method"""
        print("🎯 RAG System Launcher")
        print(f"💻 Platform: {self.system}")
        print(f"📁 Project: {self.project_root}")
        
        # Check dependencies
        if not self.check_dependencies():
            print("\n❌ Dependency check failed. Please run the install script first.")
            return 1
        
        # Setup signal handlers
        def signal_handler(signum, frame):
            self.cleanup()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        if self.system != "Windows":
            signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            # Start backend
            if not self.start_backend():
                return 1
            
            # Start frontend  
            if not self.start_frontend():
                self.cleanup()
                return 1
            
            print("\n✅ RAG system is running!")
            print("🌐 Backend: http://localhost:8000")
            print("🌐 Frontend: http://localhost:5173")
            print("\n👀 Watching for changes... Press Ctrl+C to stop")
            
            # Wait for frontend to finish (it will run until stopped)
            self.frontend_process.wait()
            
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return 1
        finally:
            self.cleanup()
        
        return 0

def main():
    launcher = RAGLauncher()
    sys.exit(launcher.run())

if __name__ == '__main__':
    main()