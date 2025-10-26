from __future__ import annotations
import argparse, sys
from src.core.config import Config
from src.core.engine import RulesEngine
from src.core.hints import pick_hints


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--transcript', required=True, help='Путь к текстовому файлу, по строке на сообщение')
    args = ap.parse_args()
    cfg = Config.from_yaml(args.config)
    eng = RulesEngine(cfg)

    with open(args.transcript, 'r', encoding='utf-8') as f:
        lines = [ln.strip() for ln in f if ln.strip()]

    for i, line in enumerate(lines, 1):
        res = eng.process_message('cli_chat', line)
        print(f"[{i}] {line}")
        print(f"  events={res['events']} state={res['state']} risk={res['risk']}")
        bad = [r['id'] for r in res['ltlf'] if not r['ok']]
        if bad:
            print(f"  violations={bad}")
        if res['hints']:
            print("  hints:")
            for h in res['hints']:
                print("   -", h)
        print()


if __name__ == '__main__':
    main()
