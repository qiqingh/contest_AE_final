#!/usr/bin/env python3
"""
Unified DSL Test Case Generation Engine
Unified DSL Test Case Generation Engine

Design Principles:
1. No distinction between intra-IE / inter-IE, unified processing
2. Modify fields based on field_id
3. Modular design with clear responsibilities
4. Easy to extend with new constraint types
"""

import json
import re
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
import copy


# ============================================================================
# Data Structure Definition
# ============================================================================

class ConstraintType(Enum):
    """Constraint type enumeration"""
    VALUE_DEPENDENCY = "ValueDependency"
    RANGE_ALIGNMENT = "RangeAlignment"
    CROSS_REFERENCE = "CrossReference"
    ASSOCIATION = "Association"
    CONDITIONAL = "Conditional"
    UNKNOWN = "Unknown"


@dataclass
class FieldInfo:
    """Field Information"""
    field_id: int
    field_name: str
    current_value: Any
    can_modify: bool = True  # Can it be modified (based on reencode success list)


@dataclass
class FieldRange:
    """Field value range information"""
    field_id: int
    field_type: str  # INT, ENUM, CHOICE, etc.
    available_options: List[str] = None
    range_min: Optional[int] = None
    range_max: Optional[int] = None
    
    def __post_init__(self):
        if self.available_options is None:
            self.available_options = []


@dataclass
class DSLRule:
    """Parsed DSL rules"""
    raw_dsl: str
    constraint_type: ConstraintType
    operator: str  # IMPLIES, EQ, IN, LE, etc.
    condition: Optional[str] = None  # For IMPLIES(condition, result)
    result: Optional[str] = None
    field1_constraints: List[str] = None
    field2_constraints: List[str] = None
    
    def __post_init__(self):
        if self.field1_constraints is None:
            self.field1_constraints = []
        if self.field2_constraints is None:
            self.field2_constraints = []


# ============================================================================
# Helper function
# ============================================================================

def camel_to_snake_upper(name: str) -> str:
    """
    Convert camelCase to uppercase underscore style
    
    Examples:
        ValueDependency -> VALUE_DEPENDENCY
        RangeAlignment -> RANGE_ALIGNMENT
        CrossReference -> CROSS_REFERENCE
    """
    # Insert underscores before uppercase letters
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
    return s2.upper()


# ============================================================================
# 1. DSL Parser
# ============================================================================

class DSLParser:
    """DSL Rule Parser"""
    
    @staticmethod
    def parse(dsl_rule: str, constraint_type: str) -> DSLRule:
        """
        Parse DSL rules
        
        Args:
            dsl_rule: DSL rule string
            constraint_type: constraint type string
            
        Returns:
            DSLRule Object
        """
        # Normalization: Remove redundant whitespace
        normalized = ' '.join(str(dsl_rule).split())
        
        # Attempting to parse IMPLIES
        implies_match = re.match(
            r'IMPLIES\s*\(\s*(.*?)\s*,\s*(.*)\s*\)\s*$', 
            normalized, 
            flags=re.I | re.S
        )
        
        if implies_match:
            condition = implies_match.group(1).strip()
            result = implies_match.group(2).strip()
            
            return DSLRule(
                raw_dsl=dsl_rule,
                constraint_type=ConstraintType[camel_to_snake_upper(constraint_type)] 
                    if constraint_type else ConstraintType.UNKNOWN,
                operator="IMPLIES",
                condition=condition,
                result=result
            )
        
        # Other simple constraints (EQ, MATCH, etc.)
        for op in ['MATCH', 'EQ', 'NE', 'IN', 'LE', 'GE', 'LT', 'GT']:
            if normalized.upper().startswith(op):
                return DSLRule(
                    raw_dsl=dsl_rule,
                    constraint_type=ConstraintType[camel_to_snake_upper(constraint_type)] 
                        if constraint_type else ConstraintType.UNKNOWN,
                    operator=op,
                    result=normalized
                )
        
        # Default return
        return DSLRule(
            raw_dsl=dsl_rule,
            constraint_type=ConstraintType.UNKNOWN,
            operator="UNKNOWN"
        )
    
    @staticmethod
    def extract_value_from_constraint(constraint: str) -> Any:
        """Extract target values from constraints"""
        # EQ(field, value) -> value
        eq_match = re.match(r'EQ\s*\([^,]+,\s*(.+)\)', constraint, re.I)
        if eq_match:
            value_str = eq_match.group(1).strip()
            return DSLParser._parse_literal(value_str)
        
        # IN(field, {values}) -> values
        in_match = re.match(r'IN\s*\([^,]+,\s*\{([^}]+)\}\)', constraint, re.I)
        if in_match:
            values_str = in_match.group(1)
            return [DSLParser._parse_literal(v.strip()) for v in values_str.split(',')]
        
        # NE(field, value) -> value
        ne_match = re.match(r'NE\s*\([^,]+,\s*(.+)\)', constraint, re.I)
        if ne_match:
            return DSLParser._parse_literal(ne_match.group(1).strip())
        
        # LE/GE(field, value) -> value
        le_match = re.match(r'(LE|GE|LT|GT)\s*\([^,]+,\s*(.+)\)', constraint, re.I)
        if le_match:
            return DSLParser._parse_literal(le_match.group(2).strip())
        
        return None
    
    @staticmethod
    def _parse_literal(value_str: str) -> Any:
        """Parse literal values"""
        value_str = value_str.strip()
        
        if value_str.upper() == 'NULL':
            return None
        elif value_str.lower() == 'true':
            return True
        elif value_str.lower() == 'false':
            return False
        elif re.fullmatch(r'[+-]?\d+', value_str):
            return int(value_str)
        elif value_str.startswith("'") and value_str.endswith("'"):
            return value_str[1:-1]
        elif value_str.startswith('"') and value_str.endswith('"'):
            return value_str[1:-1]
        else:
            return value_str


# ============================================================================
# 2. Field Domain Manager
# ============================================================================

class FieldRangeManager:
    """Field Value Domain Information Manager"""
    
    def __init__(self, range_dir: str):
        """
        Args:
            range_dir: field range file directory path
        """
        self.range_dir = range_dir
        self._cache = {}  # field_id -> FieldRange
    
    def get_range(self, field_id: int) -> Optional[FieldRange]:
        """Get the value range information of the field"""
        if field_id in self._cache:
            return self._cache[field_id]
        
        import os
        range_file = os.path.join(self.range_dir, f"{field_id}.json")
        
        try:
            with open(range_file, 'r') as f:
                data = json.load(f)
            
            # Elevate nested asn1_rules.rules[0] to top level
            if 'asn1_rules' in data and 'rules' in data['asn1_rules']:
                rules = data['asn1_rules']['rules']
                if rules:
                    for key in ['type', 'available_options', 'range', 'min', 'max']:
                        if key in rules[0] and key not in data:
                            data[key] = rules[0][key]
            
            # Normalized types
            field_type = str(data.get('type', 'UNKNOWN')).upper()
            
            # Handle available_options
            options = data.get('available_options', [])
            if options:
                # Filter out None values and convert other values to strings
                options = [str(o) for o in options if o is not None]
                
                # INT type: Clean invalid enumerations
                if field_type == 'INT':
                    if all(x in ["None", "null", "NULL"] for x in options):
                        options = []
            
            # Get range
            range_data = data.get('range', [])
            range_min = None
            range_max = None
            if isinstance(range_data, list) and len(range_data) >= 2:
                range_min = self._safe_int(range_data[0])
                range_max = self._safe_int(range_data[1])
            
            field_range = FieldRange(
                field_id=field_id,
                field_type=field_type,
                available_options=options,
                range_min=range_min,
                range_max=range_max
            )
            
            self._cache[field_id] = field_range
            return field_range
            
        except FileNotFoundError:
            print(f"Warning: Range file not found for field_id {field_id}")
            return None
        except Exception as e:
            print(f"Error loading range for field_id {field_id}: {e}")
            return None
    
    @staticmethod
    def _safe_int(value, default=None):
        """Safe conversion to integer"""
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            s = value.strip()
            if s.lower() in ['null', 'none', '']:
                return default
            if re.fullmatch(r'[+-]?\d+', s):
                return int(s)
            if re.fullmatch(r'[+-]?\d+\.\d+', s):
                return int(float(s))
        return default


# ============================================================================
# 3. Constraint Violator (Value Generator)
# ============================================================================

class ConstraintViolator:
    """Generate values that violate constraints"""
    
    def __init__(self, range_manager: FieldRangeManager):
        self.range_manager = range_manager
    
    def generate_violation(
        self, 
        current_value: Any, 
        field_range: FieldRange,
        constraint_type: str,
        target_value: Any = None
    ) -> Any:
        """
        Generate values that violate constraints
        
        Args:
            current_value: Current field value
            field_range: Field value range information
            constraint_type: constraint type (EQ, NE, IN, LE, GE, etc.)
            constraint target value
            
        Returns:
            New value that violates constraints (guaranteed to be within domain and different from current_value)
        """
        
        # ENUM/CHOICE type: Select from available_options
        if field_range.available_options:
            return self._violate_enum(
                current_value, 
                field_range.available_options,
                constraint_type,
                target_value
            )
        
        # INT type or types with range
        if field_range.field_type == 'INT' or (field_range.range_min is not None):
            return self._violate_int(
                current_value,
                field_range.range_min or 0,
                field_range.range_max or 100,
                constraint_type,
                target_value
            )
        
        # Default: Try to force differences
        return self._force_different(current_value, field_range)
    
    def _violate_enum(
        self, 
        current_value: Any, 
        options: List[str],
        constraint_type: str,
        target_value: Any
    ) -> str:
        """Violates enumeration constraint"""
        candidates = []
        
        if constraint_type == 'EQ':
            # Violate EQ: select a value that is != target and != current
            for opt in options:
                if str(opt) != str(target_value) and str(opt) != str(current_value):
                    candidates.append(opt)
        
        elif constraint_type == 'IN':
            # Violating IN: selecting a value not in the set
            target_set = set(str(v) for v in (target_value if isinstance(target_value, list) else []))
            for opt in options:
                if str(opt) not in target_set and str(opt) != str(current_value):
                    candidates.append(opt)
        
        elif constraint_type == 'NE':
            # Violate NE: selection == target (if within domain)
            if target_value and str(target_value) in [str(o) for o in options]:
                if str(target_value) != str(current_value):
                    return str(target_value)
        
        # If there are candidates, return the first one
        if candidates:
            return candidates[0]
        
        # Otherwise return any different value
        for opt in options:
            if str(opt) != str(current_value):
                return opt
        
        # There's only one option, no way to violate it.
        return current_value
    
    def _violate_int(
        self,
        current_value: Any,
        range_min: int,
        range_max: int,
        constraint_type: str,
        target_value: Any
    ) -> int:
        """Violates integer constraint"""
        current_int = FieldRangeManager._safe_int(current_value, range_min)
        target_int = FieldRangeManager._safe_int(target_value)
        
        if constraint_type == 'EQ':
            # Violate EQ: Select boundary values (prioritize values different from both target and current)
            return range_max if current_int != range_max else range_min
        
        elif constraint_type == 'LE':
            # Violate LE: select value > target (prioritize upper bound)
            if target_int is not None and target_int < range_max:
                return range_max if range_max != current_int else range_min
            # If the condition is not met, return the boundary value
            return range_max if current_int != range_max else range_min
        
        elif constraint_type == 'GE':
            # Violate GE: select value < target (prioritize lower bound)
            if target_int is not None and target_int > range_min:
                return range_min if range_min != current_int else range_max
            # If the condition is not met, return the boundary value
            return range_max if current_int != range_max else range_min
        
        elif constraint_type == 'NE':
            # Violation NE: selection == target (if within domain)
            if target_int is not None and range_min <= target_int <= range_max:
                if target_int != current_int:
                    return target_int
            # If the condition is not met, return the boundary value
            return range_max if current_int != range_max else range_min
        
        # Default: Select peer boundary
        return range_max if current_int != range_max else range_min
    
    def _force_different(self, current_value: Any, field_range: FieldRange) -> Any:
        """Force generate different values (when constraints cannot be resolved)"""
        if field_range.available_options:
            for opt in field_range.available_options:
                if str(opt) != str(current_value):
                    return opt
        
        if field_range.range_min is not None:
            current_int = FieldRangeManager._safe_int(current_value, field_range.range_min)
            return field_range.range_max if current_int != field_range.range_max else field_range.range_min
        
        return current_value
    
    def value_in_domain(self, value: Any, field_range: FieldRange) -> bool:
        """Check if the value is within the valid range"""
        if field_range.available_options:
            return str(value) in [str(o) for o in field_range.available_options]
        
        if field_range.range_min is not None and field_range.range_max is not None:
            value_int = FieldRangeManager._safe_int(value)
            if value_int is not None:
                return field_range.range_min <= value_int <= field_range.range_max
        
        return True  # Unable to determine, assume valid by default


# ============================================================================
# 4. Test Case Generator (Main Engine)
# ============================================================================

class TestCaseGenerator:
    """Unified Test Case Generation Engine"""
    
    def __init__(
        self, 
        range_dir: str,
        valid_field_ids_file: Optional[str] = None
    ):
        """
        Args:
            range_dir: Field range file directory
            valid_field_ids_file: Valid field IDs list file (optional)
        """
        self.range_manager = FieldRangeManager(range_dir)
        self.violator = ConstraintViolator(self.range_manager)
        self.valid_field_ids = self._load_valid_field_ids(valid_field_ids_file)
    
    def _load_valid_field_ids(self, filepath: Optional[str]) -> Set[int]:
        """Load list of modifiable field IDs"""
        if not filepath:
            return set()  # Empty set means no restriction
        
        try:
            with open(filepath, 'r') as f:
                return set(int(line.strip()) for line in f if line.strip().isdigit())
        except FileNotFoundError:
            print(f"Warning: Valid field IDs file not found: {filepath}")
            return set()
    
    def can_modify_field(self, field_id: int) -> bool:
        """Check if the field can be modified"""
        if not self.valid_field_ids:
            return True  # No restriction list, all fields allowed
        return field_id in self.valid_field_ids
    
    def generate_test_case(
        self,
        dsl_rule: str,
        constraint_type: str,
        field_ids: Dict,
        ie_data: List[Dict]
    ) -> Tuple[List[Dict], Dict]:
        """
        Generate test cases
        
        Args:
            dsl_rule: DSL rule string
            constraint type
            field_ids: Field ID information (format: {"field1_all": [...], "field2_all": [...], "actual_pairs": [...]})
            ie_data: IE data list (may contain fields from multiple IEs)
            
        Returns:
            (Modified IE data, statistics)
        """
        # 1. Parse DSL
        parsed_rule = DSLParser.parse(dsl_rule, constraint_type)
        
        # 2. Extract the involved fields
        field1_ids = field_ids.get('field1_all', [])
        field2_ids = field_ids.get('field2_all', [])
        
        # 3. Locate field information
        field1_info_list = self._find_fields_by_ids(ie_data, field1_ids)
        field2_info_list = self._find_fields_by_ids(ie_data, field2_ids)
        
        if not field1_info_list or not field2_info_list:
            print(f"Warning: Cannot find fields in IE data")
            return ie_data, {'modified': 0, 'preserved': len(ie_data)}
        
        # 4. Select the first matching field pair (simplified processing)
        field1_info = field1_info_list[0]
        field2_info = field2_info_list[0]
        
        # 5. Check if modifications can be made
        field1_can_modify = self.can_modify_field(field1_info.field_id)
        field2_can_modify = self.can_modify_field(field2_info.field_id)
        
        if not field1_can_modify and not field2_can_modify:
            print(f"Info: Both fields cannot be modified, keeping original values")
            return ie_data, {'modified': 0, 'preserved': 2}
        
        # 6. Get field value range
        field1_range = self.range_manager.get_range(field1_info.field_id)
        field2_range = self.range_manager.get_range(field2_info.field_id)
        
        if not field1_range or not field2_range:
            print(f"Warning: Cannot get field ranges")
            return ie_data, {'modified': 0, 'preserved': 2}
        
        # 7. Generate violation values
        new_field1_value, new_field2_value = self._process_constraint(
            parsed_rule,
            field1_info, field2_info,
            field1_range, field2_range,
            field1_can_modify, field2_can_modify
        )
        
        # 8. Update IE data
        modified_ie_data = copy.deepcopy(ie_data)
        stats = {'modified': 0, 'preserved': 0}
        
        for field in modified_ie_data:
            if field['field_id'] == field1_info.field_id:
                if field1_can_modify and new_field1_value != field['current_value']:
                    field['suggested_value'] = new_field1_value
                    stats['modified'] += 1
                else:
                    field['suggested_value'] = field['current_value']
                    stats['preserved'] += 1
            
            elif field['field_id'] == field2_info.field_id:
                if field2_can_modify and new_field2_value != field['current_value']:
                    field['suggested_value'] = new_field2_value
                    stats['modified'] += 1
                else:
                    field['suggested_value'] = field['current_value']
                    stats['preserved'] += 1
            
            else:
                # Keep other fields at their original values
                field['suggested_value'] = field['current_value']
                stats['preserved'] += 1
        
        return modified_ie_data, stats
    
    def generate_test_cases_cartesian(
        self,
        dsl_rule: str,
        constraint_type: str,
        field_ids: Dict,
        ie_data: List[Dict]
    ) -> List[Tuple[List[Dict], Dict, str]]:
        """
        Generate test cases for all field combinations using Cartesian product
        
        For actual_pairs = [[[116, 181, 246], [271]]]
        Will generate:
        - (116, 271)
        - (181, 271)
        - (246, 271)
        
        Args:
            dsl_rule: DSL rule string
            constraint type
            field_ids: Field ID information (including actual_pairs)
            ie_data: Field data list
            
        Returns:
            List of (modified data, statistics, test case ID)
        """
        results = []
        actual_pairs = field_ids.get('actual_pairs', [])
        
        # If there are no actual_pairs, use field1_all × field2_all
        if not actual_pairs:
            field1_all = field_ids.get('field1_all', [])
            field2_all = field_ids.get('field2_all', [])
            if field1_all and field2_all:
                actual_pairs = [[field1_all, field2_all]]
            else:
                # No field information
                return []
        
        # Perform Cartesian product expansion for each pair
        for pair_idx, pair in enumerate(actual_pairs):
            field1_ids_in_pair = pair[0] if len(pair) > 0 else []
            field2_ids_in_pair = pair[1] if len(pair) > 1 else []
            
            # Cartesian product: each field1 × each field2
            for f1_id in field1_ids_in_pair:
                for f2_id in field2_ids_in_pair:
                    try:
                        # Generate test cases for this specific (f1_id, f2_id) combination
                        modified_data, stats = self._generate_for_single_field_pair(
                            dsl_rule,
                            constraint_type,
                            f1_id,
                            f2_id,
                            ie_data
                        )
                        
                        # Generate unique test case ID
                        # Format: pair0_f116_f271, pair0_f181_f271, etc.
                        test_id = f"pair{pair_idx}_f{f1_id}_f{f2_id}"
                        
                        results.append((modified_data, stats, test_id))
                        
                    except Exception as e:
                        print(f"Warning: Failed to generate test case for ({f1_id}, {f2_id}): {e}")
                        continue
        
        return results
    
    def _generate_for_single_field_pair(
        self,
        dsl_rule: str,
        constraint_type: str,
        field1_id: int,
        field2_id: int,
        ie_data: List[Dict]
    ) -> Tuple[List[Dict], Dict]:
        """
        Generate test cases for a single field pair (field1_id, field2_id)
        
        This method wraps individual field pairs into field_ids format, then calls the original generate_test_case()
        """
        # Construct field_ids for single field pairs
        single_pair_field_ids = {
            'field1_all': [field1_id],
            'field2_all': [field2_id],
            'actual_pairs': [[[field1_id], [field2_id]]]
        }
        
        # Call the existing generate_test_case method
        return self.generate_test_case(
            dsl_rule,
            constraint_type,
            single_pair_field_ids,
            ie_data
        )
    
    def _find_fields_by_ids(self, ie_data: List[Dict], field_ids: List[int]) -> List[FieldInfo]:
        """Find fields based on field_id list"""
        result = []
        for field_id in field_ids:
            for field in ie_data:
                if field.get('field_id') == field_id:
                    result.append(FieldInfo(
                        field_id=field['field_id'],
                        field_name=field.get('field_name', 'unknown'),
                        current_value=field.get('current_value'),
                        can_modify=self.can_modify_field(field['field_id'])
                    ))
                    break
        return result
    
    def _process_constraint(
        self,
        rule: DSLRule,
        field1_info: FieldInfo,
        field2_info: FieldInfo,
        field1_range: FieldRange,
        field2_range: FieldRange,
        field1_can_modify: bool,
        field2_can_modify: bool
    ) -> Tuple[Any, Any]:
        """Process constraints and generate violation values"""
        
        if rule.operator == "IMPLIES":
            return self._process_implies(
                rule, field1_info, field2_info,
                field1_range, field2_range,
                field1_can_modify, field2_can_modify
            )
        
        # Other simple constraint types
        # Simplified processing: directly generate different values
        new_val1 = field1_info.current_value
        new_val2 = field2_info.current_value
        
        if field1_can_modify:
            new_val1 = self.violator._force_different(field1_info.current_value, field1_range)
        
        if field2_can_modify:
            new_val2 = self.violator._force_different(field2_info.current_value, field2_range)
        
        return new_val1, new_val2
    
    def _process_implies(
        self,
        rule: DSLRule,
        field1_info: FieldInfo,
        field2_info: FieldInfo,
        field1_range: FieldRange,
        field2_range: FieldRange,
        field1_can_modify: bool,
        field2_can_modify: bool
    ) -> Tuple[Any, Any]:
        """Handle IMPLIES constraints"""
        
        # Violating IMPLIES(A, B): Let A be true and B be false
        
        new_val1 = field1_info.current_value
        new_val2 = field2_info.current_value
        
        # Extract constraint type and target value from result
        if 'EQ' in rule.result.upper():
            target = DSLParser.extract_value_from_constraint(rule.result)
            
            # Assuming result involves field2, generate values that violate EQ
            if field2_can_modify:
                new_val2 = self.violator.generate_violation(
                    new_val2, field2_range, 'EQ', target
                )
        
        elif 'LE' in rule.result.upper():
            target = DSLParser.extract_value_from_constraint(rule.result)
            
            if field2_can_modify:
                new_val2 = self.violator.generate_violation(
                    new_val2, field2_range, 'LE', target
                )
        
        elif 'NE' in rule.result.upper():
            target = DSLParser.extract_value_from_constraint(rule.result)
            
            if field2_can_modify:
                new_val2 = self.violator.generate_violation(
                    new_val2, field2_range, 'NE', target
                )
        
        # Ensure values are different and within the domain
        if field1_can_modify and new_val1 == field1_info.current_value:
            new_val1 = self.violator._force_different(new_val1, field1_range)
        
        if field2_can_modify and new_val2 == field2_info.current_value:
            new_val2 = self.violator._force_different(new_val2, field2_range)
        
        return new_val1, new_val2


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example: How to use DSL Engine
    
    # 1. Initialize engine
    engine = TestCaseGenerator(
        range_dir="/path/to/combine_fields",
        valid_field_ids_file="/path/to/extract_reencode_success.txt"
    )
    
    # 2. Prepare input
    dsl_rule = "IMPLIES(EQ(field1, 'nonCodebook'), EQ(field2, 1))"
    constraint_type = "ValueDependency"
    
    field_ids = {
        "field1_all": [825],
        "field2_all": [830],
        "actual_pairs": [[[825], [830]]]
    }
    
    ie_data = [
        {
            "field_id": 825,
            "field_name": "usage",
            "current_value": "nonCodebook"
        },
        {
            "field_id": 830,
            "field_name": "nrofSRS-Ports",
            "current_value": 1
        }
    ]
    
    # 3. Generate Test Cases
    modified_ie_data, stats = engine.generate_test_case(
        dsl_rule, constraint_type, field_ids, ie_data
    )
    
    # 4. View Results
    print(f"Statistics: {stats}")
    for field in modified_ie_data:
        print(f"Field {field['field_id']}: {field['current_value']} -> {field.get('suggested_value')}")