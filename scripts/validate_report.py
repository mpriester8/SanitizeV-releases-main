import os
import json
import sys


def validate_report(filepath):
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

        if not isinstance(data, list):
            print("Error: Root element is not a list.")
            sys.exit(1)

        print(f"Successfully validated {filepath}. Found {len(data)} items.")

        for item in data:
            required_keys = ["title", "description", "deepLink", "filePath",
                             "lineNumber", "confidence", "rationale", "context", "language"]
            for key in required_keys:
                if key not in item:
                    print(f"Error: Missing key '{key}' in item: {item}")
                    sys.exit(1)

            if not isinstance(item['confidence'], int) or not (1 <= item['confidence'] <= 3):
                print(f"Error: Invalid confidence score in item: {item}")
                sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    report_path = os.path.join(script_dir, "todo_report.json")
    validate_report(report_path)
