#!/usr/bin/env python
"""Manual test script to verify file summing functionality.

This script tests the fix for the "Adding spectra is not working" bug.
It simulates what happens when users select multiple files via File -> Open & Sum Multiple Files.
"""

import sys
from pathlib import Path

# Add src to path so we can import quicknxs
sys.path.insert(0, str(Path(__file__).parent / "src"))

from quicknxs.interfaces.configuration import Configuration
from quicknxs.interfaces.data_handling.filepath import FilePath


def test_marie_case():
    """Test Marie's reported case: REF_M_42112 + REF_M_42113."""
    print("\n" + "=" * 80)
    print("Testing Marie's case: REF_M_42112 + REF_M_42113")
    print("=" * 80)

    # Find the data files
    data_dir = Path(__file__).parent / "test" / "data" / "quicknxs-data"
    file1 = data_dir / "REF_M_42112.nxs.h5"
    file2 = data_dir / "REF_M_42113.nxs.h5"

    if not file1.exists() or not file2.exists():
        print(f"⚠️  Data files not found in {data_dir}")
        print(f"   Looked for: {file1.name} and {file2.name}")
        return False

    # Create composite file path (what FilePath does)
    composite_path = f"{file1}+{file2}"

    # Load data
    try:
        conf = Configuration()
        print(f"\n📂 Loading: {composite_path}")
        ws_list = conf.instrument.load_data(composite_path, conf)

        print(f"\n✅ SUCCESS! Loaded {len(ws_list)} cross-sections")
        print("   Expected: 4 cross-sections (not 8)")

        # Check details
        for i, ws in enumerate(ws_list):
            run = ws.getRun()
            xs_id = run.getProperty("cross_section_id").value
            run_numbers = run.getProperty("run_numbers").value
            events = ws.getNumberEvents()
            print(f"\n   Cross-section {i}: {xs_id}")
            print(f"     Run numbers: {run_numbers}")
            print(f"     Events: {events:,}")

        # Verify run_numbers property exists (this was the bug)
        if ws_list[0].getRun().hasProperty("run_numbers"):
            print("\n✅ run_numbers property correctly added")
            print(f"   Value: '{ws_list[0].getRun().getProperty('run_numbers').value}'")
        else:
            print("\n❌ ERROR: run_numbers property missing!")
            return False

        return len(ws_list) == 4

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_bogdan_case():
    """Test Bogdan's reported case: 4 files summed together."""
    print("\n" + "=" * 80)
    print("Testing Bogdan's case: REF_M_44724 + 44726 + 44728 + 44729")
    print("=" * 80)

    # Find the data files
    data_dir = Path(__file__).parent / "test" / "data" / "quicknxs-data"
    files = [
        data_dir / "REF_M_44724.nxs.h5",
        data_dir / "REF_M_44726.nxs.h5",
        data_dir / "REF_M_44728.nxs.h5",
        data_dir / "REF_M_44729.nxs.h5",
    ]

    # Check if files exist
    missing = [f for f in files if not f.exists()]
    if missing:
        print("⚠️  Some data files not found:")
        for f in missing:
            print(f"   {f.name}")
        print("\n   This test requires these specific files from the data repository.")
        return None  # Skip test

    # Create composite file path
    composite_path = "+".join(str(f) for f in files)

    # Load data
    try:
        conf = Configuration()
        print("\n📂 Loading 4 files...")
        ws_list = conf.instrument.load_data(composite_path, conf)

        print(f"\n✅ SUCCESS! Loaded {len(ws_list)} cross-sections")
        print("   Expected: 4 cross-sections (not 16)")

        # Check details
        for i, ws in enumerate(ws_list):
            run = ws.getRun()
            xs_id = run.getProperty("cross_section_id").value
            run_numbers = run.getProperty("run_numbers").value
            events = ws.getNumberEvents()
            print(f"\n   Cross-section {i}: {xs_id}")
            print(f"     Run numbers: {run_numbers}")
            print(f"     Events: {events:,}")

        return len(ws_list) == 4

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_filepath_parsing():
    """Test FilePath class correctly parses composite paths."""
    print("\n" + "=" * 80)
    print("Testing FilePath parsing")
    print("=" * 80)

    test_path = "/path/to/REF_M_42112.nxs.h5+/path/to/REF_M_42113.nxs.h5"
    fp = FilePath(test_path)

    print(f"\n📂 Input: {test_path}")
    print(f"\n   Is composite: {fp.is_composite}")
    print(f"   Single paths: {len(fp.single_paths)}")
    for i, path in enumerate(fp.single_paths):
        print(f"     {i + 1}. {path}")

    print(f"\n   Run numbers (short): {fp.run_numbers(string_representation='short')}")
    print(f"   Run numbers (long):  {fp.run_numbers(string_representation='long')}")

    return fp.is_composite and len(fp.single_paths) == 2


def main():
    """Run all manual tests."""
    print("\n" + "=" * 80)
    print("MANUAL TEST: File Summing Fix Verification")
    print("=" * 80)
    print("\nThis tests the fix for: 'Adding spectra is not working'")
    print("Bug: Files were concatenated (8 xs) instead of merged (4 xs)")
    print("Bug: run_numbers property was missing, causing crashes")

    results = {}

    # Test FilePath parsing
    results["filepath"] = test_filepath_parsing()

    # Test Marie's case
    results["marie"] = test_marie_case()

    # Test Bogdan's case (might skip if files missing)
    results["bogdan"] = test_bogdan_case()

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    for test_name, result in results.items():
        if result is True:
            status = "✅ PASS"
        elif result is False:
            status = "❌ FAIL"
        else:
            status = "⚠️  SKIP"
        print(f"  {status}  {test_name}")

    # Overall result
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)

    print(f"\n  Total: {passed} passed, {failed} failed, {skipped} skipped")

    if failed > 0:
        print("\n❌ Some tests failed!")
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
