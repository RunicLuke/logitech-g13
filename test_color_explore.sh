#!/bin/bash
# Try different report IDs to find what controls the main backlight
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
REPORT="${1:-all}"
sudo venv/bin/python3 << PYEOF
import hid, time

d = hid.device()
d.open(0x046d, 0xc21c)

report = "$REPORT"

if report == "all":
    # Try various report IDs to find the main backlight
    for rid in [5, 7, 8, 9, 11]:
        print(f"Testing report ID {rid} - setting RED...")
        try:
            d.send_feature_report([rid, 255, 0, 0, 0])
            print(f"  Report {rid}: sent OK")
        except Exception as e:
            print(f"  Report {rid}: FAILED - {e}")
        time.sleep(2)

        print(f"Testing report ID {rid} - setting BLUE...")
        try:
            d.send_feature_report([rid, 0, 0, 255, 0])
            print(f"  Report {rid}: sent OK")
        except Exception as e:
            print(f"  Report {rid}: FAILED - {e}")
        time.sleep(2)
else:
    rid = int(report)
    print(f"Testing report ID {rid} with RED")
    d.send_feature_report([rid, 255, 0, 0, 0])

d.close()
print("Done")
PYEOF
