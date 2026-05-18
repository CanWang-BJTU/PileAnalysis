                      
                                                                         
                           
                                
                     
                                                                         
import re
from typing import Dict, List, Any, Optional
from pathlib import Path

                                                                         
        
                                                                         
class DATParser:

    
    def __init__(self):
        self.mode = 0
        self.piles = []
        self.pile_types = {}
        self.simulative_piles = []
        self.simulative_piles = []
        self.snum = 0         
        self.single_pile_index = 1

        
    def parse_file(self, dat_file: str) -> Dict[str, Any]:

        with open(dat_file, 'r', encoding='utf-8') as f:
            content = f.read()
        


        self._parse_control_block(content)
        arrange_piles, simu_piles = self._parse_arrange_block(content)
        type_assignments = self._parse_no_simu_block(content)
        self._parse_pile_types(content)
        loads_data = self._parse_load_block(content)
        disps_data = self._parse_disp_block(content)

        simu_data = self._parse_simupile_block(content)

        

        self._expand_differential_types()
        


        

        self.piles = []
        for i, (x, y) in enumerate(arrange_piles):
            type_id = type_assignments[i]
            type_name = self._get_type_name(type_id)
            self.piles.append({
                'no': i + 1,
                'x': x,
                'y': y,
                'type': type_name
            })
        


        self.simulative_piles = []
        for i, (x, y) in enumerate(simu_piles):
            simu_pile = {'x': x, 'y': y}
            if i < len(simu_data):
                simu_pile.update(simu_data[i])
            self.simulative_piles.append(simu_pile)

        
                               
        disp_cases = disps_data.get('disp_cases', [])
        is_multi_disp = disps_data.get('is_multi_disp', False)
        
                                   
        if self.mode == 1 and (is_multi_disp or len(disp_cases) > 1):
                              
            reverse_load_cases = []
            ref_coords = getattr(self, 'ref_coords', [])
            
            for i, disp in enumerate(disp_cases):
                case = dict(disp)          
                         
                if i < len(ref_coords):
                    case['x'] = ref_coords[i].get('x', 0.0)
                    case['y'] = ref_coords[i].get('y', 0.0)
                else:
                    case['x'] = 0.0
                    case['y'] = 0.0
                reverse_load_cases.append(case)
            
            loads_data['load_cases'] = reverse_load_cases
            loads_data['is_multi_case'] = len(reverse_load_cases) > 1
        
                
        result = {
            'mode': self.mode,
            'mode': self.mode,
            'calc_pile_no': self.single_pile_index,
            'piles': self.piles,

            'piles': self.piles,
            'pile_types': self.pile_types,
            'cap': {},
            'loads': loads_data,         
            'load_cases': loads_data.get('load_cases', []),         
            'is_multi_case': loads_data.get('is_multi_case', False),
            'disps': disps_data,
            'simulative_piles': self.simulative_piles,
            'has_simulative': self.snum > 0
        }
        
        return result
    
    def _parse_control_block(self, content: str):

        match = re.search(r'\[CONTRAL\](.+?)END;', content, re.DOTALL | re.IGNORECASE)
        if match:
            block_content = match.group(1).strip()
            lines = [l.strip() for l in block_content.split('\n') if l.strip()]
            
            if len(lines) >= 1:
                jctr = int(lines[0].split()[0])
                if jctr == 1:
                    self.mode = 2                         
                elif jctr == 2:
                    self.mode = 0                               
                elif jctr == 3:
                    self.mode = 1                                
            
                                 
            self.nact = 1         
            self.ref_coords = []           
            self.single_pile_index = 1
            
            if len(lines) >= 2:
                try:
                    val = int(lines[1].split()[0])
                    if self.mode == 1:
                        self.single_pile_index = val
                    else:
                        self.nact = val
                except ValueError:
                    if self.mode == 1:
                        self.single_pile_index = 1
                    else:
                        self.nact = 1
                
                                                            
                                                    
                has_load_data = False
                if len(lines) >= 4 and self.nact >= 1:
                    potential_load_line = lines[3]
                    parts = potential_load_line.split()
                    if len(parts) >= 6:
                        try:
                                                     
                            test_vals = [float(p) for p in parts[:6]]
                                                     
                            if any(abs(v) > 1 for v in test_vals):
                                has_load_data = True
                        except ValueError:
                            pass
                
                         
                line_idx = 2
                for _ in range(self.nact):
                    if line_idx < len(lines):
                        coord_parts = lines[line_idx].split()
                        if len(coord_parts) >= 2:
                            try:
                                x = float(coord_parts[0])
                                y = float(coord_parts[1])
                                self.ref_coords.append({'x': x, 'y': y})
                            except ValueError:
                                self.ref_coords.append({'x': 0.0, 'y': 0.0})
                        line_idx += 2 if has_load_data else 1                   
    
    def _parse_arrange_block(self, content: str) -> tuple:

        arrange_match = re.search(r'\[ARRANGE\](.+?)END;', content, re.DOTALL | re.IGNORECASE)
        if not arrange_match:
            return [], []
        
        arrange_text = arrange_match.group(1)
        lines = arrange_text.strip().split('\n')
        
                   
        first_line = lines[0].strip().split()
        pnum = int(first_line[0])
        snum = int(first_line[1]) if len(first_line) > 1 else 0
        self.snum = snum
        
                                                          
              
        coords = []
        for line in lines[1:]:
            values = line.strip().split()
            for i in range(0, len(values), 2):
                if i + 1 < len(values):
                    x = float(values[i])
                    y = float(values[i + 1])
                    coords.append((x, y))
        
        real_piles = coords[:pnum]
        simu_piles = coords[pnum:pnum+snum]
        
        return real_piles, simu_piles
    
    def _parse_no_simu_block(self, content: str) -> List[int]:

        no_simu_match = re.search(r'\[NO_SIMU\](.+?)(?=<\s*[+\-]?\d+\s*>)', content, re.DOTALL | re.IGNORECASE)
        if not no_simu_match:
                                                                           
            no_simu_match = re.search(r'\[NO_SIMU\](.+?)(?=<)', content, re.DOTALL | re.IGNORECASE)
        
        if not no_simu_match:
            return []
        
        type_line = no_simu_match.group(1).strip()
        type_ids = [int(x) for x in type_line.split()]
        return type_ids
    
    def _parse_pile_types(self, content: str):

        no_simu_match = re.search(r'\[NO_SIMU\](.+?)END;', content, re.DOTALL | re.IGNORECASE)
        if not no_simu_match:
            return
        
        no_simu_content = no_simu_match.group(1)
                                                   
        type_pattern = r'<\s*([+\-]?\d+)\s*>(.+?)(?=<\s*[+\-]?\d+\s*>|$)'
        matches = re.finditer(type_pattern, no_simu_content, re.DOTALL)
        
        for match in matches:
            type_id = int(match.group(1))
            type_content = match.group(2).strip()
            type_name = self._get_type_name(type_id)
            
            if type_id < 0:
                           
                self.pile_types[type_name] = self._parse_differential_type(type_content)
            else:
                           
                self.pile_types[type_name] = self._parse_single_type(type_content)
    
    def _expand_differential_types(self):
        import copy
        
                    
        base_type_name = '类型0'
        if base_type_name not in self.pile_types:
            return
        
        base_type = self.pile_types[base_type_name]
        
                        
        for type_name, type_data in list(self.pile_types.items()):
            if type_data.get('is_differential'):
                          
                expanded = copy.deepcopy(base_type)
                
                               
                if 'angle' not in expanded:
                    expanded['angle'] = [0.0, 0.0, 1.0]
                
                         
                diff_params = type_data.get('differential_params', [])
                for param in diff_params:
                    if len(param) >= 3:
                        key, idx, val = param[0], param[1], param[2]
                                          
                                     
                        if key == 'AGL=':
                                                                     
                            if 1 <= idx <= 3:
                                expanded['angle'][idx - 1] = val
                        elif key == 'HFR=':
                                     
                            if 'above_ground' in expanded and idx - 1 < len(expanded['above_ground']):
                                expanded['above_ground'][idx - 1][0] = val
                        elif key == 'HBL=':
                                     
                            if 'below_ground' in expanded and idx - 1 < len(expanded['below_ground']):
                                expanded['below_ground'][idx - 1][0] = val
                        elif key == 'NSF=':
                                      
                            if 'above_ground' in expanded and idx - 1 < len(expanded['above_ground']):
                                expanded['above_ground'][idx - 1][2] = int(val)
                        elif key == 'NSS=':
                                      
                            if 'below_ground' in expanded and idx - 1 < len(expanded['below_ground']):
                                expanded['below_ground'][idx - 1][4] = int(val)
                
                                            
                expanded['_original_differential'] = True
                expanded['_differential_params'] = diff_params
                self.pile_types[type_name] = expanded
    
    def _parse_differential_type(self, content: str) -> Dict[str, Any]:
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        
        if not lines:
            return {'is_differential': True, 'differential_params': []}
        
                  
        try:
            n_params = int(lines[0])
        except ValueError:
            return {'is_differential': True, 'differential_params': []}
        
        diff_params = []
        for i in range(1, min(n_params + 1, len(lines))):
            parts = lines[i].split()
            if len(parts) >= 3:
                key = parts[0].strip("'\"")
                idx = int(parts[1])
                val = float(parts[2])
                diff_params.append((key, idx, val))
        
        return {
            'is_differential': True,
            'base_type': '类型0',              
            'differential_params': diff_params
        }
    
    def _parse_single_type(self, content: str) -> Dict[str, Any]:
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        
        if len(lines) < 3:
            return {}
        
                                                          
                                           
        first_values = lines[0].split()
        ksh = int(first_values[0])
        ksu = int(first_values[1])
        angle_x = float(first_values[2])
        angle_y = float(first_values[3])
        angle_z = float(first_values[4])
        
                                                          
                         
        second_values = lines[1].split()
        nfr = int(second_values[0])
        
        above_ground = []
        line_idx = 1
        
        if nfr > 0:
            above_values = second_values[1:]
            current_line = 2
            while len(above_values) < nfr * 3 and current_line < len(lines):
                above_values.extend(lines[current_line].split())
                current_line += 1
            line_idx = current_line
            
            for i in range(0, nfr * 3, 3):
                if i + 2 < len(above_values):
                    h = float(above_values[i])
                    d = float(above_values[i + 1])
                    n = int(float(above_values[i + 2]))
                    above_ground.append([h, d, n])
        else:
            line_idx = 2
        
                                                          
                          
        if line_idx >= len(lines):
            return {}
        
                                                          
                        
             
                                                      
                                        
                                                             
        
                          
        remaining_values = lines[line_idx].split()
        nbl = int(remaining_values[0])
        remaining_values = remaining_values[1:]          
        
        current_read_line = line_idx + 1
        
                                  
        expected_soil_count = nbl * 5
        while len(remaining_values) < expected_soil_count:
             if current_read_line >= len(lines): break
             remaining_values.extend(lines[current_read_line].split())
             current_read_line += 1
             
                
        below_ground = []
        soil_data = remaining_values[:expected_soil_count]
        remaining_values = remaining_values[expected_soil_count:]                     

        for i in range(0, len(soil_data), 5):
            if i + 4 < len(soil_data):
                h = float(soil_data[i])
                d = float(soil_data[i + 1])
                m = float(soil_data[i + 2])
                phi = float(soil_data[i + 3])
                n = int(float(soil_data[i + 4]))
                below_ground.append([h, d, m, phi, n])
                
                                 
                                          
        while len(remaining_values) < 3:
             if current_read_line >= len(lines): break
             remaining_values.extend(lines[current_read_line].split())
             current_read_line += 1
             
        if len(remaining_values) >= 3:
            pmb = float(remaining_values[0])
            peh = float(remaining_values[1])
            pke = float(remaining_values[2])
        else:
                               
            pmb, peh, pke = 0.0, 0.0, 0.0
        
        return {
            'ksh': ksh,
            'ksu': ksu,
            'angle': [angle_x, angle_y, angle_z],
            'peh': peh,
            'pke': pke,
            'pmb': pmb,
            'above_ground': above_ground,
            'below_ground': below_ground
        }
    
    def _get_type_name(self, type_id: int) -> str:

        if type_id == 0:
            return "类型0"
        elif type_id > 0:
            return f"类型+{type_id}"
        else:
            return f"类型{type_id}"
    
    def _parse_load_block(self, content: str) -> Dict[str, Any]:

        match = re.search(r'\[CONTRAL\](.+?)END;', content, re.DOTALL | re.IGNORECASE)
        if not match:
            return {'load_cases': [], 'is_multi_case': False, 'fx': 0.0, 'fy': 0.0, 'fz': 0.0, 'mx': 0.0, 'my': 0.0, 'mz': 0.0}
        
        block_content = match.group(1).strip()
        lines = [l.strip() for l in block_content.split('\n') if l.strip()]
        
        if len(lines) < 1:
            return {'load_cases': [], 'is_multi_case': False, 'fx': 0.0, 'fy': 0.0, 'fz': 0.0, 'mx': 0.0, 'my': 0.0, 'mz': 0.0}
        
        jctr = int(lines[0].split()[0])
        
        if jctr == 1 and len(lines) >= 2:
                    
            nact = int(lines[1].split()[0])
            load_cases = []
            
                                
            line_idx = 2
            for case_idx in range(nact):
                if line_idx + 1 >= len(lines):
                    break
                
                try:
                         
                    coord_line = lines[line_idx]
                    coord_values = coord_line.split()
                    x = float(coord_values[0]) if len(coord_values) >= 1 else 0.0
                    y = float(coord_values[1]) if len(coord_values) >= 2 else 0.0
                    
                         
                    load_line = lines[line_idx + 1]
                    load_values = load_line.split()
                    
                    if len(load_values) >= 6:
                        load_case = {
                            'x': x,
                            'y': y,
                            'fx': float(load_values[0]),
                            'fy': float(load_values[1]),
                            'fz': float(load_values[2]),
                            'mx': float(load_values[3]),
                            'my': float(load_values[4]),
                            'mz': float(load_values[5])
                        }
                        load_cases.append(load_case)
                except (ValueError, IndexError):
                    pass
                
                line_idx += 2
            
                    
            is_multi_case = len(load_cases) > 1
            result = {
                'load_cases': load_cases,
                'is_multi_case': is_multi_case
            }
            
                                
            if load_cases:
                first = load_cases[0]
                result.update({
                    'x': first.get('x', 0.0),
                    'y': first.get('y', 0.0),
                    'fx': first.get('fx', 0.0),
                    'fy': first.get('fy', 0.0),
                    'fz': first.get('fz', 0.0),
                    'mx': first.get('mx', 0.0),
                    'my': first.get('my', 0.0),
                    'mz': first.get('mz', 0.0)
                })
            else:
                result.update({'x': 0.0, 'y': 0.0, 'fx': 0.0, 'fy': 0.0, 'fz': 0.0, 'mx': 0.0, 'my': 0.0, 'mz': 0.0})
            
            return result
        
        return {'load_cases': [], 'is_multi_case': False, 'fx': 0.0, 'fy': 0.0, 'fz': 0.0, 'mx': 0.0, 'my': 0.0, 'mz': 0.0}
    
    
    def _parse_disp_block(self, content: str) -> Dict[str, Any]:

                         
        match = re.search(r'\[DISP\](.+?)END;', content, re.DOTALL | re.IGNORECASE)
        if not match:
                                   
             match = re.search(r'\[DISP\]\s+([\d\.\-\+\sEe]+)', content, re.IGNORECASE)
             
        if match:
            disp_content = match.group(1).strip()
            lines = [l.strip() for l in disp_content.split('\n') if l.strip()]
            
                     
            lines = [l for l in lines if not l.upper().startswith('END')]
            
            if not lines:
                return {'ux': 0.0, 'uy': 0.0, 'uz': 0.0, 'thetax': 0.0, 'thetay': 0.0, 'thetaz': 0.0, 
                        'disp_cases': [], 'is_multi_disp': False}
            
            disp_cases = []
            for line in lines:
                values = line.split()
                if len(values) >= 6:
                    try:
                        disp_case = {
                            'ux': float(values[0]),
                            'uy': float(values[1]),
                            'uz': float(values[2]),
                            'thetax': float(values[3]),
                            'thetay': float(values[4]),
                            'thetaz': float(values[5])
                        }
                        disp_cases.append(disp_case)
                    except ValueError:
                        pass
            
            is_multi_disp = len(disp_cases) > 1
            
                    
            result = {
                'disp_cases': disp_cases,
                'is_multi_disp': is_multi_disp
            }
            
                                
            if disp_cases:
                first = disp_cases[0]
                result.update({
                    'ux': first.get('ux', 0.0),
                    'uy': first.get('uy', 0.0),
                    'uz': first.get('uz', 0.0),
                    'thetax': first.get('thetax', 0.0),
                    'thetay': first.get('thetay', 0.0),
                    'thetaz': first.get('thetaz', 0.0)
                })
            else:
                result.update({'ux': 0.0, 'uy': 0.0, 'uz': 0.0, 'thetax': 0.0, 'thetay': 0.0, 'thetaz': 0.0})
            
            return result
                    
        return {'ux': 0.0, 'uy': 0.0, 'uz': 0.0, 'thetax': 0.0, 'thetay': 0.0, 'thetaz': 0.0,
                'disp_cases': [], 'is_multi_disp': False}
    

    
    def _parse_simupile_block(self, content: str) -> List[Dict[str, Any]]:

        simu_match = re.search(r'\[SIMU_PE\](.+?)END;', content, re.DOTALL | re.IGNORECASE)
        if not simu_match:
            return []
        
        simu_text = simu_match.group(1).strip()
        lines = [l.strip() for l in simu_text.split('\n') if l.strip()]
        if not lines:
            return []
        
                 
        if not lines:
            return []
        ksctr_line = lines[0]
        try:
            ksctr_values = [int(x) for x in ksctr_line.split()]
        except:
            return []
        
                 
        stiffness_data = {}
        i = 1
        while i < len(lines):
            line = lines[i]
            block_match = re.match(r'<\s*([+\-]?\d+)\s*>', line)
            
            if block_match:
                control_id = int(block_match.group(1))
                i += 1              
                
                if i < len(lines):
                    stiffness_line = lines[i]
                                       
                    safe_line = stiffness_line.replace('-', ' -').replace('E -', 'E-')
                    
                    try:
                        values = [float(x) for x in safe_line.split()]
                        
                        if control_id < 0:
                                           
                            stiffness_data[control_id] = {
                                'control_id': control_id,
                                'type': 'diagonal',
                                'stiffness_diagonal': values[:6]             
                            }
                        else:
                                           
                            matrix = [values]
                            for _ in range(5):
                                i += 1
                                if i < len(lines):
                                    row_values = [float(x) for x in lines[i].split()]
                                    matrix.append(row_values)
                            stiffness_data[control_id] = {
                                'control_id': control_id,
                                'type': 'matrix',
                                'stiffness_matrix': matrix             
                            }
                    except Exception as e:
                        print(f"[Error] 解析刚度数值行失败: {line}, 错误: {e}")
            i += 1
        
                
        result = []
        for ksctr in ksctr_values:
            if ksctr in stiffness_data:
                result.append(stiffness_data[ksctr])
            else:
                       
                result.append({
                    'control_id': ksctr,
                    'type': 'diagonal',
                    'stiffness_diagonal': [0.0] * 6
                })
        
        return result

                                                                         
     
                                                                         
def main():
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python dat_parser.py <dat文件路径>")
        return
    
    dat_file = sys.argv[1]
    if not Path(dat_file).exists():
        print(f"文件不存在: {dat_file}")
        return
    
    parser = DATParser()
    try:
        gui_data = parser.parse_file(dat_file)
        
        print("=" * 70)
        print(f"成功解析: {dat_file}")
        print("=" * 70)
        print(f"计算模式: {gui_data['mode']}")
        print(f"桩数量: {len(gui_data['piles'])}")
        print(f"桩类型数: {len(gui_data['pile_types'])}")
        print(f"模拟桩数量: {len(gui_data.get('simulative_piles', []))}")
        print(f"启用模拟桩: {'是' if gui_data.get('has_simulative') else '否'}")
        print("\n 解析完成！")
        
    except Exception as e:
        print(f"解析失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
