"""Preview explicit, approved virtual picks. This command never sends email."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prediction_mail import build_message


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--sender', required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding='utf-8'))
    message = build_message(plan['date'], plan['picks'], args.sender)
    print('To:', message['To'])
    print('Subject:', message['Subject'])
    print(message.get_content())


if __name__ == '__main__':
    main()
