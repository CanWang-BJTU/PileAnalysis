                      
                                                                         
                                              
                     
                                                                         
from __future__ import annotations
from typing import Dict, List, Any, Optional, TextIO, Tuple
from dataclasses import dataclass, field
from enum import IntEnum
import math
import logging
import re

logger = logging.getLogger(__name__)

                                                                         
      
                                                                         
class CalculationMode(IntEnum):
    FULL_ANALYSIS = 1            
    FOUNDATION_STIFFNESS = 2         
    SINGLE_PILE_STIFFNESS = 3         


class PileShape(IntEnum):
    CIRCULAR = 0
    SQUARE = 1


class PileSupportType(IntEnum):
    FRICTION_50 = 1              
    FRICTION_67 = 2                
    END_BEARING = 3        
    HINGED = 4            

                                                                         
       
                                                                         
@dataclass
class FreeSegment:
    height: float              
    diameter: float               
    subdivisions: int       
    
    def validate(self) -> None:
        if self.height <= 0: raise ValueError(f"自由段高度必须为正: {self.height}")
        if self.diameter <= 0: raise ValueError(f"自由段直径必须为正: {self.diameter}")
        if self.subdivisions < 1: raise ValueError(f"分段数必须≥1: {self.subdivisions}")


@dataclass
class EmbeddedSegment:
    height: float                 
    diameter: float                  
    soil_modulus: float                   
    friction_angle: float           
    subdivisions: int          
    
    def validate(self) -> None:
        if self.height <= 0: raise ValueError(f"土层厚度必须为正: {self.height}")
        if self.diameter <= 0: raise ValueError(f"土层处直径必须为正: {self.diameter}")
        if self.soil_modulus <= 0: raise ValueError(f"土的 m 值必须为正: {self.soil_modulus}")
        if not (0 <= self.friction_angle <= 45):
            logger.warning(f"内摩擦角 {self.friction_angle}° 超出常规范围 [0, 45]")
        if self.subdivisions < 1: raise ValueError(f"分段数必须≥1: {self.subdivisions}")


@dataclass
class PileTypeParams:
    name: str
    shape: PileShape = PileShape.CIRCULAR
    support_type: PileSupportType = PileSupportType.FRICTION_50
    direction_cosines: tuple = (0.0, 0.0, 1.0)
    elastic_modulus: float = 3.0e7
    stiffness_factor: float = 1.0
    base_soil_modulus: float = 15000.0
    free_segments: List[FreeSegment] = field(default_factory=list)
    embedded_segments: List[EmbeddedSegment] = field(default_factory=list)
    
                                    
    base_type_name: Optional[str] = None
    differential_params: Optional[List[Tuple[str, int, float]]] = None                             
    
    def validate(self) -> None:
        ax, ay, az = self.direction_cosines
        norm = math.sqrt(ax**2 + ay**2 + az**2)
        if abs(norm - 1.0) > 1e-6:
            raise ValueError(f"方向余弦必须满足 α²+β²+γ²=1，当前={norm:.6f}")
        
        if self.elastic_modulus <= 0: raise ValueError(f"弹性模量必须为正: {self.elastic_modulus}")
        if not (0 < self.stiffness_factor <= 2.0):
            raise ValueError(f"惯性矩修正系数应在 (0, 2] 范围: {self.stiffness_factor}")
        if self.base_soil_modulus <= 0: raise ValueError(f"桩底地基系数必须为正: {self.base_soil_modulus}")
        
                                  
                        
        
        for seg in self.free_segments: seg.validate()
        for seg in self.embedded_segments: seg.validate()


@dataclass
class PilePosition:
    number: int
    x: float
    y: float
    type_name: str


@dataclass
class LoadCase:
    x: float = 0.0
    y: float = 0.0
    fx: float = 0.0
    fy: float = 0.0
    fz: float = 0.0
    mx: float = 0.0
    my: float = 0.0
    mz: float = 0.0


@dataclass  
class SimulativePile:

    x: float
    y: float
    control_id: int
    stiffness_diagonal: Optional[List[float]] = None
    stiffness_matrix: Optional[List[List[float]]] = None

                                                                         
          
                                                                         
class DATGenerator:
    
    MAX_PILES = 300
    MAX_SIMULATIVE_PILES = 20
    MAX_SEGMENTS = 15
    
    def __init__(self):
        self._reset()
    
    def _reset(self) -> None:

        self.mode: CalculationMode = CalculationMode.FULL_ANALYSIS
        self.single_pile_index: int = 1
        self.pile_types: Dict[str, PileTypeParams] = {}
        self.piles: List[PilePosition] = []
        self.load_cases: List[LoadCase] = []
        self.simulative_piles: List[SimulativePile] = []
        

        self.cap_length = 0.0
        self.cap_width = 0.0
        self.cap_thickness = 0.0
        self.soil_coef_h = 0.0
        self.soil_coef_v = 0.0
        
        self.displacements = [0.0] * 6                                      
        
    def configure(
        self,
        mode: CalculationMode,
        pile_types: Dict[str, PileTypeParams],
        piles: List[PilePosition],
        load_cases: Optional[List[LoadCase]] = None,
        single_pile_index: int = 1,
        simulative_piles: Optional[List[SimulativePile]] = None
    ) -> 'DATGenerator':

        self._reset()
        
        self.mode = mode
        self.single_pile_index = single_pile_index
        self.pile_types = pile_types
        self.piles = piles
        self.load_cases = load_cases or []
        self.simulative_piles = simulative_piles or []
        
        return self
    
    def generate_from_gui_data(self, gui_data: Dict[str, Any], filename: str, skip_validation: bool = False) -> bool:
        self._reset()
        


        gui_mode = gui_data.get('mode', 0)
        mode_mapping = {
            0: CalculationMode.FOUNDATION_STIFFNESS,
            1: CalculationMode.SINGLE_PILE_STIFFNESS,
            2: CalculationMode.FULL_ANALYSIS
        }
        self.mode = mode_mapping.get(gui_mode, CalculationMode.FOUNDATION_STIFFNESS)
        self.single_pile_index = int(gui_data.get('calc_pile_no', 1))
        
                                                          

        raw_types = gui_data.get('pile_types', {})
        for name, params in raw_types.items():
            pile_type = self._convert_pile_type(name, params)
            self.pile_types[name] = pile_type
        

        cap_data = gui_data.get('cap', {})
        self.cap_length = float(cap_data.get('length', 10.0))
        self.cap_width = float(cap_data.get('width', 8.0))
        self.cap_thickness = float(cap_data.get('thickness', 2.0))
        self.soil_coef_h = float(cap_data.get('soil_coef_h', 0.0))
        self.soil_coef_v = float(cap_data.get('soil_coef_v', 0.0))
        

        raw_piles = gui_data.get('piles', [])
        for p in raw_piles:
            self.piles.append(PilePosition(
                number=int(p.get('no', len(self.piles) + 1)),
                x=float(p.get('x', 0)),
                y=float(p.get('y', 0)),
                type_name=str(p.get('type', ''))
            ))
        




        raw_simulative = gui_data.get('simulative_piles', [])
        
                         
        unique_stiffness_map = {}                                     
        next_neg_id = -1                   
        next_pos_id = 1                   
        
        for sp_data in raw_simulative:
                    
            pile_type = sp_data.get('type', 'diagonal')
            is_matrix_type = pile_type == 'matrix'
            
                    
            stiffness_diagonal = None
            stiffness_matrix = None
            
            if is_matrix_type:
                       
                raw_matrix = sp_data.get('stiffness_matrix')
                if raw_matrix and isinstance(raw_matrix, list) and len(raw_matrix) >= 6:
                    stiffness_matrix = []
                    for row in raw_matrix[:6]:
                        if isinstance(row, list):
                            stiffness_matrix.append([float(x) for x in (row + [0.0]*6)[:6]])
                        else:
                            stiffness_matrix.append([0.0] * 6)
                                  
                    stiffness_diagonal = [stiffness_matrix[i][i] for i in range(6)]
                else:
                                   
                    stiffness_matrix = [[0.0]*6 for _ in range(6)]
                    stiffness_diagonal = [0.0] * 6
                    
                stiff_key = ('matrix', tuple(tuple(row) for row in stiffness_matrix))
            else:
                       
                raw_diag = sp_data.get('stiffness_diagonal') or sp_data.get('stiffness', [])
                if isinstance(raw_diag, list) and len(raw_diag) > 0:
                    if isinstance(raw_diag[0], list):
                                        
                        stiffness_diagonal = [raw_diag[i][i] if i < len(raw_diag) and i < len(raw_diag[i]) else 0.0 for i in range(6)]
                    else:
                        stiffness_diagonal = [float(x) for x in (raw_diag + [0.0]*6)[:6]]
                else:
                    stiffness_diagonal = [0.0] * 6
                    
                stiff_key = ('diagonal', tuple(stiffness_diagonal))
            
                                      
            original_control_id = sp_data.get('control_id')
            
                           
            if original_control_id is not None and original_control_id != 0:
                        
                control_id = original_control_id
            elif stiff_key in unique_stiffness_map:
                          
                control_id = unique_stiffness_map[stiff_key]
            elif is_matrix_type:
                          
                control_id = next_pos_id
                unique_stiffness_map[stiff_key] = control_id
                next_pos_id += 1
            else:
                          
                control_id = next_neg_id
                unique_stiffness_map[stiff_key] = control_id
                next_neg_id -= 1
            
                     
            sp = SimulativePile(
                x=float(sp_data.get('x', 0.0)),
                y=float(sp_data.get('y', 0.0)),
                control_id=control_id,
                stiffness_diagonal=stiffness_diagonal,
                stiffness_matrix=stiffness_matrix
            )
            self.simulative_piles.append(sp)

                                   

                      
        load_cases_raw = gui_data.get('load_cases', [])
        if not load_cases_raw:
                                
            raw_loads = gui_data.get('loads', {})
            if raw_loads:
                load_cases_raw = [raw_loads]
        
        if self.mode == CalculationMode.FULL_ANALYSIS:
            self.load_cases = []
            for lc in load_cases_raw:
                load_case = LoadCase(
                    x=float(lc.get('x', 0.0)),
                    y=float(lc.get('y', 0.0)),
                    fx=float(lc.get('fx', 0)),
                    fy=float(lc.get('fy', 0)),
                    fz=float(lc.get('fz', 0)),
                    mx=float(lc.get('mx', 0)),
                    my=float(lc.get('my', 0)),
                    mz=float(lc.get('mz', 0))
                )
                self.load_cases.append(load_case)
            
                       
            if not self.load_cases:
                self.load_cases = [LoadCase(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)]
        

                    
        raw_disps = gui_data.get('displacements', gui_data.get('disps', {}))
        self.displacements = [
            float(raw_disps.get('ux', 0)),
            float(raw_disps.get('uy', 0)),
            float(raw_disps.get('uz', 0)),
            float(raw_disps.get('thetax', 0)),
            float(raw_disps.get('thetay', 0)),
            float(raw_disps.get('thetaz', 0))
        ]
        

               
        if not skip_validation:
            self._validate()
        return self._write_file(filename)
    
    def _convert_pile_type(self, name: str, params: Dict) -> PileTypeParams:
        
                                                                                                
        is_diff = params.get('is_differential', False) or params.get('_original_differential', False)
        base_type = params.get('base_type')
        diff_params = params.get('differential_params') or params.get('_differential_params')
        
        if diff_params is not None or is_diff:
                             
            return PileTypeParams(
                name=name,
                base_type_name=base_type or '类型0',
                differential_params=diff_params if diff_params else []
            )
        
              
        angle = params.get('angle', [0, 0, 1])
        if len(angle) >= 3:
            direction_cosines = (float(angle[0]), float(angle[1]), float(angle[2]))
        else:
            direction_cosines = (0.0, 0.0, 1.0)
        
        norm = math.sqrt(sum(x**2 for x in direction_cosines))
        if norm > 1e-10:
            direction_cosines = tuple(x / norm for x in direction_cosines)
        else:
            direction_cosines = (0.0, 0.0, 1.0)
        

             
        free_segments = []
        for item in params.get('above_ground', []):
            if len(item) >= 3:
                free_segments.append(FreeSegment(
                    height=float(item[0]),
                    diameter=float(item[1]),
                    subdivisions=int(item[2])
                ))
        
             
        embedded_segments = []
        for item in params.get('below_ground', []):
            if len(item) >= 5:
                embedded_segments.append(EmbeddedSegment(
                    height=float(item[0]),
                    diameter=float(item[1]),
                    soil_modulus=float(item[2]),
                    friction_angle=float(item[3]),
                    subdivisions=int(item[4])
                ))
        
        return PileTypeParams(
            name=name,
            shape=PileShape(int(params.get('ksh', 0))),
            support_type=PileSupportType(int(params.get('ksu', 4))),
            direction_cosines=direction_cosines,
            elastic_modulus=float(params.get('elastic_modulus', params.get('peh', 3.0e7))),
            stiffness_factor=float(params.get('stiffness_factor', params.get('pke', 1.0))),
            base_soil_modulus=float(params.get('base_modulus', params.get('pmb', 1.5e4))),
            free_segments=free_segments,
            embedded_segments=embedded_segments
        )
    
    def _validate(self) -> None:

        if len(self.piles) > self.MAX_PILES:
            raise ValueError(f"桩数量超过限制: {len(self.piles)} > {self.MAX_PILES}")
        if len(self.simulative_piles) > self.MAX_SIMULATIVE_PILES:
            raise ValueError(f"模拟桩数量超过限制: {len(self.simulative_piles)} > {self.MAX_SIMULATIVE_PILES}")
        
        if not self.piles: raise ValueError("至少需要定义一根桩")
        if not self.pile_types: raise ValueError("至少需要定义一种桩类型")
        
                                
        for pile in self.piles:
            tname = pile.type_name
                               
            try:
                int(str(tname))
                                   
                if str(tname) not in self.pile_types and tname not in self.pile_types:
                    raise ValueError(f"桩 {pile.number} 引用了未定义的类型ID: '{tname}'")
            except ValueError:
                            
                if tname not in self.pile_types:
                    raise ValueError(f"桩 {pile.number} 引用了未定义的类型: '{tname}'")
        
        if self.mode == CalculationMode.FULL_ANALYSIS and not self.load_cases:
            raise ValueError("完整分析模式 (JCTR=1) 需要定义荷载工况")
        
        if self.mode == CalculationMode.SINGLE_PILE_STIFFNESS:
            if not (1 <= self.single_pile_index <= len(self.piles)):
                raise ValueError(f"单桩计算桩号 {self.single_pile_index} 超出范围")
        
        for name, pile_type in self.pile_types.items():
                                  
            if pile_type.differential_params is not None:
                continue
            try:
                pile_type.validate()
            except ValueError as e:
                raise ValueError(f"桩类型 '{name}' 参数错误: {e}")
            
            if len(pile_type.free_segments) > self.MAX_SEGMENTS:
                raise ValueError(f"桩类型 '{name}' 自由段数量超过限制")
            if len(pile_type.embedded_segments) > self.MAX_SEGMENTS:
                raise ValueError(f"桩类型 '{name}' 土层数量超过限制")
    


    
    def _write_file(self, filename: str) -> bool:

        try:
            with open(filename, 'w', encoding='ascii', newline='\r\n') as f:
                self._write_control_block(f)
                self._write_arrange_block(f)
                self._write_nosimu_block(f)
                self._write_simupile_block(f)
                self._write_disp_block(f)

            logger.info(f"成功生成输入文件: {filename}")
            return True
        except Exception as e:
            logger.error(f"写入文件失败: {e}")
            raise
    
    def _write_control_block(self, f: TextIO) -> None:

        f.write("[CONTRAL]\n")
        f.write(f" {self.mode.value}\n")
        
        if self.mode == CalculationMode.FULL_ANALYSIS:
            nact = len(self.load_cases)
            f.write(f" {nact}\n")
            for load in self.load_cases:
                f.write(f" {load.x:.6E}  {load.y:.6E}\n")
                f.write(f" {load.fx:.6E}  {load.fy:.6E}  {load.fz:.6E}  ")
                f.write(f"{load.mx:.6E}  {load.my:.6E}  {load.mz:.6E}\n")
        
        elif self.mode == CalculationMode.SINGLE_PILE_STIFFNESS:
            f.write(f" {self.single_pile_index}\n")
        
        f.write("END;\n")
    
    def _write_arrange_block(self, f: TextIO) -> None:

        f.write("[ARRANGE]\n")
        
        pnum = len(self.piles)
        snum = len(self.simulative_piles)
        f.write(f" {pnum}  {snum}\n")
        
                           
        for pile in self.piles:
            f.write(f" {pile.x:.6E}  {pile.y:.6E}\n")
        
                           
        if snum > 0:
            for sp in self.simulative_piles:
                f.write(f" {sp.x:.6E}  {sp.y:.6E}\n")
        
        f.write("END;\n")
    
    def _write_nosimu_block(self, f: TextIO) -> None:

        f.write("[NO_SIMU]\n")
        
        type_names = list(self.pile_types.keys())
        
                                     
                                                                                              
                                                          
                                                           
                                       
        
                                       
        type_to_id = {}
        for idx, name in enumerate(type_names):
                                           
            try:
                explicit_id = int(name)
            except Exception:
                explicit_id = None

            if explicit_id is not None:
                type_to_id[name] = explicit_id
                continue
            
                            
            match = re.match(r'类型([+-]?\d+)', name)
            if match:
                type_id = int(match.group(1))
                type_to_id[name] = type_id
                continue

            if idx == 0:
                type_to_id[name] = 0
            else:
                                                                    
                pt = self.pile_types[name]
                is_diff = bool(pt.base_type_name) or bool(pt.differential_params)
                type_to_id[name] = -idx if is_diff else idx

                                                  
        kctr_values = []
        for p in self.piles:
            tname = p.type_name
                      
            if isinstance(tname, int):
                kctr_values.append(str(tname))
                continue
                        
            try:
                k = int(str(tname))
                kctr_values.append(str(k))
                continue
            except Exception:
                pass

                        
            if tname in type_to_id:
                kctr_values.append(str(type_to_id[tname]))
            else:
                                  
                logger.warning(f"未知桩类型名 '{tname}'，将其写为 0")
                kctr_values.append('0')
        for i in range(0, len(kctr_values), 20):
            f.write(" " + "  ".join(kctr_values[i:i+20]) + "\n")
        
                         
                          
                          
                                                       
        
                          
        base_type_name = None
        for name, id_val in type_to_id.items():
            if id_val == 0:
                base_type_name = name
                break
        
                                          
        if base_type_name is None:
            for name, id_val in type_to_id.items():
                if id_val >= 0:
                    type_to_id[name] = 0
                    base_type_name = name
                    break
        
                
        if base_type_name is None:
            raise ValueError("必须定义至少一个基类型（ID >= 0）")
        
                       
        f.write("<0>\n")
        self._write_pile_type_params(f, self.pile_types[base_type_name])
        
                        
        other_ids = sorted([tid for tid in set(type_to_id.values()) if tid != 0])
        
        for tid in other_ids:
                           
            type_name = None
            for name, id_val in type_to_id.items():
                if id_val == tid:
                    type_name = name
                    break
            
            if type_name is None:
                continue
                
            pt = self.pile_types[type_name]
            
            if tid > 0:
                           
                f.write(f"<{tid}>\n")
                self._write_pile_type_params(f, pt)
            else:
                            
                f.write(f"<{tid}>\n")
                self._write_differential_type(f, pt)
        
        f.write("END;\n")
    
    def _write_differential_type(self, f: TextIO, pt: PileTypeParams) -> None:

                         
                                   
        if not pt.differential_params:
            f.write(" 0\n")
            return
            
        f.write(f" {len(pt.differential_params)}\n")
                                                            
                           
        for key, idx, val in pt.differential_params:
            if abs(val) < 1e-6:
                val_str = "0.0"
            elif abs(val) >= 1e4 or abs(val) < 1e-2:
                val_str = f"{val:.4E}"
            else:
                val_str = f"{val:.4f}"
            
                                                                                            
                                                  
            f.write(f" '{key}'  {idx}  {val_str}\n")
    
    def _write_pile_type_params(self, f: TextIO, pt: PileTypeParams) -> None:

        ax, ay, az = pt.direction_cosines
        
        f.write(f" {pt.shape.value}  {pt.support_type.value}  ")
        f.write(f"{ax:.6E}  {ay:.6E}  {az:.6E}\n")
        
        nfr = len(pt.free_segments)
        f.write(f" {nfr}")
        if nfr == 0:
            f.write("\n")
        else:
            for i, seg in enumerate(pt.free_segments):
                if i == 0:
                    f.write(f"  {seg.height:.2f}  {seg.diameter:.2f}  {seg.subdivisions}\n")
                else:
                    f.write(f"        {seg.height:.2f}  {seg.diameter:.2f}  {seg.subdivisions}\n")
        
        nbl = len(pt.embedded_segments)
        f.write(f" {nbl}\n")
        for i, seg in enumerate(pt.embedded_segments):
            if i == 0:
                f.write(f"  {seg.height:.2f}  {seg.diameter:.2f}  ")
                f.write(f"{seg.soil_modulus:.0f}  {seg.friction_angle:.1f}  {seg.subdivisions}\n")
            else:
                f.write(f"        {seg.height:.2f}  {seg.diameter:.2f}  ")
                f.write(f"{seg.soil_modulus:.0f}  {seg.friction_angle:.1f}  {seg.subdivisions}\n")
        
        f.write(f" {pt.base_soil_modulus:.6E}  {pt.elastic_modulus:.6E}  {pt.stiffness_factor:.6E}\n")
    
    def _write_simupile_block(self, f: TextIO) -> None:
        f.write("[SIMU_PE]\n")
        
        snum = len(self.simulative_piles)
        if snum == 0:
            f.write("END;\n")
            return
        
        ksctr_values = [str(sp.control_id) for sp in self.simulative_piles]
        f.write(" " + "  ".join(ksctr_values) + "\n")
        
        unique_ids = sorted(set(sp.control_id for sp in self.simulative_piles))
        for cid in unique_ids:
            sp = next(s for s in self.simulative_piles if s.control_id == cid)
            
            if cid < 0:
                f.write(f"<{cid}>\n")              
                if sp.stiffness_diagonal:
                    vals = " ".join(f"{v:.6E}" for v in sp.stiffness_diagonal)
                    f.write(f" {vals}\n")
            else:
                f.write(f"<+{cid}>\n")               
                if sp.stiffness_matrix:
                    for row in sp.stiffness_matrix:
                        vals = " ".join(f"{v:.6E}" for v in row)
                        f.write(f" {vals}\n")
        
        f.write("END;\n")
    
    def _write_disp_block(self, f: TextIO) -> None:
                                               
        if all(abs(x) < 1e-9 for x in self.displacements):
            return
            
        f.write("[DISP]\n")
        vals = "  ".join(f"{v:.6E}" for v in self.displacements)
        f.write(f" {vals}\n")
        f.write("END;\n")




                                                                         
      
                                                                         
def create_dat_file(
    filename: str,
    mode: CalculationMode,
    pile_types: Dict[str, PileTypeParams],
    piles: List[PilePosition],
    load_cases: Optional[List[LoadCase]] = None,
    single_pile_index: int = 1,
    simulative_piles: Optional[List[SimulativePile]] = None
) -> bool:
    generator = DATGenerator()
    generator.configure(
        mode=mode,
        pile_types=pile_types,
        piles=piles,
        load_cases=load_cases,
        single_pile_index=single_pile_index,
        simulative_piles=simulative_piles
    )
    return generator._write_file(filename)