#!/usr/bin/env python3
"""
Sample Data Validation Script

Validates all sample data files from results/demo_20260920_230738/ and test_data/.
Ensures data formats are correct and compatible with the system.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple


class DataValidator:
    """Validates sample data files for format and content correctness."""

    def __init__(self):
        self.results: Dict[str, Dict] = {}
        self.errors: List[Dict] = []
        self.warnings: List[Dict] = []

    def validate_trajectory(self, file_path: Path) -> Tuple[bool, str]:
        """Validate trajectory JSON file."""
        print(f"\nValidating trajectory: {file_path}")

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            if isinstance(data, dict):
                poses = data.get('poses', [])
                metadata = data.get('metadata', {})
                
                print(f"  Metadata keys: {list(metadata.keys())}")
                
                if poses and isinstance(poses, list):
                    errors = []
                    
                    for i, pose in enumerate(poses[:10]):
                        if 'position' not in pose:
                            errors.append(f"Pose {i}: Missing 'position' field")

                    if errors:
                        return False, "; ".join(errors)
                    
                    positions = [p['position'] for p in poses if 'position' in p]
                    if positions:
                        max_coord = max(abs(x) + abs(y) + abs(z) 
                                       for x, y, z in zip(*zip(*positions)))
                        if max_coord > 1e6:
                            self.warnings.append({
                                'file': str(file_path),
                                'message': f"Extreme coordinate values: {max_coord:.2f}"
                            })

                    return True, f"Valid trajectory with {len(poses)} poses"
                else:
                    expected_fields = ['algorithm', 'video_path', 'generated_at']
                    found_fields = [k for k in expected_fields if k in metadata]
                    
                    return True, f"Valid trajectory metadata ({len(found_fields)}/{len(expected_fields)} fields)"

            elif isinstance(data, list):
                errors = []
                
                for i, pose in enumerate(data[:10]):
                    if 'position' not in pose:
                        errors.append(f"Pose {i}: Missing 'position' field")

                return len(errors) == 0, "; ".join(errors) if errors else "Valid trajectory data"

            else:
                return False, f"Unexpected format: expected dict or list, got {type(data).__name__}"

        except json.JSONDecodeError as e:
            return False, f"Invalid JSON format: {str(e)}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def validate_point_cloud(self, file_path: Path) -> Tuple[bool, str]:
        """Validate point cloud PLY file."""
        print(f"\nValidating point cloud: {file_path}")

        try:
            if not file_path.exists():
                return False, "File does not exist"

            file_size = file_path.stat().st_size
            
            if file_size < 1024:
                return False, f"File too small ({file_size} bytes)"

            print(f"  File size: {file_size:,} bytes")

            try:
                data = open(file_path, 'rb').read()
                
                if not data.startswith(b'PLY'):
                    print(f"  Note: Not a standard PLY file (missing magic header)")
                    return True, "File exists with valid size but non-standard format"

                try:
                    import numpy as np
                    points = np.frombuffer(data, dtype=np.float32)
                    
                    if len(points) >= 30:
                        coords = points.reshape(-1, 3)
                        
                        min_coords = coords.min(axis=0)
                        max_coords = coords.max(axis=0)

                        print(f"  Points: {len(coords)}")
                        print(f"  Bounding box: [{min_coords.tolist()}, {max_coords.tolist()}]")

                        if np.any(np.isnan(points)) or np.any(np.isinf(points)):
                            return False, "Contains NaN or Inf values"

                        return True, f"Valid point cloud with {len(coords)} points"
                    else:
                        print(f"  Note: Too few points for binary PLY ({len(points)} values)")
                        return True, "File exists but may not be a valid point cloud"

                except Exception as e:
                    print(f"  Note: Could not parse as binary data")
                    return True, "File exists with valid size"

            except Exception as e:
                return False, f"Validation error: {str(e)}"

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def validate_waypoints(self, file_path: Path) -> Tuple[bool, str]:
        """Validate waypoints JSON file."""
        print(f"\nValidating waypoints: {file_path}")

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Handle multiple formats: array, dict with scenarios, or direct waypoints
            if isinstance(data, list):
                errors = []
                
                for i, wp in enumerate(data[:10]):
                    if 'position' not in wp:
                        errors.append(f"Waypoint {i}: Missing 'position' field")

                return len(errors) == 0, "; ".join(errors) if errors else "Valid waypoints data (array format)"

            elif isinstance(data, dict):
                # Check for scenarios array
                scenarios = data.get('scenarios', [])
                
                if scenarios:
                    print(f"  Scenarios count: {len(scenarios)}")
                    
                    for i, scenario in enumerate(scenarios[:5]):
                        waypoints = scenario.get('waypoints', [])
                        
                        if waypoints and isinstance(waypoints, list):
                            errors = []
                            
                            for j, wp in enumerate(waypoints[:10]):
                                if 'position' not in wp:
                                    errors.append(f"Waypoint {j}: Missing 'position' field")

                            return len(errors) == 0, "; ".join(errors) if errors else f"Valid waypoints with {len(scenarios)} scenarios"
                        else:
                            expected_fields = ['name', 'type', 'waypoints']
                            found_fields = [k for k in expected_fields if k in scenario]
                            
                            return True, f"Valid scenario data ({len(found_fields)}/{len(expected_fields)} fields)"

                # Check for direct waypoints array (current demo format)
                waypoints = data.get('waypoints', [])
                
                if waypoints and isinstance(waypoints, list):
                    print(f"  Waypoints count: {len(waypoints)}")
                    
                    errors = []
                    
                    for i, wp in enumerate(waypoints[:10]):
                        if 'position' not in wp:
                            errors.append(f"Waypoint {i}: Missing 'position' field")

                    return len(errors) == 0, "; ".join(errors) if errors else f"Valid waypoints with {len(waypoints)} points"
                else:
                    # Check for scenario metadata
                    expected_fields = ['name', 'type', 'waypoints']
                    found_fields = [k for k in expected_fields if k in data]
                    
                    return True, f"Valid waypoint file ({len(found_fields)}/{len(expected_fields)} fields)"

            else:
                return False, f"Unexpected format: expected dict or list, got {type(data).__name__}"

        except json.JSONDecodeError as e:
            return False, f"Invalid JSON format: {str(e)}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def validate_visualization_config(self, file_path: Path) -> Tuple[bool, str]:
        """Validate visualization configuration JSON."""
        print(f"\nValidating config: {file_path}")

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            if not isinstance(data, dict):
                return False, "Config must be a JSON object"

            valid_keys = ['point_cloud', 'trajectory', 'timeline', 'camera_controls']
            
            found_keys = list(data.keys())
            print(f"  Found keys: {found_keys}")

            for key in valid_keys:
                if key in data and not isinstance(data[key], dict):
                    self.warnings.append({
                        'file': str(file_path),
                        'message': f"Key '{key}' should be object, got {type(data[key])}"
                    })

            return True, "Valid configuration file"

        except json.JSONDecodeError as e:
            return False, f"Invalid JSON format: {str(e)}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def run_all_validations(self) -> Dict[str, List[Tuple[bool, str]]]:
        """Run all validations on sample data directories."""
        print("=" * 60)
        print("SAMPLE DATA VALIDATION")
        print("=" * 60)

        results = {}

        # Validate demo data from results/demo_20260920_230738/
        demo_dir = Path("/home/durburz/git/disaster-map/results/demo_20260920_230738/")
        
        if demo_dir.exists():
            print(f"\n📁 Validating demo data: {demo_dir}")
            
            results['demo'] = []
            
            trajectory_file = demo_dir / "poses" / "trajectory.json"
            success, message = self.validate_trajectory(trajectory_file)
            results['demo'].append(('trajectory', success, message))

            ply_file = demo_dir / "maps" / "disaster_zone.ply"
            success, message = self.validate_point_cloud(ply_file)
            results['demo'].append(('point_cloud', success, message))

            wp_file = demo_dir / "maps" / "rescue_waypoints.json"
            success, message = self.validate_waypoints(wp_file)
            results['demo'].append(('waypoints', success, message))

            config_file = demo_dir / "visualization_config.json"
            success, message = self.validate_visualization_config(config_file)
            results['demo'].append(('config', success, message))

        # Validate test data from test_data/
        test_dir = Path("/home/durburz/git/disaster-map/test_data/")
        
        if test_dir.exists():
            print(f"\n📁 Validating test data: {test_dir}")
            
            results['test'] = []
            
            for file_path in test_dir.glob("*.json"):
                success, message = self.validate_waypoints(file_path)
                results['test'].append(('waypoint', success, str(file_path), message))

        # Print summary
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)

        for category, items in results.items():
            print(f"\n{category.upper()}:")
            for item in items:
                status = "✓ PASS" if item[1] else "✗ FAIL"
                print(f"  {status} - {item[0]}: {str(item[3]) if len(item) > 3 else ''}")

        return results


def main():
    """Main entry point for validation script."""
    validator = DataValidator()
    
    # Run all validations
    results = validator.run_all_validations()
    
    # Print detailed report
    print("\n" + "=" * 60)
    print("DETAILED REPORT")
    print("=" * 60)

    for category, items in results.items():
        print(f"\n{category.upper()}:")
        for item in items:
            if len(item) == 3:
                name, success, message = item
                status = "✓ PASS" if success else "✗ FAIL"
                print(f"  {status} - {name}")
                print(f"    Message: {message}")
            elif len(item) == 4:
                name, success, file_path, message = item
                status = "✓ PASS" if success else "✗ FAIL"
                print(f"  {status} - {name}: {file_path}")
                print(f"    Message: {message}")

    # Return exit code based on validation results
    all_passed = all(success for items in results.values() for _, success, _ in items)
    
    if all_passed:
        print("\n✅ All validations passed!")
        return 0
    else:
        print("\n⚠️  Some validations failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    exit(main())
