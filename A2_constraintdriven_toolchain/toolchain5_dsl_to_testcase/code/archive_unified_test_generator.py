#!/usr/bin/env python3
"""
Unified Test Case Generator - With Field Pair Deduplication
Unified test case generator with Field Pair deduplication

New features:
1. Field pair level deduplication (each unique pair is generated only once)
2. Configurable: Each pair generates 1 or generates N based on constraint type
3. Field pair standardization (80, 197) == (197, 80)
4. Iterate through all DSLs, the first one encountered determines the test case for that pair
"""

import os
import json
import glob
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
from dsl_engine import TestCaseGenerator


# ============================================================================
# Configuration Switch
# ============================================================================

# Enable field pair deduplication
ENABLE_FIELD_PAIR_DEDUP = True

# Pattern for generating test cases for each field pair
# 'single': Generate only 1 test case for each pair
# 'by_constraint_type': Generate N test cases based on constraint type
TEST_CASES_PER_PAIR_MODE = 'single'  # or 'by_constraint_type'

# Determine how many test cases to generate for each pair based on constraint type (used only in by_constraint_type mode)
TEST_CASES_PER_PAIR_BY_TYPE = {
    'CrossReference': 1,      # Simple, 1 is enough.
    'ValueDependency': 2,     # Complex, requires 2
    'Association': 2,
    'Conditional': 2,
    'RangeConstraint': 2,
    'default': 1              # Default 1
}


class UnifiedTestCaseGeneratorV2:
    """Unified Test Case Generator - with Field Pair Deduplication"""
    
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
        
        # Load flatten.json (load only once!)
        print(f"Loading flatten.json from: {config['flatten_json']}")
        with open(config['flatten_json'], 'r') as f:
            self.all_fields = json.load(f)
        print(f"✅ Loaded {len(self.all_fields)} fields from flatten.json")
        
        # Create output directory
        Path(config['output_dir']).mkdir(parents=True, exist_ok=True)
        
        # ========== New: Field Pair Deduplication Tracking ==========
        self.generated_pairs: Set[Tuple[int, int]] = set()
        
        # Record which DSL first generated each pair
        self.pair_to_dsl: Dict[Tuple[int, int], str] = {}
        
        # Record which DSL generated each test case file
        # Format: {"f101_f103.json": "dsl_file_name.json"}
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
            'skipped_all_pairs_generated': 0,  # Added: All pairs have been generated
            'test_cases_generated': 0,
            'fields_modified': 0,
            'fields_preserved': 0,
            'error_types': {},
            'unsupported_operators': {},
            'dsl_testcase_counts': [],
            'cartesian_expansion_stats': [],
            # Field pair analysis
            'unique_pairs_total': 0,          # Total unique pairs
            'unique_pairs_generated': 0,      # Actual generated test case unique pairs
            'pairs_skipped_duplicate': 0,     # Number of pair instances skipped due to already being generated
            'constraint_type_stats': {}       # Statistics by Constraint Type
        }
        
        # Diagnostic logs
        self.diagnosis_file = config.get('diagnosis_file', 'diagnosis_v2.txt')
        self._init_diagnosis_file()
    
    def _init_diagnosis_file(self):
        """Initialize diagnostic file"""
        Path(os.path.dirname(self.diagnosis_file)).mkdir(parents=True, exist_ok=True)
        with open(self.diagnosis_file, 'w') as f:
            f.write(f"Unified Test Generator V2 Diagnosis Log\n")
            f.write(f"Started at: {datetime.now()}\n")
            f.write(f"Configuration:\n")
            for key, value in self.config.items():
                if key != 'flatten_json':
                    f.write(f"  {key}: {value}\n")
            f.write(f"  flatten_json: {len(self.all_fields)} fields loaded\n")
            f.write(f"\nField Pair Deduplication Settings:\n")
            f.write(f"  ENABLE_FIELD_PAIR_DEDUP: {ENABLE_FIELD_PAIR_DEDUP}\n")
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
        """
        Standardized field pair: always put the smaller one first
        (80, 197) == (197, 80) → (80, 197)
        """
        return tuple(sorted([field1_id, field2_id]))
    
    def _get_test_cases_quota(self, constraint_type: str) -> int:
        """
        Based on the configuration and constraint types, determine how many test cases to generate for each field pair.
        
        Args:
            constraint_type: constraint type
            
        Returns:
            Number of test cases
        """
        if TEST_CASES_PER_PAIR_MODE == 'single':
            return 1
        elif TEST_CASES_PER_PAIR_MODE == 'by_constraint_type':
            return TEST_CASES_PER_PAIR_BY_TYPE.get(
                constraint_type,
                TEST_CASES_PER_PAIR_BY_TYPE['default']
            )
        else:
            return 1  # Default
    
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
                      f"Unique pairs: {len(self.generated_pairs)})", 
                      end='\r')
            
            self._process_single_dsl(dsl_file)
        
        print()  # Line break
        self._print_stats()
    
    def _process_single_dsl(self, dsl_file: str):
        """Process single DSL file - with Field Pair deduplication"""
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
            
            # 4. Check for unsupported operators
            unsupported_op = self._get_unsupported_operator(dsl_rule)
            if unsupported_op:
                self.stats['skipped'] += 1
                self.stats['skipped_unsupported_op'] += 1
                self.stats['unsupported_operators'][unsupported_op] = \
                    self.stats['unsupported_operators'].get(unsupported_op, 0) + 1
                
                self._log_diagnosis(
                    f"SKIP-UNSUPPORTED: {os.path.basename(dsl_file)} - "
                    f"operator={unsupported_op}"
                )
                return
            
            # ========== New: Field Pair Deduplication Logic ==========
            if ENABLE_FIELD_PAIR_DEDUP:
                # 5. Extract all field pairs from this DSL
                all_pairs_in_dsl = self._extract_field_pairs_from_field_ids(field_ids)
                
                # 6. Find new field pairs (not yet generated)
                new_pairs = [
                    pair for pair in all_pairs_in_dsl 
                    if pair not in self.generated_pairs
                ]
                
                # 7. If all pairs have already been generated, skip this DSL
                if not new_pairs:
                    self.stats['skipped'] += 1
                    self.stats['skipped_all_pairs_generated'] += 1
                    self.stats['pairs_skipped_duplicate'] += len(all_pairs_in_dsl)
                    
                    self._log_diagnosis(
                        f"SKIP-ALL-PAIRS-GENERATED: {os.path.basename(dsl_file)} - "
                        f"{len(all_pairs_in_dsl)} pairs already generated"
                    )
                    return
                
                # 8. Generate test cases only for new pairs
                test_cases_quota = self._get_test_cases_quota(constraint_type)
                
                generated_count = self._generate_for_new_pairs_only(
                    dsl_file=dsl_file,
                    dsl_rule=dsl_rule,
                    constraint_type=constraint_type,
                    field_ids=field_ids,
                    new_pairs=new_pairs,
                    quota_per_pair=test_cases_quota
                )
                
                # 9. Statistics
                if generated_count > 0:
                    self.stats['successful'] += 1
                    self.stats['unique_pairs_generated'] += len(new_pairs)
                    self.stats['pairs_skipped_duplicate'] += (len(all_pairs_in_dsl) - len(new_pairs))
                    
                    self._log_diagnosis(
                        f"SUCCESS: {os.path.basename(dsl_file)} - "
                        f"generated {generated_count} test cases for {len(new_pairs)} new pairs "
                        f"(skipped {len(all_pairs_in_dsl) - len(new_pairs)} duplicate pairs)"
                    )
                else:
                    self.stats['skipped'] += 1
            
            else:
                # ========== Original Logic (No Deduplication) ==========
                all_results = self.engine.generate_test_cases_cartesian(
                    dsl_rule=dsl_rule,
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
                    # test_id format: "pair0_f80_f197"
                    try:
                        # Extract field number
                        parts = test_id.split('_f')
                        if len(parts) >= 3:
                            f1_id = parts[1]
                            f2_id = parts[2]
                            output_filename = f"f{f1_id}_f{f2_id}.json"
                        else:
                            # Downgrade: Use original format
                            output_filename = f"{test_id}.json"
                    except:
                        # Downgrade: Use original format
                        output_filename = f"{test_id}.json"
                    
                    output_path = os.path.join(self.config['output_dir'], output_filename)
                    
                    with open(output_path, 'w') as f:
                        json.dump(modified_data, f, indent=2)
                    
                    # Record which DSL generated this test case
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
        """
        Extract all field pairs (after normalization) from field_ids
        
        Args:
            field_ids: DSL field_ids data
            
        Returns:
            Standardized field pairs list
        """
        pairs = []
        actual_pairs = field_ids.get('actual_pairs', [])
        
        # If there are no actual_pairs, use field1_all × field2_all
        if not actual_pairs:
            field1_all = field_ids.get('field1_all', [])
            field2_all = field_ids.get('field2_all', [])
            if field1_all and field2_all:
                actual_pairs = [[field1_all, field2_all]]
        
        # Expand all pairs
        for pair in actual_pairs:
            field1_ids_in_pair = pair[0] if len(pair) > 0 else []
            field2_ids_in_pair = pair[1] if len(pair) > 1 else []
            
            for f1_id in field1_ids_in_pair:
                for f2_id in field2_ids_in_pair:
                    # Standardization
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
        """
        Generate test cases only for new field pairs
        
        Args:
            dsl_file: DSL file path
            dsl_rule: DSL Rule
            constraint_type: Constraint Type
            field_ids: Field ID information
            new_pairs: New field pairs (not previously generated)
            quota_per_pair: How many test cases to generate for each pair
            
        Returns:
            Number of generated test cases
        """
        dsl_filename = os.path.basename(dsl_file)
        generated_count = 0
        
        for pair_idx, (f1_id, f2_id) in enumerate(new_pairs):
            # Generate quota_per_pair test cases for this field pair
            for variant in range(quota_per_pair):
                try:
                    # Call engine to generate test cases for a single field pair
                    modified_data, stats = self.engine._generate_for_single_field_pair(
                        dsl_rule=dsl_rule,
                        constraint_type=constraint_type,
                        field1_id=f1_id,
                        field2_id=f2_id,
                        ie_data=self.all_fields
                    )
                    
                    # Generate simplified filename: include field number only
                    # Format: f101_f103.json or f101_f103_v1.json (if there are multiple variants)
                    if quota_per_pair > 1:
                        output_filename = f"f{f1_id}_f{f2_id}_v{variant}.json"
                    else:
                        output_filename = f"f{f1_id}_f{f2_id}.json"
                    
                    # Save test case
                    output_path = os.path.join(self.config['output_dir'], output_filename)
                    
                    with open(output_path, 'w') as f:
                        json.dump(modified_data, f, indent=2)
                    
                    # Records which DSL generated this test case
                    self.testcase_to_dsl[output_filename] = dsl_filename
                    
                    # Update Statistics
                    self.stats['test_cases_generated'] += 1
                    self.stats['fields_modified'] += stats.get('modified', 0)
                    self.stats['fields_preserved'] += stats.get('preserved', 0)
                    generated_count += 1
                    
                except Exception as e:
                    self._log_diagnosis(
                        f"WARNING: Failed to generate for pair ({f1_id}, {f2_id}): {e}"
                    )
                    continue
            
            # Mark this pair as generated
            normalized_pair = self.normalize_field_pair(f1_id, f2_id)
            self.generated_pairs.add(normalized_pair)
            self.pair_to_dsl[normalized_pair] = dsl_filename
        
        return generated_count
    
    def _get_unsupported_operator(self, dsl_rule: str) -> Optional[str]:
        """Check for unsupported operators in DSL rules"""
        unsupported_ops = [
            'FORALL', 'EXISTS', 'XOR', 'NAND', 'NOR',
            'COUNT', 'SUM', 'AVG', 'MIN', 'MAX',
            'SUBSET', 'SUPERSET', 'INTERSECTION', 'UNION'
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
            for op, count in sorted(self.stats['unsupported_operators'].items()):
                print(f"  {op}: {count} occurrences")
        
        if self.stats['error_types']:
            print(f"\nError Types:")
            for error_type, count in sorted(self.stats['error_types'].items()):
                print(f"  {error_type}: {count} occurrences")
        
        print("\n" + "="*80)
        
        # Save detailed statistics to file
        self._save_detailed_stats()
    
    def _save_detailed_stats(self):
        """Save detailed statistics to JSON file"""
        stats_output = {
            'summary': {
                'total_dsl_files': self.stats['total_dsl_files'],
                'processed': self.stats['processed'],
                'successful': self.stats['successful'],
                'skipped': self.stats['skipped'],
                'failed': self.stats['failed'],
                'test_cases_generated': self.stats['test_cases_generated'],
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
            'config': {
                'ENABLE_FIELD_PAIR_DEDUP': ENABLE_FIELD_PAIR_DEDUP,
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
            
            # Create more detailed mapping information
            detailed_mapping = {
                'description': 'Mapping from test case files to their source DSL files',
                'total_test_cases': len(self.testcase_to_dsl),
                'mappings': self.testcase_to_dsl
            }
            
            with open(mapping_file, 'w') as f:
                json.dump(detailed_mapping, f, indent=2, sort_keys=True)
            
            print(f"Test case to DSL mapping saved to: {mapping_file}")
            
            # Also save a readable text version
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
    """Main function - handles both intra-IE and inter-IE simultaneously"""
    
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
    
    # Create generator (intra-IE usually doesn't need deduplication due to few duplicates)
    print("\nConfiguration:")
    print(f"  Field Pair Dedup: {ENABLE_FIELD_PAIR_DEDUP}")
    print(f"  Mode: {TEST_CASES_PER_PAIR_MODE}")
    
    intra_generator = UnifiedTestCaseGeneratorV2(intra_ie_config)
    
    # Handle intra-IE DSL
    if os.path.exists(intra_ie_dsl_dir):
        intra_generator.process_directory(intra_ie_dsl_dir)
    else:
        print(f"  Intra-IE DSL directory not found: {intra_ie_dsl_dir}")
        print("   Skipping intra-IE generation.")
    
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
    
    # Create generator (inter-IE requires deduplication)
    print("\nConfiguration:")
    print(f"  Field Pair Dedup: {ENABLE_FIELD_PAIR_DEDUP}")
    print(f"  Mode: {TEST_CASES_PER_PAIR_MODE}")
    
    inter_generator = UnifiedTestCaseGeneratorV2(inter_ie_config)
    
    # Handle inter-IE DSL
    if os.path.exists(inter_ie_dsl_dir):
        inter_generator.process_directory(inter_ie_dsl_dir)
    else:
        print(f"  Inter-IE DSL directory not found: {inter_ie_dsl_dir}")
        print("   Skipping inter-IE generation.")
    
    # ========== Summary ==========
    print("\n\n" + "="*80)
    print("OVERALL SUMMARY")
    print("="*80)
    
    print("\n📊 Intra-IE:")
    if os.path.exists(intra_ie_dsl_dir):
        print(f"  Test cases generated: {intra_generator.stats['test_cases_generated']}")
        if ENABLE_FIELD_PAIR_DEDUP:
            print(f"  Unique pairs: {len(intra_generator.generated_pairs)}")
        print(f"  Output: {intra_ie_config['output_dir']}/")
    else:
        print(f"  Skipped (directory not found)")
    
    print("\n Inter-IE:")
    if os.path.exists(inter_ie_dsl_dir):
        print(f"  Test cases generated: {inter_generator.stats['test_cases_generated']}")
        if ENABLE_FIELD_PAIR_DEDUP:
            print(f"  Unique pairs: {len(inter_generator.generated_pairs)}")
        print(f"  Output: {inter_ie_config['output_dir']}/")
    else:
        print(f"  Skipped (directory not found)")
    
    print("\n All generation complete!")


if __name__ == "__main__":
    main()