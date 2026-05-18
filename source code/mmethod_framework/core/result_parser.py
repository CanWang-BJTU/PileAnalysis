                                                                         
                                       
                                  
                    
                                                                         

from __future__ import annotations
import re
import logging
from typing import Dict, List, Optional, Tuple, Iterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class OutputMode(Enum):
    FULL_ANALYSIS = "full_analysis"
    FOUNDATION_STIFFNESS = "foundation_stiffness"
    SINGLE_PILE_STIFFNESS = "single_pile_stiffness"
    UNKNOWN = "unknown"


                                                                         
         
                                                                         
@dataclass
class Vector6D:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    rx: float = 0.0         
    ry: float = 0.0         
    rz: float = 0.0         
    
    def to_dict(self) -> Dict[str, float]:
        return {
            'x': self. x, 'y': self.y, 'z': self.z,
            'rx': self.rx, 'ry': self. ry, 'rz': self.rz
        }


                                                                         
        
                                                                         
@dataclass
class CapResult:
    displacement: Vector6D = field(default_factory=Vector6D)               


                                                                         
      
                                                                         
@dataclass
class PileTopResult:
    displacement: Vector6D = field(default_factory=Vector6D)               
    force: Vector6D = field(default_factory=Vector6D)                 


                                                                         
           
                                                                         
@dataclass
class PileBodyPoint:
    z: float = 0.0                
    ux: float = 0.0                   
    uy: float = 0.0                   
    sx: float = 0.0                     
    sy: float = 0.0                     
    psx: float = 0.0                       
    psy: float = 0.0                       
    nx: float = 0.0                    
    ny: float = 0.0                    
    nz: float = 0.0                
    mx: float = 0.0                      
    my: float = 0.0                      


                                                                         
        
                                                                         
@dataclass
class PileResult:
    pile_no: int = 0
    x: float = 0.0
    y: float = 0.0
    top: PileTopResult = field(default_factory=PileTopResult)
    body: List[PileBodyPoint] = field(default_factory=list)
    
    def get_z_values(self) -> List[float]:
        return [p.z for p in self.body]
    
    def get_displacements(self) -> Tuple[List[float], List[float]]:
        return ([p.ux for p in self.body], [p.uy for p in self.body])
    
    def get_forces(self) -> Tuple[List[float], List[float], List[float]]:
        return (
            [p.nx for p in self.body],
            [p.ny for p in self. body],
            [p.nz for p in self.body]
        )
    
    def get_moments(self) -> Tuple[List[float], List[float]]:
        return ([p.mx for p in self.body], [p. my for p in self.body])


                                                                         
          
                                                                         
@dataclass
class Matrix6x6:
    data: List[List[float]] = field(default_factory=lambda: [[0.0]*6 for _ in range(6)])
    
    def __getitem__(self, key: Tuple[int, int]) -> float:
        i, j = key
        return self.data[i][j]
    
    def __setitem__(self, key: Tuple[int, int], value: float) -> None:
        i, j = key
        self.data[i][j] = value
    
    def to_numpy(self):
        try:
            import numpy as np
            return np.array(self.data)
        except ImportError:
            raise ImportError("需要安装numpy: pip install numpy")
    
    def multiply_vector(self, vec: List[float]) -> List[float]:
        if len(vec) != 6:
            raise ValueError(f"向量维度必须为6，当前为{len(vec)}")
        
        result = [0.0] * 6
        for i in range(6):
            for j in range(6):
                result[i] += self.data[i][j] * vec[j]
        return result
    
    def to_string(self, precision: int = 4) -> str:
        lines = []
        fmt = f"{{:12.{precision}E}}"
        for row in self.data:
            lines.append("  ".join(fmt.format(v) for v in row))
        return "\n".join(lines)


                                                                         
      
                                                                         
@dataclass
class AnalysisCase:
    case_id: int = 1
    cap_result: Optional[CapResult] = None
    pile_results: List[PileResult] = field(default_factory=list)

                                                                         
       
                                                                         
class ResultParser:
    
                
    SCI_NUMBER = r'[+-]?(?:\d+\.\d*|\.\d+)[Ee][+-]?\d+'                   
    FLOAT_NUMBER = r'[+-]?\d+\.?\d*'
    ANY_NUMBER = rf'(?:{SCI_NUMBER}|{FLOAT_NUMBER})'
    
    def __init__(self):
        self._reset()
    
    def _reset(self) -> None:

        self.raw_output: str = ""
        self.mode: OutputMode = OutputMode.UNKNOWN
        self.stiffness_matrix: Optional[Matrix6x6] = None
        self.single_pile_no: Optional[int] = None
        self.cases: List[AnalysisCase] = []
        self._parse_errors: List[str] = []
        
                                                       
        self._current_case_index: int = 0

    @property
    def cap_result(self) -> Optional[CapResult]:

        if self.cases and 0 <= self._current_case_index < len(self.cases):
            return self.cases[self._current_case_index].cap_result
        return None

    @property
    def pile_results(self) -> List[PileResult]:

        if self.cases and 0 <= self._current_case_index < len(self.cases):
            return self.cases[self._current_case_index].pile_results
        return []
    
    @property
    def parse_errors(self) -> List[str]:

        return self._parse_errors.copy()
    
    def parse_out_file(self, filepath: str) -> bool:

        self._reset()
        
        path = Path(filepath)
        if not path.exists():
            self._parse_errors.append(f"文件不存在: {filepath}")
            return False
        
        try:
                    
            for encoding in ['utf-8', 'gbk', 'latin-1']:
                try:
                    self.raw_output = path.read_text(encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                self._parse_errors.append("无法解码文件内容")
                return False
                
        except Exception as e:
            self._parse_errors.append(f"读取文件失败: {e}")
            return False
        
                 
        self._identify_mode()
        
        if self.mode == OutputMode.FOUNDATION_STIFFNESS or self.mode == OutputMode.SINGLE_PILE_STIFFNESS:
                                    
            success = self._parse_stiffness_matrix()
            if not success:
                self._parse_errors.append("解析刚度矩阵失败")
                return False
        elif self.mode == OutputMode.FULL_ANALYSIS:
                                 
            self._parse_full_analysis_multi_case()
        
        return True
    
    def _identify_mode(self) -> None:

                             
        if 'Stiffness of the entire pile foundation' in self.raw_output:
                           
            self.mode = OutputMode.FOUNDATION_STIFFNESS
        elif 'Stiffness of the No.' in self.raw_output and 'pile ***' in self.raw_output:
                                                                   
            self.mode = OutputMode.SINGLE_PILE_STIFFNESS
                  
            match = re.search(r"Stiffness of the No\.\s*(\d+)", self.raw_output)
            if match:
                self.single_pile_no = int(match.group(1))
        elif 'DISPLACEMENTS AT THE CAP CENTER' in self.raw_output:
                            
            self.mode = OutputMode.FULL_ANALYSIS
        else:
            self.mode = OutputMode.UNKNOWN
            logger.warning(f"无法识别输出模式，请检查输出文件。输出前100字符: {self.raw_output[:100]}")
    
    def _parse_stiffness_matrix(self) -> bool:

                               
        patterns = [
                                                                     
            r'\*\*\*\s*Stiffness of the entire pile foundation\s*\*\*\*\s*\n([\s\S]+?)(?=\n\s*\n|\Z)',
                                                         
            r'\*\*\*\s*Stiffness of the No\.\s*\d+\s*pile\s*\*\*\*\s*\n([\s\S]+?)(?=\n\s*\n|\Z)',
        ]
        
        matrix_text = None
        for pattern in patterns:
            match = re.search(pattern, self.raw_output, re.IGNORECASE)
            if match:
                matrix_text = match.group(1)
                logger.debug(f"找到刚度矩阵文本: {matrix_text[:100]}...")
                break
        
        if not matrix_text:
            logger.warning("未找到刚度矩阵输出")
            return False
        
                
        matrix = Matrix6x6()
        lines = [l.strip() for l in matrix_text.split('\n') if l.strip()]
        
        row_count = 0
        for line in lines:
                                
            numbers = re.findall(self.ANY_NUMBER, line)
            
            if len(numbers) >= 6:
                for j in range(6):
                    try:
                                                           
                        matrix[row_count, j] = float(numbers[j])
                    except (ValueError, IndexError) as e:
                        logger.error(f"解析矩阵元素失败 [{row_count},{j}]: {e}")
                        return False
                
                row_count += 1
                if row_count >= 6:
                    break
        
        if row_count < 6:
            logger.error(f"刚度矩阵行数不足，期望6行，实际{row_count}行")
            return False
        
        self.stiffness_matrix = matrix
        logger.info(f"成功解析 {6}x{6} 刚度矩阵")
        return True

    def _parse_full_analysis_multi_case(self) -> None:

                                                        
                                   
        
        delimiter = "DISPLACEMENTS AT THE CAP CENTER"
        
                  
        indices = [m.start() for m in re.finditer(re.escape(delimiter), self.raw_output)]
        
        if not indices:
            self._parse_errors.append("未找到承台位移标识，无法解析结果")
            return
            
        case_blocks = []
        for i, start_idx in enumerate(indices):
            end_idx = indices[i+1] if i + 1 < len(indices) else len(self.raw_output)
            case_blocks.append(self.raw_output[start_idx:end_idx])
            
        logger.info(f"检测到 {len(case_blocks)} 个工况结果")
        
        for i, block in enumerate(case_blocks):
            case_id = i + 1
            case_result = AnalysisCase(case_id=case_id)
            
                            
            case_result.cap_result = self._parse_cap_displacement_from_text(block)
            
                             
            case_result.pile_results = self._parse_pile_sections_from_text(block)
            
            self.cases.append(case_result)
            logger.info(f"工况 {case_id} 解析完成: 包含 {len(case_result.pile_results)} 根桩")

    def _parse_cap_displacement_from_text(self, text: str) -> Optional[CapResult]:

        cap_result = CapResult()
        
                                              
        cap_section = re.search(
            r'DISPLACEMENTS AT THE CAP CENTER.*?\n\s*\*+\s*\n(.*?)(?=\n\s*\*{10,}|\Z)',
            text,
            re.DOTALL | re.IGNORECASE
        )
        
        if not cap_section:
            return None
        
        cap_text = cap_section.group(1)
        
        patterns = [
            (r'Movement.*?X\s*axis\s*:\s*UX\s*=\s*(' + self.SCI_NUMBER + r')', 'x'),
            (r'Movement.*?Y\s*axis\s*:\s*UY\s*=\s*(' + self.SCI_NUMBER + r')', 'y'),
            (r'Movement.*?Z\s*axis\s*:\s*UZ\s*=\s*(' + self.SCI_NUMBER + r')', 'z'),
            (r'Rotational.*?angle.*?X\s*axis\s*:\s*SX\s*=\s*(' + self.SCI_NUMBER + r')', 'rx'),
            (r'Rotational.*?angle.*?Y\s*axis\s*:\s*SY\s*=\s*(' + self.SCI_NUMBER + r')', 'ry'),
            (r'Rotational.*?angle.*?Z\s*axis\s*:\s*SZ\s*=\s*(' + self.SCI_NUMBER + r')', 'rz'),
        ]
        
        for pattern, attr in patterns:
            match = re.search(pattern, cap_text, re.IGNORECASE | re.DOTALL)
            if match:
                try:
                    value = float(match.group(1))
                    setattr(cap_result.displacement, attr, value)
                except (ValueError, AttributeError):
                    pass
        return cap_result
    
    def _parse_pile_sections_from_text(self, text: str) -> List[PileResult]:

        results = []
        
                   
                                                    
        pile_pattern = r'\*{10,}\s*\n.*?NO\.\s+(\d+)\s*#\s*PILE.*?\n\s*\*{10,}\s*\n(.*?)(?=\n\s*\*{10,}.*?NO\.\s+\d+\s*#\s*PILE|\Z)'
        pile_sections = re.finditer(pile_pattern, text, re.DOTALL | re.IGNORECASE)
        
        for match in pile_sections:
            pile_no = int(match.group(1))
            pile_text = match.group(2)
            
            pile_result = PileResult(pile_no=pile_no)
            
                     
            coord_match = re.search(
                rf'Coordinator.*?:\s*\(x\s*,\s*y\)\s*=\s*\(\s*({self.SCI_NUMBER})\s*,\s*({self.SCI_NUMBER})\s*\)',
                pile_text,
                re.IGNORECASE
            )
            if coord_match:
                pile_result.x = float(coord_match.group(1))
                pile_result.y = float(coord_match.group(2))
            
                       
            top_patterns = [
                (r'UX\s*=\s*(' + self.SCI_NUMBER + r')', 'displacement', 'x'),
                (r'UY\s*=\s*(' + self.SCI_NUMBER + r')', 'displacement', 'y'),
                (r'UZ\s*=\s*(' + self.SCI_NUMBER + r')', 'displacement', 'z'),
                (r'SX\s*=\s*(' + self.SCI_NUMBER + r')', 'displacement', 'rx'),
                (r'SY\s*=\s*(' + self.SCI_NUMBER + r')', 'displacement', 'ry'),
                (r'SZ\s*=\s*(' + self.SCI_NUMBER + r')', 'displacement', 'rz'),
                (r'NX\s*=\s*(' + self.SCI_NUMBER + r')', 'force', 'x'),
                (r'NY\s*=\s*(' + self.SCI_NUMBER + r')', 'force', 'y'),
                (r'NZ\s*=\s*(' + self.SCI_NUMBER + r')', 'force', 'z'),
                (r'MX\s*=\s*(' + self.SCI_NUMBER + r')', 'force', 'rx'),
                (r'MY\s*=\s*(' + self.SCI_NUMBER + r')', 'force', 'ry'),
                (r'MZ\s*=\s*(' + self.SCI_NUMBER + r')', 'force', 'rz'),
            ]
            
                      
            top_section = re.search(
                r'Displacements and internal forces at the top of pile\s*:(.*?)(?=%{5}|\Z)',
                pile_text,
                re.DOTALL | re.IGNORECASE
            )
            
            if top_section:
                top_text = top_section.group(1)
                for pattern, vector_type, attr in top_patterns:
                    match = re.search(pattern, top_text)
                    if match:
                        try:
                            value = float(match.group(1))
                            if vector_type == 'displacement':
                                setattr(pile_result.top.displacement, attr, value)
                            else:         
                                setattr(pile_result.top.force, attr, value)
                        except (ValueError, AttributeError):
                            continue
            
                      
            disp_section = re.search(
                r'Displacements of the pile body.*?%{5,}\s*\n.*?Z\s+UX\s+UY.*?\n.*?\(m\).*?\n(.*?)(?=%{5}|\Z)',
                pile_text,
                re.DOTALL | re.IGNORECASE
            )
            
            body_displacements = {}
            if disp_section:
                disp_lines = disp_section.group(1).strip().split('\n')
                for line in disp_lines:
                    numbers = re.findall(self.ANY_NUMBER, line)
                    if len(numbers) >= 5:
                        try:
                            z = float(numbers[0])
                            ux = float(numbers[1])
                            uy = float(numbers[2])
                            sx = float(numbers[3])
                            sy = float(numbers[4])
                            psx = float(numbers[5]) if len(numbers) > 5 else 0.0
                            psy = float(numbers[6]) if len(numbers) > 6 else 0.0
                            body_displacements[z] = (ux, uy, sx, sy, psx, psy)
                        except (ValueError, IndexError):
                            continue
            
                      
            force_section = re.search(
                r'Internal forces of the pile body.*?%{5,}\s*\n.*?Z\s+NX\s+NY.*?\n.*?\(m\).*?\n(.*?)(?=\*{10}|\Z)',
                pile_text,
                re.DOTALL | re.IGNORECASE
            )
            
            body_forces = {}
            if force_section:
                force_lines = force_section.group(1).strip().split('\n')
                for line in force_lines:
                    numbers = re.findall(self.ANY_NUMBER, line)
                    if len(numbers) >= 6:
                        try:
                            z = float(numbers[0])
                            nx = float(numbers[1])
                            ny = float(numbers[2])
                            nz = float(numbers[3])
                            mx = float(numbers[4])
                            my = float(numbers[5])
                            body_forces[z] = (nx, ny, nz, mx, my)
                        except (ValueError, IndexError):
                            continue
            
                  
            all_z = sorted(set(body_displacements.keys()) | set(body_forces.keys()))
            for z in all_z:
                point = PileBodyPoint(z=z)
                if z in body_displacements:
                    ux, uy, sx, sy, psx, psy = body_displacements[z]
                    point.ux = ux
                    point.uy = uy
                    point.sx = sx
                    point.sy = sy
                    point.psx = psx
                    point.psy = psy
                if z in body_forces:
                    nx, ny, nz, mx, my = body_forces[z]
                    point.nx = nx
                    point.ny = ny
                    point.nz = nz
                    point.mx = mx
                    point.my = my
                pile_result.body.append(point)
            
            results.append(pile_result)
        return results