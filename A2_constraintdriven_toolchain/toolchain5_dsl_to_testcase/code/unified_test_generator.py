#!/usr/bin/env python3
"""
Unified Test Case Generator V2.1 - Enhanced Inter-IE Support
With intelligent DSL transformation for Inter-IE operators

Key improvements:
1. Smart DSL transformation: MATCH → EQ, ASSOCIATED → EQ
2. Enhanced operator detection for Inter-IE specific syntax
3. Detailed diagnostics for troubleshooting
4. Field pair deduplication (existing feature)
"""

import os
import json
import glob
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
from dsl_engine import TestCaseGenerator


# ============================================================================
# Configuration Switch
# ============================================================================

# Enable field pair deduplication
ENABLE_FIELD_PAIR_DEDUP = True

# Enable DSL transformation for Inter-IE operators
ENABLE_DSL_TRANSFORMATION = True  # NEW: Transform MATCH to EQ

# Pattern for generating test cases for each field pair
TEST_CASES_PER_PAIR_MODE = 'single'  # or 'by_constraint_type'

# Determine how many test cases to generate for each pair based on constraint type
TEST_CASES_PER_PAIR_BY_TYPE = {
    'CrossReference': 1,
    'ValueDependency': 2,
    'Association': 2,
    'Conditional': 2,
    'RangeConstraint': 2,
    'default': 1
}


class UnifiedTestCaseGeneratorV2:
    """Unified Test Case Generator - Enhanced Inter-IE Support"""
    
    def __init__(self, config: Dict):
        """
        Args:
            config: configuration dictionary containing all paths and parameters
        """
        self.config = config
        
        # Initialize DSL Engine
        self.engine = TestCaseGenerator(
            range_dir=config['range_dir'],
            valid_field_ids_file=config.get('valid_field_ids_file')
        )
        
        # Load flatten.json
        print(f"Loading flatten.json from: {config['flatten_json']}")
        with open(config['flatten_json'], 'r') as f:
            self.all_fields = json.load(f)
        print(f"✅ Loaded {len(self.all_fields)} fields from flatten.json")
        
        # Create output directory
        Path(config['output_dir']).mkdir(parents=True, exist_ok=True)
        
        # Field Pair Deduplication Tracking
        self.generated_pairs: Set[Tuple[int, int]] = set()
        self.pair_to_dsl: Dict[Tuple[int, int], str] = {}
        self.testcase_to_dsl: Dict[str, str] = {}
        
        # Statistical Information
        self.stats = {
            'total_dsl_files': 0,
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'skipped_no_rule': 0,
            'skipped_unsupported_op': 0,
            'skipped_all_pairs_generated': 0,
            'test_cases_generated': 0,
            'fields_modified': 0,
            'fields_preserved': 0,
            'error_types': {},
            'unsupported_operators': {},
            'transformed_dsls': 0,  # NEW: Count of transformed DSLs
            'transformation_details': {},  # NEW: Track transformations
            'dsl_testcase_counts': [],
            'cartesian_expansion_stats': [],
            'unique_pairs_total': 0,
            'unique_pairs_generated': 0,
            'pairs_skipped_duplicate': 0,
            'constraint_type_stats': {}
        }
        
        # Diagnostic logs
        self.diagnosis_file = config.get('diagnosis_file', 'diagnosis_v2.txt')
        self._init_diagnosis_file()
    
    def _init_diagnosis_file(self):
        """Initialize diagnostic file"""
        Path(os.path.dirname(self.diagnosis_file)).mkdir(parents=True, exist_ok=True)
        with open(self.diagnosis_file, 'w') as f:
            f.write(f"Unified Test Generator V2.1 Diagnosis Log\n")
            f.write(f"Started at: {datetime.now()}\n")
            f.write(f"Configuration:\n")
            for key, value in self.config.items():
                if key != 'flatten_json':
                    f.write(f"  {key}: {value}\n")
            f.write(f"  flatten_json: {len(self.all_fields)} fields loaded\n")
            f.write(f"\nFeature Settings:\n")
            f.write(f"  ENABLE_FIELD_PAIR_DEDUP: {ENABLE_FIELD_PAIR_DEDUP}\n")
            f.write(f"  ENABLE_DSL_TRANSFORMATION: {ENABLE_DSL_TRANSFORMATION}\n")
            f.write(f"  TEST_CASES_PER_PAIR_MODE: {TEST_CASES_PER_PAIR_MODE}\n")
            if TEST_CASES_PER_PAIR_MODE == 'by_constraint_type':
                f.write(f"  TEST_CASES_PER_PAIR_BY_TYPE: {TEST_CASES_PER_PAIR_BY_TYPE}\n")
            f.write("\n" + "="*80 + "\n\n")
    
    def _log_diagnosis(self, message: str):
        """Record diagnostic information"""
        with open(self.diagnosis_file, 'a') as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
    
    @staticmethod
    def normalize_field_pair(field1_id: int, field2_id: int) -> Tuple[int, int]:
        """Standardized field pair: always put the smaller one first"""
        return tuple(sorted([field1_id, field2_id]))
    
    def _transform_dsl_rule(self, dsl_rule: str, dsl_filename: str) -> Tuple[str, bool, str]:
        """
        Transform Inter-IE specific operators to Engine-supported operators
        
        Args:
            dsl_rule: Original DSL rule
            dsl_filename: DSL file name (for logging)
            
        Returns:
            (transformed_dsl, was_transformed, transformation_note)
        """
        if not ENABLE_DSL_TRANSFORMATION:
            return dsl_rule, False, ""
        
        original_rule = dsl_rule
        was_transformed = False
        transformations = []
        
        # Transformation 1: MATCH(field1, field2) → EQ(field1, field2)
        if 'MATCH' in dsl_rule.upper():
            # Pattern: MATCH(field1, field2) or MATCH(anything, anything)
            pattern = r'\bMATCH\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)'
            matches = re.finditer(pattern, dsl_rule, re.IGNORECASE)
            
            for match in matches:
                old_expr = match.group(0)
                field1 = match.group(1).strip()
                field2 = match.group(2).strip()
                new_expr = f'EQ({field1}, {field2})'
                dsl_rule = dsl_rule.replace(old_expr, new_expr)
                transformations.append(f'MATCH→EQ')
                was_transformed = True
        
        # Transformation 2: ASSOCIATED(field1, field2, ...) → EQ(field1, field2)
        if 'ASSOCIATED' in dsl_rule.upper():
            # Pattern matches: 
            #   ASSOCIATED(field1, field2)
            #   ASSOCIATED(field1, field2, anything)
            #   ASSOCIATED(field1, field2, "description with spaces")
            # We extract only the first two arguments and convert to EQ
            pattern = r'\bASSOCIATED\s*\(\s*([^,]+)\s*,\s*([^,)]+)(?:\s*,\s*[^)]+)?\s*\)'
            matches = list(re.finditer(pattern, dsl_rule, re.IGNORECASE))
            
            # Process matches in reverse order to avoid string offset issues
            for match in reversed(matches):
                old_expr = match.group(0)
                field1 = match.group(1).strip()
                field2 = match.group(2).strip()
                
                # Clean up field names:
                # - Remove "from ..." clauses: "field1 from IE_name" → "field1"
                # - Remove extra quotes
                field1 = re.sub(r'\s+from\s+.*$', '', field1, flags=re.IGNORECASE).strip()
                field2 = re.sub(r'\s+from\s+.*$', '', field2, flags=re.IGNORECASE).strip()
                
                new_expr = f'EQ({field1}, {field2})'
                dsl_rule = dsl_rule.replace(old_expr, new_expr)
                transformations.append(f'ASSOCIATED→EQ')
                was_transformed = True
        
        if was_transformed:
            transformation_note = '; '.join(transformations)
            self._log_diagnosis(
                f"DSL-TRANSFORM: {dsl_filename} - {transformation_note}\n"
                f"  Original: {original_rule}\n"
                f"  Transformed: {dsl_rule}"
            )
            self.stats['transformed_dsls'] += 1
            
            # Track transformation types
            for trans in transformations:
                self.stats['transformation_details'][trans] = \
                    self.stats['transformation_details'].get(trans, 0) + 1
        
        return dsl_rule, was_transformed, transformation_note if was_transformed else ""
    
    def _get_test_cases_quota(self, constraint_type: str) -> int:
        """Determine how many test cases to generate for each field pair"""
        if TEST_CASES_PER_PAIR_MODE == 'single':
            return 1
        elif TEST_CASES_PER_PAIR_MODE == 'by_constraint_type':
            return TEST_CASES_PER_PAIR_BY_TYPE.get(
                constraint_type,
                TEST_CASES_PER_PAIR_BY_TYPE['default']
            )
        else:
            return 1
    
    def process_directory(self, dsl_dir: str):
        """Process the entire DSL directory"""
        print(f"\nProcessing DSL directory: {dsl_dir}")
        
        # Recursively find all JSON files
        json_files = []
        for root, dirs, files in os.walk(dsl_dir):
            for file in files:
                if file.endswith('.json') and file != 'summary.json':
                    json_files.append(os.path.join(root, file))
        
        self.stats['total_dsl_files'] = len(json_files)
        print(f"Found {len(json_files)} DSL files")
        
        # Process each file
        for idx, dsl_file in enumerate(json_files, 1):
            if idx % 10 == 0 or idx == len(json_files):
                print(f"Progress: {idx}/{len(json_files)} "
                      f"(Generated: {self.stats['test_cases_generated']} test cases, "
                      f"Unique pairs: {len(self.generated_pairs)}, "
                      f"Transformed: {self.stats['transformed_dsls']})", 
                      end='\r')
            
            self._process_single_dsl(dsl_file)
        
        print()  # Line break
        self._print_stats()
    
    def _process_single_dsl(self, dsl_file: str):
        """Process single DSL file - with transformation and deduplication"""
        self.stats['processed'] += 1
        
        try:
            # 1. Read DSL file
            with open(dsl_file, 'r') as f:
                dsl_data = json.load(f)
            
            # 2. Check if there are valid rules
            if not dsl_data.get('has_valid_rule', False):
                self.stats['skipped'] += 1
                self.stats['skipped_no_rule'] += 1
                self._log_diagnosis(f"SKIP-NO-RULE: {os.path.basename(dsl_file)}")
                return
            
            # 3. Extract necessary information
            dsl_rule = dsl_data.get('dsl_rule', '')
            constraint_type = dsl_data.get('constraint_type', '')
            field_ids = dsl_data.get('field_ids', {})
            
            # 4. NEW: Try to transform DSL rule
            transformed_rule, was_transformed, trans_note = self._transform_dsl_rule(
                dsl_rule, 
                os.path.basename(dsl_file)
            )
            
            # Use transformed rule for processing
            processing_rule = transformed_rule
            
            # 5. Check for unsupported operators (after transformation)
            unsupported_op = self._get_unsupported_operator(processing_rule)
            if unsupported_op:
                self.stats['skipped'] += 1
                self.stats['skipped_unsupported_op'] += 1
                self.stats['unsupported_operators'][unsupported_op] = \
                    self.stats['unsupported_operators'].get(unsupported_op, 0) + 1
                
                self._log_diagnosis(
                    f"SKIP-UNSUPPORTED: {os.path.basename(dsl_file)} - "
                    f"operator={unsupported_op}, dsl={processing_rule[:100]}"
                )
                return
            
            # Field Pair Deduplication Logic
            if ENABLE_FIELD_PAIR_DEDUP:
                # 6. Extract all field pairs from this DSL
                all_pairs_in_dsl = self._extract_field_pairs_from_field_ids(field_ids)
                
                # 7. Find new field pairs (not yet generated)
                new_pairs = [
                    pair for pair in all_pairs_in_dsl 
                    if pair not in self.generated_pairs
                ]
                
                # 8. If all pairs have already been generated, skip this DSL
                if not new_pairs:
                    self.stats['skipped'] += 1
                    self.stats['skipped_all_pairs_generated'] += 1
                    self.stats['pairs_skipped_duplicate'] += len(all_pairs_in_dsl)
                    
                    self._log_diagnosis(
                        f"SKIP-ALL-PAIRS-GENERATED: {os.path.basename(dsl_file)} - "
                        f"{len(all_pairs_in_dsl)} pairs already generated"
                    )
                    return
                
                # 9. Generate test cases only for new pairs
                test_cases_quota = self._get_test_cases_quota(constraint_type)
                
                generated_count = self._generate_for_new_pairs_only(
                    dsl_file=dsl_file,
                    dsl_rule=processing_rule,  # Use transformed rule
                    constraint_type=constraint_type,
                    field_ids=field_ids,
                    new_pairs=new_pairs,
                    quota_per_pair=test_cases_quota
                )
                
                # 10. Statistics
                if generated_count > 0:
                    self.stats['successful'] += 1
                    self.stats['unique_pairs_generated'] += len(new_pairs)
                    self.stats['pairs_skipped_duplicate'] += (len(all_pairs_in_dsl) - len(new_pairs))
                    
                    log_msg = (
                        f"SUCCESS: {os.path.basename(dsl_file)} - "
                        f"generated {generated_count} test cases for {len(new_pairs)} new pairs "
                        f"(skipped {len(all_pairs_in_dsl) - len(new_pairs)} duplicate pairs)"
                    )
                    if was_transformed:
                        log_msg += f" [TRANSFORMED: {trans_note}]"
                    
                    self._log_diagnosis(log_msg)
                else:
                    self.stats['skipped'] += 1
            
            else:
                # Original Logic (No Deduplication)
                all_results = self.engine.generate_test_cases_cartesian(
                    dsl_rule=processing_rule,
                    constraint_type=constraint_type,
                    field_ids=field_ids,
                    ie_data=self.all_fields
                )
                
                if not all_results:
                    self.stats['skipped'] += 1
                    return
                
                # Save all test cases
                dsl_filename = os.path.basename(dsl_file)
                
                for modified_data, stats, test_id in all_results:
                    # Extract field number from test_id
                    try:
                        parts = test_id.split('_f')
                        if len(parts) >= 3:
                            f1_id = parts[1]
                            f2_id = parts[2]
                            output_filename = f"f{f1_id}_f{f2_id}.json"
                        else:
                            output_filename = f"{test_id}.json"
                    except:
                        output_filename = f"{test_id}.json"
                    
                    output_path = os.path.join(self.config['output_dir'], output_filename)
                    
                    with open(output_path, 'w') as f:
                        json.dump(modified_data, f, indent=2)
                    
                    self.testcase_to_dsl[output_filename] = dsl_filename
                    
                    self.stats['test_cases_generated'] += 1
                    self.stats['fields_modified'] += stats.get('modified', 0)
                    self.stats['fields_preserved'] += stats.get('preserved', 0)
                
                self.stats['successful'] += 1
            
            # Statistics by Constraint Type
            if constraint_type not in self.stats['constraint_type_stats']:
                self.stats['constraint_type_stats'][constraint_type] = {
                    'dsl_count': 0,
                    'testcase_count': 0,
                    'unique_pairs': set()
                }
            
            self.stats['constraint_type_stats'][constraint_type]['dsl_count'] += 1
            
        except Exception as e:
            self.stats['failed'] += 1
            error_type = type(e).__name__
            self.stats['error_types'][error_type] = \
                self.stats['error_types'].get(error_type, 0) + 1
            
            self._log_diagnosis(f"ERROR: {os.path.basename(dsl_file)} - {error_type}: {e}")
    
    def _extract_field_pairs_from_field_ids(self, field_ids: Dict) -> List[Tuple[int, int]]:
        """Extract all field pairs (after normalization) from field_ids"""
        pairs = []
        actual_pairs = field_ids.get('actual_pairs', [])
        
        if not actual_pairs:
            field1_all = field_ids.get('field1_all', [])
            field2_all = field_ids.get('field2_all', [])
            if field1_all and field2_all:
                actual_pairs = [[field1_all, field2_all]]
        
        for pair in actual_pairs:
            field1_ids_in_pair = pair[0] if len(pair) > 0 else []
            field2_ids_in_pair = pair[1] if len(pair) > 1 else []
            
            for f1_id in field1_ids_in_pair:
                for f2_id in field2_ids_in_pair:
                    normalized_pair = self.normalize_field_pair(f1_id, f2_id)
                    if normalized_pair not in pairs:
                        pairs.append(normalized_pair)
        
        return pairs
    
    def _generate_for_new_pairs_only(
        self,
        dsl_file: str,
        dsl_rule: str,
        constraint_type: str,
        field_ids: Dict,
        new_pairs: List[Tuple[int, int]],
        quota_per_pair: int
    ) -> int:
        """Generate test cases only for new field pairs"""
        dsl_filename = os.path.basename(dsl_file)
        generated_count = 0
        
        for pair_idx, (f1_id, f2_id) in enumerate(new_pairs):
            for variant in range(quota_per_pair):
                try:
                    modified_data, stats = self.engine._generate_for_single_field_pair(
                        dsl_rule=dsl_rule,
                        constraint_type=constraint_type,
                        field1_id=f1_id,
                        field2_id=f2_id,
                        ie_data=self.all_fields
                    )
                    
                    if quota_per_pair > 1:
                        output_filename = f"f{f1_id}_f{f2_id}_v{variant}.json"
                    else:
                        output_filename = f"f{f1_id}_f{f2_id}.json"
                    
                    output_path = os.path.join(self.config['output_dir'], output_filename)
                    
                    with open(output_path, 'w') as f:
                        json.dump(modified_data, f, indent=2)
                    
                    self.testcase_to_dsl[output_filename] = dsl_filename
                    
                    self.stats['test_cases_generated'] += 1
                    self.stats['fields_modified'] += stats.get('modified', 0)
                    self.stats['fields_preserved'] += stats.get('preserved', 0)
                    generated_count += 1
                    
                except Exception as e:
                    self._log_diagnosis(
                        f"WARNING: Failed to generate for pair ({f1_id}, {f2_id}): {e}"
                    )
                    continue
            
            normalized_pair = self.normalize_field_pair(f1_id, f2_id)
            self.generated_pairs.add(normalized_pair)
            self.pair_to_dsl[normalized_pair] = dsl_filename
        
        return generated_count
    
    def _get_unsupported_operator(self, dsl_rule: str) -> Optional[str]:
        """
        Check for unsupported operators in DSL rules
        
        Note: MATCH and ASSOCIATED are now supported through transformation to EQ
        """
        unsupported_ops = [
            # General complex operators (not supported)
            'FORALL', 'EXISTS', 'XOR', 'NAND', 'NOR',
            'COUNT', 'SUM', 'AVG', 'MIN', 'MAX',
            'SUBSET', 'SUPERSET', 'INTERSECTION', 'UNION',
            
            # Inter-IE specific operators (not supported even after transformation)
            # NOTE: ASSOCIATED removed from this list - now handled by transformation!
            # NOTE: MATCH also removed - already supported via transformation
            'CONDITIONAL',  # Complex conditional logic (different from IMPLIES)
            'MAP'          # Value mapping
            
            # Transformation coverage:
            # ✅ MATCH → EQ (supported)
            # ✅ ASSOCIATED → EQ (supported as of this version)
            # ❌ CONDITIONAL (still unsupported - complex logic)
            # ❌ MAP (still unsupported - requires multiple IMPLIES)
        ]
        
        for op in unsupported_ops:
            if op in dsl_rule.upper():
                return op
        return None
    
    def _print_stats(self):
        """Print statistics"""
        print("\n" + "="*80)
        print("GENERATION STATISTICS")
        print("="*80)
        
        print(f"\nDSL Files:")
        print(f"  Total files: {self.stats['total_dsl_files']}")
        print(f"  Processed: {self.stats['processed']}")
        print(f"  Successful: {self.stats['successful']}")
        print(f"  Skipped: {self.stats['skipped']}")
        print(f"    - No valid rule: {self.stats['skipped_no_rule']}")
        print(f"    - Unsupported operator: {self.stats['skipped_unsupported_op']}")
        if ENABLE_FIELD_PAIR_DEDUP:
            print(f"    - All pairs already generated: {self.stats['skipped_all_pairs_generated']}")
        print(f"  Failed: {self.stats['failed']}")
        
        print(f"\nTest Cases:")
        print(f"  Total generated: {self.stats['test_cases_generated']}")
        print(f"  Fields modified: {self.stats['fields_modified']}")
        print(f"  Fields preserved: {self.stats['fields_preserved']}")
        
        # NEW: Show transformation statistics
        if ENABLE_DSL_TRANSFORMATION and self.stats['transformed_dsls'] > 0:
            print(f"\n🔄 DSL Transformations:")
            print(f"  Total transformed: {self.stats['transformed_dsls']}")
            if self.stats['transformation_details']:
                print(f"  By type:")
                for trans_type, count in sorted(self.stats['transformation_details'].items()):
                    print(f"    {trans_type}: {count}")
        
        if self.testcase_to_dsl:
            print(f"\n💾 Test Case Mapping:")
            print(f"  Mapping file: testcase_to_dsl_mapping.json")
            print(f"  Readable file: testcase_to_dsl_mapping.txt")
            print(f"  Total mappings: {len(self.testcase_to_dsl)}")
        
        if ENABLE_FIELD_PAIR_DEDUP:
            print(f"\nField Pair Deduplication:")
            print(f"  Mode: {TEST_CASES_PER_PAIR_MODE}")
            print(f"  Unique pairs generated: {len(self.generated_pairs)}")
            print(f"  Test cases per pair: ", end="")
            if TEST_CASES_PER_PAIR_MODE == 'single':
                print("1")
            else:
                print("varies by constraint type")
            print(f"  Pair instances skipped (duplicates): {self.stats['pairs_skipped_duplicate']}")
            
            if len(self.generated_pairs) > 0:
                avg_tests_per_pair = self.stats['test_cases_generated'] / len(self.generated_pairs)
                print(f"  Average test cases per unique pair: {avg_tests_per_pair:.2f}")
        
        if self.stats['constraint_type_stats']:
            print(f"\nBy Constraint Type:")
            for ctype, data in sorted(self.stats['constraint_type_stats'].items()):
                print(f"  {ctype}:")
                print(f"    DSLs: {data['dsl_count']}")
                if 'testcase_count' in data:
                    print(f"    Test cases: {data['testcase_count']}")
        
        if self.stats['unsupported_operators']:
            print(f"\nUnsupported Operators:")
            for op, count in sorted(self.stats['unsupported_operators'].items(), 
                                   key=lambda x: x[1], reverse=True):
                print(f"  {op}: {count} occurrences")
        
        if self.stats['error_types']:
            print(f"\nError Types:")
            for error_type, count in sorted(self.stats['error_types'].items()):
                print(f"  {error_type}: {count} occurrences")
        
        print("\n" + "="*80)
        
        self._save_detailed_stats()
    
    def _save_detailed_stats(self):
        """Save detailed statistics to JSON file"""
        stats_output = {
            'summary': {
                'total_dsl_files': self.stats['total_dsl_files'],
                'processed': self.stats['processed'],
                'successful': self.stats['successful'],
                'skipped': self.stats['skipped'],
                'skipped_no_rule': self.stats['skipped_no_rule'],
                'skipped_unsupported_op': self.stats['skipped_unsupported_op'],
                'skipped_all_pairs_generated': self.stats['skipped_all_pairs_generated'],
                'failed': self.stats['failed'],
                'test_cases_generated': self.stats['test_cases_generated'],
                'transformed_dsls': self.stats['transformed_dsls'],
            },
            'transformation': {
                'enabled': ENABLE_DSL_TRANSFORMATION,
                'total_transformed': self.stats['transformed_dsls'],
                'by_type': self.stats['transformation_details'],
            },
            'field_pair_dedup': {
                'enabled': ENABLE_FIELD_PAIR_DEDUP,
                'mode': TEST_CASES_PER_PAIR_MODE,
                'unique_pairs_generated': len(self.generated_pairs),
                'pairs_skipped_duplicate': self.stats['pairs_skipped_duplicate'],
            },
            'constraint_type_stats': {
                k: {
                    'dsl_count': v['dsl_count'],
                    'testcase_count': v.get('testcase_count', 0),
                }
                for k, v in self.stats['constraint_type_stats'].items()
            },
            'unsupported_operators': self.stats['unsupported_operators'],
            'config': {
                'ENABLE_FIELD_PAIR_DEDUP': ENABLE_FIELD_PAIR_DEDUP,
                'ENABLE_DSL_TRANSFORMATION': ENABLE_DSL_TRANSFORMATION,
                'TEST_CASES_PER_PAIR_MODE': TEST_CASES_PER_PAIR_MODE,
                'TEST_CASES_PER_PAIR_BY_TYPE': TEST_CASES_PER_PAIR_BY_TYPE,
            }
        }
        
        stats_file = os.path.join(self.config['output_dir'], 'generation_stats_v2.json')
        with open(stats_file, 'w') as f:
            json.dump(stats_output, f, indent=2)
        
        print(f"\nDetailed statistics saved to: {stats_file}")
        
        # Save test case to DSL mapping
        if self.testcase_to_dsl:
            mapping_file = os.path.join(self.config['output_dir'], 'testcase_to_dsl_mapping.json')
            
            detailed_mapping = {
                'description': 'Mapping from test case files to their source DSL files',
                'total_test_cases': len(self.testcase_to_dsl),
                'mappings': self.testcase_to_dsl
            }
            
            with open(mapping_file, 'w') as f:
                json.dump(detailed_mapping, f, indent=2, sort_keys=True)
            
            print(f"Test case to DSL mapping saved to: {mapping_file}")
            
            mapping_txt = os.path.join(self.config['output_dir'], 'testcase_to_dsl_mapping.txt')
            with open(mapping_txt, 'w') as f:
                f.write("TEST CASE TO DSL MAPPING\n")
                f.write("="*80 + "\n\n")
                f.write(f"Total test cases: {len(self.testcase_to_dsl)}\n\n")
                f.write(f"{'Test Case File':<40} {'Source DSL File'}\n")
                f.write("-"*80 + "\n")
                
                for tc_file, dsl_file in sorted(self.testcase_to_dsl.items()):
                    f.write(f"{tc_file:<40} {dsl_file}\n")
            
            print(f"Readable mapping saved to: {mapping_txt}")


def main():
    """Main function - handles both intra-IE and inter-IE"""
    
    # ========== Intra-IE Configuration ==========
    print("\n" + "="*80)
    print("PROCESSING INTRA-IE CONSTRAINTS")
    print("="*80)
    
    intra_ie_config = {
        'range_dir': '../combine_fields',
        'flatten_json': '../02_flatten.json',
        'output_dir': '../output/test_cases_intra_ie',
        'diagnosis_file': '../diagnosis/intra_ie_generation_v2.txt',
    }
    
    intra_ie_dsl_dir = '../../toolchain4_field_pair_LLM_query/intra-IE/outputs/intra-IE_DSL_results_gpt4o'
    
    print("\nConfiguration:")
    print(f"  Field Pair Dedup: {ENABLE_FIELD_PAIR_DEDUP}")
    print(f"  DSL Transformation: {ENABLE_DSL_TRANSFORMATION}")
    print(f"  Mode: {TEST_CASES_PER_PAIR_MODE}")
    
    intra_generator = UnifiedTestCaseGeneratorV2(intra_ie_config)
    
    if os.path.exists(intra_ie_dsl_dir):
        intra_generator.process_directory(intra_ie_dsl_dir)
    else:
        print(f"  Intra-IE DSL directory not found: {intra_ie_dsl_dir}")
        print("  Skipping intra-IE generation.")
    
    # ========== Inter-IE Configuration ==========
    print("\n\n" + "="*80)
    print("PROCESSING INTER-IE CONSTRAINTS")
    print("="*80)
    
    inter_ie_config = {
        'range_dir': '../combine_fields',
        'flatten_json': '../02_flatten.json',
        'output_dir': '../output/test_cases_inter_ie',
        'diagnosis_file': '../diagnosis/inter_ie_generation_v2.txt',
    }
    
    inter_ie_dsl_dir = '../../toolchain4_field_pair_LLM_query/inter-IE/output/inter_ie_dsl_rules_gpt4o'
    
    print("\nConfiguration:")
    print(f"  Field Pair Dedup: {ENABLE_FIELD_PAIR_DEDUP}")
    print(f"  DSL Transformation: {ENABLE_DSL_TRANSFORMATION}")
    print(f"  Mode: {TEST_CASES_PER_PAIR_MODE}")
    
    inter_generator = UnifiedTestCaseGeneratorV2(inter_ie_config)
    
    if os.path.exists(inter_ie_dsl_dir):
        inter_generator.process_directory(inter_ie_dsl_dir)
    else:
        print(f"  Inter-IE DSL directory not found: {inter_ie_dsl_dir}")
        print("  Skipping inter-IE generation.")
    
    # ========== Summary ==========
    print("\n\n" + "="*80)
    print("OVERALL SUMMARY")
    print("="*80)
    
    print("\n📊 Intra-IE:")
    if os.path.exists(intra_ie_dsl_dir):
        print(f"  Test cases generated: {intra_generator.stats['test_cases_generated']}")
        if ENABLE_FIELD_PAIR_DEDUP:
            print(f"  Unique pairs: {len(intra_generator.generated_pairs)}")
        if ENABLE_DSL_TRANSFORMATION:
            print(f"  DSLs transformed: {intra_generator.stats['transformed_dsls']}")
        print(f"  Output: {intra_ie_config['output_dir']}/")
    else:
        print(f"  Skipped (directory not found)")
    
    print("\n📊 Inter-IE:")
    if os.path.exists(inter_ie_dsl_dir):
        print(f"  Test cases generated: {inter_generator.stats['test_cases_generated']}")
        if ENABLE_FIELD_PAIR_DEDUP:
            print(f"  Unique pairs: {len(inter_generator.generated_pairs)}")
        if ENABLE_DSL_TRANSFORMATION:
            print(f"  DSLs transformed: {inter_generator.stats['transformed_dsls']}")
        print(f"  Output: {inter_ie_config['output_dir']}/")
    else:
        print(f"  Skipped (directory not found)")
    
    print("\n✅ All generation complete!")


if __name__ == "__main__":
    main()