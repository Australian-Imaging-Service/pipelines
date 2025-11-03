#!/usr/bin/env python3
"""
Test script to verify GSP Vial Metrics environment is set up correctly
"""

import sys
import subprocess


def test_python_packages():
    """Test that all required Python packages are installed"""
    print("=" * 60)
    print("Testing Python Packages")
    print("=" * 60)
    
    packages = {
        'numpy': 'numpy',
        'pandas': 'pandas',
        'matplotlib': 'matplotlib.pyplot',
        'scipy': 'scipy.optimize',
        'pydra': 'pydra',
    }
    
    all_pass = True
    for name, import_path in packages.items():
        try:
            __import__(import_path)
            print(f"✓ {name} - OK")
        except ImportError as e:
            print(f"✗ {name} - FAILED: {e}")
            all_pass = False
    
    return all_pass


def test_external_tools():
    """Test that external tools (ANTs, MRtrix3) are available"""
    print("\n" + "=" * 60)
    print("Testing External Tools")
    print("=" * 60)
    
    tools = [
        ('antsRegistrationSyN.sh', 'ANTs registration'),
        ('mrinfo', 'MRtrix3 info'),
        ('mrconvert', 'MRtrix3 convert'),
        ('mrgrid', 'MRtrix3 grid'),
        ('mrstats', 'MRtrix3 stats'),
        ('mrtransform', 'MRtrix3 transform'),
        ('mrcat', 'MRtrix3 concatenate'),
        ('mrmath', 'MRtrix3 math'),
    ]
    
    all_pass = True
    for cmd, description in tools:
        result = subprocess.run(['which', cmd], capture_output=True)
        if result.returncode == 0:
            print(f"✓ {description} ({cmd}) - OK")
        else:
            print(f"✗ {description} ({cmd}) - NOT FOUND")
            all_pass = False
    
    return all_pass


def test_file_structure():
    """Test that required files exist in the repository"""
    print("\n" + "=" * 60)
    print("Testing File Structure")
    print("=" * 60)
    
    from pathlib import Path
    
    required_files = [
        'pydra_phantom_iterative.py',
        'plot_maps_ir.py',
        'plot_maps_TE.py',
        'Functions/plot_vial_intensity.py',
    ]
    
    all_pass = True
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print(f"✓ {file_path} - OK")
        else:
            print(f"✗ {file_path} - NOT FOUND")
            all_pass = False
    
    return all_pass


def test_script_syntax():
    """Test that main scripts have valid Python syntax"""
    print("\n" + "=" * 60)
    print("Testing Script Syntax")
    print("=" * 60)
    
    scripts = [
        'pydra_phantom_iterative.py',
        'plot_maps_ir.py',
        'plot_maps_TE.py',
    ]
    
    all_pass = True
    for script in scripts:
        result = subprocess.run(
            ['python', '-m', 'py_compile', script],
            capture_output=True
        )
        if result.returncode == 0:
            print(f"✓ {script} - Valid syntax")
        else:
            print(f"✗ {script} - Syntax error:")
            print(f"  {result.stderr.decode()}")
            all_pass = False
    
    return all_pass


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("GSP Vial Metrics - Installation Test")
    print("=" * 60)
    print()
    
    # Python version
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print()
    
    # Run tests
    tests = [
        ("Python Packages", test_python_packages),
        ("External Tools", test_external_tools),
        ("File Structure", test_file_structure),
        ("Script Syntax", test_script_syntax),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n✗ {test_name} - ERROR: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_passed = all(results.values())
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed! Environment is ready.")
        print("\nYou can now run:")
        print("  python pydra_phantom_iterative.py single [options]")
    else:
        print("✗ Some tests failed. Please review errors above.")
        print("\nCommon fixes:")
        print("  - Python packages: pip install -r requirements.txt")
        print("  - ANTs: brew install ants")
        print("  - MRtrix3: brew install mrtrix3")
        print("  - Files: Ensure all scripts are in the repository")
    print("=" * 60)
    print()
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
