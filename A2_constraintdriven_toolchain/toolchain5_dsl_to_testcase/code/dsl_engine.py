#!/usr/bin/env python3

import json
import re
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
import copy

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
    operator: str  # IMPLIES, EQ, IN, LE, GE, GT, LT, WITHIN, MOD, etc.
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

def extract_enum_value(enum_str: str) -> Optional[int]:
    """
    Extract numeric value from enumeration string.
    
    Common patterns in 3GPP:
    - "n1" → 1, "n2" → 2, "n4" → 4, "n8" → 8
    - "ms1" → 1, "ms10" → 10 (milliseconds)
    - "sf1" → 1, "sf2" → 2 (subframe)
    - "sl1" → 1, "sl2" → 2 (slot)
    
    Args:
        enum_str: Enumeration string
        
    Returns:
        Extracted integer value, or None if not parseable
    """
    if not isinstance(enum_str, str):
        return None
    
    # Pattern 1: "n<number>" (most common in 3GPP)
    match = re.match(r'^n(\d+)$', enum_str, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    # Pattern 2: "ms<number>" (milliseconds)
    match = re.match(r'^ms(\d+)$', enum_str, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    # Pattern 3: "sf<number>" (subframe)
    match = re.match(r'^sf(\d+)$', enum_str, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    # Pattern 4: "sl<number>" (slot)
    match = re.match(r'^sl(\d+)$', enum_str, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    # Pattern 5: Direct number string
    if enum_str.isdigit():
        return int(enum_str)
    
    return None


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
# 1. DSL Parser - Enhanced
# ============================================================================

class DSLParser:
    """DSL Rule Parser - Enhanced with new operators"""
    
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
        
        # Parse MOD operator: MOD(field1, field2) == 0
        if 'MOD' in normalized.upper():
            return DSLRule(
                raw_dsl=dsl_rule,
                constraint_type=ConstraintType[camel_to_snake_upper(constraint_type)] 
                    if constraint_type else ConstraintType.UNKNOWN,
                operator="MOD",
                result=normalized
            )
        
        # Parse WITHIN operator: WITHIN(field, [min, max])
        if 'WITHIN' in normalized.upper():
            return DSLRule(
                raw_dsl=dsl_rule,
                constraint_type=ConstraintType[camel_to_snake_upper(constraint_type)] 
                    if constraint_type else ConstraintType.UNKNOWN,
                operator="WITHIN",
                result=normalized
            )
        
        # Other simple constraints (EQ, MATCH, GE, GT, etc.)
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
        """Extract target values from constraints - Enhanced"""
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
        
        # WITHIN(field, [min, max]) -> [min, max]
        within_match = re.match(r'WITHIN\s*\([^,]+,\s*\[([^\]]+)\]\)', constraint, re.I)
        if within_match:
            values_str = within_match.group(1)
            parts = [v.strip() for v in values_str.split(',')]
            if len(parts) >= 2:
                return [DSLParser._parse_literal(parts[0]), DSLParser._parse_literal(parts[1])]
        
        # NE(field, value) -> value
        ne_match = re.match(r'NE\s*\([^,]+,\s*(.+)\)', constraint, re.I)
        if ne_match:
            return DSLParser._parse_literal(ne_match.group(1).strip())
        
        # LE/GE/LT/GT(field, value) or LE/GE/LT/GT(field, field +/- constant)
        comp_match = re.match(r'(LE|GE|LT|GT)\s*\(([^,]+),\s*(.+)\)', constraint, re.I)
        if comp_match:
            # Try to parse the expression (e.g., "field1 - 1")
            expression = comp_match.group(3).strip()
            return expression  # Return as string, will be evaluated later
        
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
# 3. Constraint Violator (Value Generator) - Extended
# ============================================================================

class ConstraintViolator:
    """Generate values that violate constraints - Extended with new operators"""
    
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
        Generate values that violate constraints - Extended
        
        Args:
            current_value: Current field value
            field_range: Field value range information
            constraint_type: constraint type (EQ, NE, IN, LE, GE, GT, LT, WITHIN, etc.)
            target_value: constraint target value
            
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
        """Violates enumeration constraint - Extended"""
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
        """Violates integer constraint - Extended with GT, LT"""
        current_int = FieldRangeManager._safe_int(current_value, range_min)
        
        # Handle expression like "field1 - 1"
        target_int = None
        if isinstance(target_value, str):
            # Try to parse expression (e.g., "field1 - 1")
            # For now, just extract the number if it's a simple expression
            match = re.search(r'([+-]?\d+)', target_value)
            if match:
                target_int = int(match.group(1))
        else:
            target_int = FieldRangeManager._safe_int(target_value)
        
        if constraint_type == 'EQ':
            # Violate EQ: Select boundary values (prioritize values different from both target and current)
            return range_max if current_int != range_max else range_min
        
        elif constraint_type == 'LE':
            # Violate LE: select value > target (prioritize upper bound)
            if target_int is not None and target_int < range_max:
                return range_max if range_max != current_int else (target_int + 1 if target_int + 1 <= range_max else range_min)
            # If the condition is not met, return the boundary value
            return range_max if current_int != range_max else range_min
        
        elif constraint_type == 'GE':
            # Violate GE: select value < target (prioritize lower bound)
            if target_int is not None and target_int > range_min:
                return range_min if range_min != current_int else (target_int - 1 if target_int - 1 >= range_min else range_max)
            # If the condition is not met, return the boundary value
            return range_min if current_int != range_min else range_max
        
        elif constraint_type == 'GT':
            # Violate GT: select value <= target (prioritize target itself)
            if target_int is not None:
                if range_min <= target_int <= range_max and target_int != current_int:
                    return target_int
                elif target_int > range_min:
                    return range_min if range_min != current_int else (target_int - 1 if target_int - 1 >= range_min else range_max)
            return range_min if current_int != range_min else range_max
        
        elif constraint_type == 'LT':
            # Violate LT: select value >= target (prioritize target itself)
            if target_int is not None:
                if range_min <= target_int <= range_max and target_int != current_int:
                    return target_int
                elif target_int < range_max:
                    return range_max if range_max != current_int else (target_int + 1 if target_int + 1 <= range_max else range_min)
            return range_max if current_int != range_max else range_min
        
        elif constraint_type == 'NE':
            # Violation NE: selection == target (if within domain)
            if target_int is not None and range_min <= target_int <= range_max:
                if target_int != current_int:
                    return target_int
            # If the condition is not met, return the boundary value
            return range_max if current_int != range_max else range_min
        
        elif constraint_type == 'WITHIN':
            # Violate WITHIN: select value outside [min, max]
            if isinstance(target_value, list) and len(target_value) >= 2:
                interval_min = FieldRangeManager._safe_int(target_value[0], range_min)
                interval_max = FieldRangeManager._safe_int(target_value[1], range_max)
                
                # Try to select a value < interval_min or > interval_max
                if interval_min > range_min:
                    return range_min if range_min != current_int else interval_min - 1
                elif interval_max < range_max:
                    return range_max if range_max != current_int else interval_max + 1
        
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
    
    def select_enum_to_violate_ge(
        self,
        current_value: Any,
        field_range: FieldRange,
        other_field_value: Any,
        expression_offset: int = 0
    ) -> Any:
        """
        Intelligently select enumeration value to violate GE constraint.
        
        For constraint GE(field2, field1 - offset):
        - To violate: field2 < field1 - offset
        - Therefore: field1 > field2 - offset + 1
        
        Args:
            current_value: Current value of the enumeration field
            field_range: Field range information (must have available_options)
            other_field_value: Value of the other field in the constraint
            expression_offset: Offset in expression (e.g., -1 for "field1 - 1")
            
        Returns:
            Enum value that violates the constraint
        """
        if not field_range.available_options:
            return self._force_different(current_value, field_range)
        
        # Convert other_field_value to integer
        other_field_int = FieldRangeManager._safe_int(other_field_value)
        if other_field_int is None:
            # Try to extract from enumeration
            other_field_int = extract_enum_value(str(other_field_value))
        
        if other_field_int is None:
            # Cannot determine value, fallback
            return self._force_different(current_value, field_range)
        
        # Calculate needed value
        # For GE(field2, field1 - offset):
        #   To violate: field2 < field1 - offset
        #   So: field1 > field2 - offset + 1
        #   Therefore: field1 >= field2 - offset + 1
        needed_value = other_field_int - expression_offset + 1
        
        # Find the smallest enum value >= needed_value (and != current)
        candidates = []
        for opt in field_range.available_options:
            opt_int = extract_enum_value(str(opt))
            if opt_int is not None:
                if opt_int >= needed_value and str(opt) != str(current_value):
                    candidates.append((opt_int, opt))
        
        if candidates:
            # Return the smallest valid candidate
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]
        
        # No suitable candidate found, try to get the largest available option
        max_opt = None
        max_val = -1
        for opt in field_range.available_options:
            opt_int = extract_enum_value(str(opt))
            if opt_int is not None:
                if opt_int > max_val and str(opt) != str(current_value):
                    max_val = opt_int
                    max_opt = opt
        
        if max_opt is not None:
            return max_opt
        
        # Last resort: return any different value
        return self._force_different(current_value, field_range)
    
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
# 4. Test Case Generator (Main Engine) - Extended
# ============================================================================

class TestCaseGenerator:
    """Unified Test Case Generation Engine - Extended"""
    
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
    
    def _evaluate_expression(
        self,
        expression: str,
        field1_value: Any,
        field2_value: Any
    ) -> Any:
        """
        Evaluate expression like "field1 - 1" with actual field values.
        Supports enumeration values like "n1", "n2", etc.
        
        Args:
            expression: Expression string (e.g., "field1 - 1")
            field1_value: Current value of field1 (may be int or enum string)
            field2_value: Current value of field2 (may be int or enum string)
        
        Returns:
            Evaluated result (int if successful, original expression if failed)
        """
        if not isinstance(expression, str):
            return expression
        
        # If expression doesn't contain "field", it's already a literal
        if 'field' not in expression.lower():
            as_int = FieldRangeManager._safe_int(expression)
            return as_int if as_int is not None else expression
        
        # Convert field values to integers (handle enumerations)
        def value_to_int(val):
            """Convert value to int, handling enumerations"""
            if isinstance(val, int):
                return val
            if isinstance(val, str):
                # Try to extract from enumeration
                enum_val = extract_enum_value(val)
                if enum_val is not None:
                    return enum_val
                # Try direct int conversion
                as_int = FieldRangeManager._safe_int(val)
                if as_int is not None:
                    return as_int
            return None
        
        field1_int = value_to_int(field1_value)
        field2_int = value_to_int(field2_value)
        
        # Replace field names with actual integer values
        expr = str(expression)
        if 'field1' in expr.lower():
            if field1_int is not None:
                expr = expr.replace('field1', str(field1_int))
            else:
                # Cannot evaluate, return original
                return expression
        
        if 'field2' in expr.lower():
            if field2_int is not None:
                expr = expr.replace('field2', str(field2_int))
            else:
                # Cannot evaluate, return original
                return expression
        
        # Safely evaluate simple arithmetic expressions
        try:
            # Only allow safe characters
            allowed_chars = set('0123456789+-*/ ()')
            if all(c in allowed_chars for c in expr.replace(' ', '')):
                result = eval(expr)
                if isinstance(result, (int, float)):
                    return int(result)
                return result
        except Exception:
            pass
        
        # Fallback: try to extract a number
        match = re.search(r'([+-]?\d+)', expression)
        if match:
            return int(match.group(1))
        
        return expression
    
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
            constraint_type: constraint type
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
            constraint_type: constraint type
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
        """Process constraints and generate violation values - Extended"""
        
        if rule.operator == "IMPLIES":
            return self._process_implies(
                rule, field1_info, field2_info,
                field1_range, field2_range,
                field1_can_modify, field2_can_modify
            )
        
        # Handle simple atomic constraints - Extended
        new_val1 = field1_info.current_value
        new_val2 = field2_info.current_value
        
        # Process simple atomic constraints: GE, GT, LE, LT, etc.
        if rule.operator in ['GE', 'GT', 'LE', 'LT', 'EQ', 'NE', 'IN', 'WITHIN']:
            target_expr = DSLParser.extract_value_from_constraint(rule.result)
            has_field_expression = isinstance(target_expr, str) and 'field' in target_expr.lower()
            
            # CRITICAL FIX: For GE/GT with field expressions, prioritize modifying enum fields
            if has_field_expression and rule.operator in ['GE', 'GT']:
                # Extract offset from expression (e.g., "field1 - 1" has offset -1)
                offset = 0
                if isinstance(target_expr, str):
                    if '-' in target_expr:
                        offset_match = re.search(r'-\s*(\d+)', target_expr)
                        if offset_match:
                            offset = -int(offset_match.group(1))
                    elif '+' in target_expr:
                        offset_match = re.search(r'\+\s*(\d+)', target_expr)
                        if offset_match:
                            offset = int(offset_match.group(1))
                
                # Try field1 first if it's an enumeration
                if field1_can_modify and field1_range.available_options:
                    new_val1 = self.violator.select_enum_to_violate_ge(
                        field1_info.current_value,
                        field1_range,
                        field2_info.current_value,
                        offset
                    )
                # Otherwise try field2 if it's an enumeration
                elif field2_can_modify and field2_range.available_options:
                    new_val2 = self.violator.select_enum_to_violate_ge(
                        field2_info.current_value,
                        field2_range,
                        field1_info.current_value,
                        offset
                    )
                # Neither is enum - use normal logic with expression evaluation
                else:
                    target = self._evaluate_expression(
                        target_expr,
                        field1_info.current_value,
                        field2_info.current_value
                    )
                    if field2_can_modify:
                        new_val2 = self.violator.generate_violation(
                            new_val2, field2_range, rule.operator, target
                        )
                    elif field1_can_modify:
                        new_val1 = self.violator.generate_violation(
                            new_val1, field1_range, rule.operator, target
                        )
            
            # For other operators or no expression, use standard approach
            else:
                # Evaluate expression if it contains field references
                target = target_expr
                if has_field_expression:
                    target = self._evaluate_expression(
                        target_expr,
                        field1_info.current_value,
                        field2_info.current_value
                    )
                
                # Standard violation generation
                if field2_can_modify:
                    new_val2 = self.violator.generate_violation(
                        new_val2, field2_range, rule.operator, target
                    )
                elif field1_can_modify:
                    new_val1 = self.violator.generate_violation(
                        new_val1, field1_range, rule.operator, target
                    )
        
        elif rule.operator == 'MOD':
            # Handle MOD(field1, field2) == 0 or MOD(field1, constant) == 0
            # Violate by ensuring MOD != 0
            if field2_can_modify:
                new_val2 = self.violator._force_different(field2_info.current_value, field2_range)
            elif field1_can_modify:
                new_val1 = self.violator._force_different(field1_info.current_value, field1_range)
        
        else:
            # Unknown operator: force different values
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
        """Handle IMPLIES constraints - Extended with new operators"""
        
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
        
        elif 'GE' in rule.result.upper():
            target = DSLParser.extract_value_from_constraint(rule.result)
            
            if field2_can_modify:
                new_val2 = self.violator.generate_violation(
                    new_val2, field2_range, 'GE', target
                )
        
        elif 'GT' in rule.result.upper():
            target = DSLParser.extract_value_from_constraint(rule.result)
            
            if field2_can_modify:
                new_val2 = self.violator.generate_violation(
                    new_val2, field2_range, 'GT', target
                )
        
        elif 'LT' in rule.result.upper():
            target = DSLParser.extract_value_from_constraint(rule.result)
            
            if field2_can_modify:
                new_val2 = self.violator.generate_violation(
                    new_val2, field2_range, 'LT', target
                )
        
        elif 'IN' in rule.result.upper():
            target = DSLParser.extract_value_from_constraint(rule.result)
            
            if field2_can_modify:
                new_val2 = self.violator.generate_violation(
                    new_val2, field2_range, 'IN', target
                )
        
        elif 'WITHIN' in rule.result.upper():
            target = DSLParser.extract_value_from_constraint(rule.result)
            
            if field2_can_modify:
                new_val2 = self.violator.generate_violation(
                    new_val2, field2_range, 'WITHIN', target
                )
        
        elif 'NE' in rule.result.upper():
            target = DSLParser.extract_value_from_constraint(rule.result)
            
            if field2_can_modify:
                new_val2 = self.violator.generate_violation(
                    new_val2, field2_range, 'NE', target
                )
        
        elif 'MOD' in rule.result.upper():
            # Handle IMPLIES(condition, MOD(field1, field2) == 0)
            # Violate by ensuring MOD != 0
            if field2_can_modify:
                new_val2 = self.violator._force_different(new_val2, field2_range)
        
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
    # Example: How to use Extended DSL Engine
    
    # 1. Initialize engine
    engine = TestCaseGenerator(
        range_dir="/path/to/combine_fields",
        valid_field_ids_file="/path/to/extract_reencode_success.txt"
    )
    
    # 2. Example 1: Simple atomic constraint GE
    dsl_rule = "GE(field2, field1 - 1)"
    constraint_type = "RangeAlignment"
    
    field_ids = {
        "field1_all": [347],
        "field2_all": [346],
        "actual_pairs": [[[347], [346]]]
    }
    
    ie_data = [
        {
            "field_id": 347,
            "field_name": "nrofSymbols",
            "current_value": 4
        },
        {
            "field_id": 346,
            "field_name": "startPosition",
            "current_value": 3
        }
    ]
    
    # 3. Generate Test Cases
    modified_ie_data, stats = engine.generate_test_case(
        dsl_rule, constraint_type, field_ids, ie_data
    )
    
    # 4. View Results
    print(f"Example 1 - GE(field2, field1 - 1):")
    print(f"Statistics: {stats}")
    for field in modified_ie_data:
        print(f"Field {field['field_id']}: {field['current_value']} -> {field.get('suggested_value')}")
    
    # Example 2: IN operator
    dsl_rule2 = "IMPLIES(EQ(field1, 0), IN(field2, {0, 1, 2}))"
    constraint_type2 = "ValueDependency"
    
    print(f"\nExample 2 - IMPLIES with IN:")
    print(f"DSL: {dsl_rule2}")