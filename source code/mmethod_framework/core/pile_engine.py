                      
                                                                         
                                     
                           
              
                    
           
            
                     
                                                                         
from __future__ import annotations
import os
import sys
import subprocess
import shutil
import tempfile
import logging
import time
from pathlib import Path
from typing import Tuple, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum
import threading

logger = logging.getLogger(__name__)

                                                                         
      
                                                                         
class EngineStatus(Enum):
    NOT_FOUND = "executable_not_found"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class CalculationResult:

    success: bool
    status: EngineStatus
    message: str
    out_file: str = ""
    pos_file: str = ""
    elapsed_time: float = 0.0
    return_code: int = -1
    stdout: str = ""
    stderr: str = ""


class PileEngine:

    
    EXECUTABLE_NAMES = [
        "BridgePile.exe", "bridgepile.exe", "BRIDGEPILE.EXE",
        "BCAD-PILE.exe", "bcad-pile.exe", "pile.exe", "PILE.EXE"
    ]
    
    DEFAULT_TIMEOUT = 300
    
    def __init__(self, exe_path: Optional[str] = None):

        self._exe_path: Optional[Path] = None
        self._status: EngineStatus = EngineStatus.NOT_FOUND
        self._process: Optional[subprocess.Popen] = None
        self._cancel_requested: bool = False
        self._progress_callback: Optional[Callable[[str], None]] = None
        
        if exe_path:
            self.set_executable_path(exe_path)
        else:
            self._find_executable()
    
    @property
    def exe_path(self) -> Optional[str]:
        return str(self._exe_path) if self._exe_path else None
    
    @property
    def status(self) -> EngineStatus:
        return self._status
    
    @property
    def is_ready(self) -> bool:
        return self._status == EngineStatus.READY
    
    def set_executable_path(self, path: str) -> bool:

        exe_path = Path(path)
        
        if not exe_path.exists():
            logger.error(f"可执行文件不存在: {path}")
            self._status = EngineStatus.NOT_FOUND
            return False
        
        if not exe_path.is_file():
            logger.error(f"路径不是文件: {path}")
            self._status = EngineStatus.NOT_FOUND
            return False
        
        if sys.platform == 'win32' and exe_path.suffix.lower() != '.exe':
            logger.warning(f"文件可能不是可执行文件: {path}")
        
        self._exe_path = exe_path
        self._status = EngineStatus.READY
        logger.info(f"已设置可执行文件: {exe_path}")
        return True
    
    def _find_executable(self) -> bool:

        search_paths = [
            Path(__file__).parent,
            Path(sys.executable).parent,
            Path(sys.executable).parent / "_internal",
            Path.cwd(),
            Path(__file__).parent / "bin",
            Path(__file__).parent / "engine",
            Path.cwd() / "bin",
        ]

                                           
        if hasattr(sys, '_MEIPASS'):
            search_paths.insert(0, Path(sys._MEIPASS))
        
        if "BCAD_PILE_PATH" in os.environ:
            search_paths.insert(0, Path(os.environ["BCAD_PILE_PATH"]))
        
        for search_dir in search_paths:
            if not search_dir.exists():
                continue
            
            for exe_name in self.EXECUTABLE_NAMES:
                exe_path = search_dir / exe_name
                if exe_path.exists() and exe_path.is_file():
                    self._exe_path = exe_path
                    self._status = EngineStatus.READY
                    logger.info(f"自动找到可执行文件: {exe_path}")
                    return True
        
        logger.warning("未能自动找到 BCAD-PILE 可执行文件")
        self._status = EngineStatus.NOT_FOUND
        return False
    
    def set_progress_callback(self, callback: Callable[[str], None]) -> None:
        self._progress_callback = callback
    
    def _report_progress(self, message: str) -> None:
        logger.debug(message)
        if self._progress_callback:
            try:
                self._progress_callback(message)
            except Exception:
                pass
    
    def cancel(self) -> None:

        self._cancel_requested = True
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass
    
    def run_calculation(
        self,
        dat_file: str,
        work_dir: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> CalculationResult:

        self._cancel_requested = False
        start_time = time.time()
        
        if not self.is_ready:
            return CalculationResult(
                success=False,
                status=EngineStatus.NOT_FOUND,
                message="计算引擎未就绪，请先设置可执行文件路径"
            )
        
                
        dat_path = Path(dat_file)
        if not dat_path.exists():
            return CalculationResult(
                success=False,
                status=EngineStatus.FAILED,
                message=f"输入文件不存在: {dat_file}"
            )
        


        if work_dir:
            work_path = Path(work_dir).resolve()
            work_path.mkdir(parents=True, exist_ok=True)
        else:
            work_path = Path(tempfile.mkdtemp(prefix="pile_calc_"))
        
                   
        dat_path_resolved = dat_path.resolve()
        if dat_path_resolved.parent != work_path:
            target_dat = work_path / dat_path.name
            if dat_path_resolved != target_dat.resolve():
                shutil.copy2(dat_path, target_dat)
                dat_path = target_dat
            else:
                dat_path = dat_path_resolved
        else:
            dat_path = dat_path_resolved
        
        base_name = dat_path.stem
        out_file = work_path / f"{base_name}.out"
        pos_file = work_path / f"{base_name}.pos"
        
        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT
        
        self._status = EngineStatus.RUNNING
        self._report_progress("正在启动计算引擎...")
        


        try:
            result = self._execute_fortran(
                work_dir=work_path,
                input_name=base_name,
                timeout=timeout
            )
            
            elapsed = time.time() - start_time
            
            if self._cancel_requested:
                self._status = EngineStatus.READY
                return CalculationResult(
                    success=False,
                    status=EngineStatus.CANCELLED,
                    message="计算已取消",
                    elapsed_time=elapsed
                )
            
            if result.success:
                if out_file.exists():
                    result.out_file = str(out_file)
                else:
                    logger.warning(f"计算完成但未找到输出文件: {out_file}")
                
                if pos_file.exists():
                    result.pos_file = str(pos_file)
                
                self._status = EngineStatus.READY
            else:
                self._status = EngineStatus.READY
            
            result.elapsed_time = elapsed
            return result
            
        except subprocess.TimeoutExpired:
            self._status = EngineStatus.READY
            return CalculationResult(
                success=False,
                status=EngineStatus.TIMEOUT,
                message=f"计算超时 ({timeout} 秒)",
                elapsed_time=time.time() - start_time
            )
        except Exception as e:
            self._status = EngineStatus.READY
            logger.exception("计算过程发生异常")
            return CalculationResult(
                success=False,
                status=EngineStatus.FAILED,
                message=f"计算异常: {str(e)}",
                elapsed_time=time.time() - start_time
            )
    
    def _execute_fortran(
        self,
        work_dir: Path,
        input_name: str,
        timeout: float
    ) -> CalculationResult:

        cmd = [str(self._exe_path)]
        
                                 
        stdin_input = f"{input_name}\n"
        
        self._report_progress(f"执行命令: {' '.join(cmd)}")
        self._report_progress(f"工作目录: {work_dir}")
        self._report_progress(f"输入文件名: {input_name}")
        
        self._process = subprocess.Popen(
            cmd,
            cwd=str(work_dir),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        
        try:
            stdout, stderr = self._process.communicate(
                input=stdin_input,
                timeout=timeout
            )
            
            return_code = self._process.returncode
            self._report_progress(f"进程退出代码: {return_code}")
            
            if return_code == 0:
                return CalculationResult(
                    success=True,
                    status=EngineStatus.COMPLETED,
                    message="计算完成",
                    return_code=return_code,
                    stdout=stdout,
                    stderr=stderr
                )
            else:
                error_msg = self._analyze_error(stdout, stderr, return_code)
                return CalculationResult(
                    success=False,
                    status=EngineStatus.FAILED,
                    message=error_msg,
                    return_code=return_code,
                    stdout=stdout,
                    stderr=stderr
                )
        finally:
            self._process = None
    
    def _analyze_error(self, stdout: str, stderr: str, return_code: int) -> str:

        combined_output = stdout + stderr
        
        if "Error:<0>" in combined_output:
            return "输入文件格式错误：缺少 <0> 段定义"
        if "Error: <" in combined_output:
            return "输入文件格式错误：段定义不正确"
        if "file not found" in combined_output.lower():
            return "找不到输入文件"
        if "access denied" in combined_output.lower():
            return "文件访问被拒绝"

        win_crash_msg = self._describe_windows_exit_code(return_code)
        if win_crash_msg:
            return win_crash_msg
        
        if return_code != 0:
            return f"程序异常退出 (代码 {return_code})"
        
        return "未知错误"

    @staticmethod
    def _describe_windows_exit_code(return_code: int) -> Optional[str]:
        if sys.platform != "win32":
            return None

                                              
                                                   
        unsigned_code = return_code & 0xFFFFFFFF
        code_map = {
            0xC0000005: "程序崩溃：非法内存访问（0xC0000005）。常见于输入数据异常、数组越界或程序本体缺陷。",
            0xC000001D: "程序崩溃：非法指令（0xC000001D）。可能是可执行文件与当前 CPU/环境不兼容。",
            0xC0000135: "程序启动失败：缺少依赖 DLL（0xC0000135）。",
            0xC0000139: "程序启动失败：入口点不存在（0xC0000139），通常是 DLL 版本不匹配。",
            0xC0000142: "程序启动失败：DLL 初始化失败（0xC0000142）。",
        }

        if unsigned_code in code_map:
            return f"{code_map[unsigned_code]} (代码 {unsigned_code})"
        return None


class AsyncPileEngine:

    
    def __init__(self, engine: Optional[PileEngine] = None):
        self._engine = engine or PileEngine()
        self._thread: Optional[threading.Thread] = None
        self._result: Optional[CalculationResult] = None
        self._on_complete: Optional[Callable[[CalculationResult], None]] = None
        self._on_progress: Optional[Callable[[str], None]] = None
    
    @property
    def engine(self) -> PileEngine:
        return self._engine
    
    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
    
    def run_async(
        self,
        dat_file: str,
        work_dir: Optional[str] = None,
        timeout: Optional[float] = None,
        on_complete: Optional[Callable[[CalculationResult], None]] = None,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> bool:
        if self.is_running:
            logger.warning("计算已在进行中")
            return False
        
        self._on_complete = on_complete
        self._on_progress = on_progress
        self._result = None
        
        if on_progress:
            self._engine.set_progress_callback(on_progress)
        
        self._thread = threading.Thread(
            target=self._run_calculation,
            args=(dat_file, work_dir, timeout),
            daemon=True
        )
        self._thread.start()
        return True
    
    def _run_calculation(
        self,
        dat_file: str,
        work_dir: Optional[str],
        timeout: Optional[float]
    ) -> None:
        try:
            self._result = self._engine.run_calculation(
                dat_file=dat_file,
                work_dir=work_dir,
                timeout=timeout
            )
        except Exception as e:
            self._result = CalculationResult(
                success=False,
                status=EngineStatus.FAILED,
                message=f"计算异常: {e}"
            )
        finally:
            if self._on_complete:
                try:
                    self._on_complete(self._result)
                except Exception:
                    logger.exception("完成回调执行失败")
    
    def cancel(self) -> None:
        self._engine.cancel()
    
    def wait(self, timeout: Optional[float] = None) -> Optional[CalculationResult]:
        if self._thread:
            self._thread.join(timeout=timeout)
        return self._result